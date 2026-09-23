from __future__ import annotations

import hashlib
from datetime import datetime
from time import perf_counter

import cv2
import numpy as np

from .config import ConfigError, polygon_signature, validate_polygon
from .sources import Frame, SourceError, iso, read_image, utcnow

PREPROCESSING = "gray-gaussian-5x5-sigma0-v1"


def pixel_hash(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def preprocess(image):
    return cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (5, 5), 0)


def difference_score(current, reference, mask):
    selected = mask != 0
    if not np.any(selected):
        raise ConfigError("The parking polygon has no usable pixels.")
    return float(np.mean(cv2.absdiff(current, reference)[selected]) / 255.0)


def classify(score, vacant_max, occupied_min):
    if not (0 <= vacant_max < occupied_min <= 1):
        return "unknown"
    if score <= vacant_max:
        return "vacant"
    if score >= occupied_min:
        return "occupied"
    return "uncertain"


def thresholds(vacant_scores, occupied_scores):
    if min(len(vacant_scores), len(occupied_scores)) < 5:
        return {"status": "uncalibrated", "reason": "need_five_samples_per_state"}
    low = float(np.percentile(vacant_scores, 95))
    high = float(np.percentile(occupied_scores, 5))
    return {"status": "calibrated" if low < high else "uncalibrated",
            "reason": None if low < high else "overlapping_score_distributions",
            "vacant_max": low, "occupied_min": high}


def occupancy_summary(slots, available=True):
    counts = {s: sum(x["state"] == s for x in slots) for s in ("occupied", "vacant", "uncertain", "unknown")}
    n = len(slots)
    unresolved = counts["unknown"] + counts["uncertain"]
    return {"total_monitored_bays": n, **counts, "unresolved": unresolved,
            "decision_coverage_pct": 100 * (n - unresolved) / n if n and available else None,
            "occupancy_pct": 100 * counts["occupied"] / n if n and available and not unresolved else None,
            "occupancy_min_pct": 100 * counts["occupied"] / n if n and available else None,
            "occupancy_max_pct": 100 * (counts["occupied"] + unresolved) / n if n and available else None}


class Analyzer:
    def __init__(self, config):
        self.config = config
        path = config.resolve(config.data.get("setup_image"))
        if path is None:
            raise ConfigError("Capture a setup frame and configure parking polygons first.")
        self.setup = read_image(path)
        self.height, self.width = self.setup.shape[:2]
        self.setup_hash = pixel_hash(self.setup)
        self.masks = {}
        self.references = {}
        self.reference_errors = {}
        self.reference_hashes = {}
        self.slot_config = config.data["slots"]
        if not self.slot_config:
            raise ConfigError("Configure at least one parking polygon first.")
        background_mask = np.full((self.height, self.width), 255, np.uint8)
        for slot in self.slot_config:
            points = validate_polygon(slot.get("polygon"), self.width, self.height)
            mask = np.zeros_like(background_mask)
            cv2.fillPoly(mask, [points], 255)
            self.masks[slot["id"]] = mask
            # Exclude bays plus a small border from alignment feature matching.
            exclusion = cv2.dilate(mask, np.ones((15, 15), np.uint8))
            background_mask[exclusion != 0] = 0
            reference_path = config.resolve(slot.get("reference_image"))
            try:
                if reference_path is None:
                    raise SourceError("missing_empty_reference")
                reference = read_image(reference_path)
                if reference.shape != self.setup.shape:
                    raise SourceError("reference_resolution_mismatch")
                self.reference_hashes[slot["id"]] = pixel_hash(reference)
                self.references[slot["id"]] = preprocess(reference)
            except SourceError as exc:
                self.reference_errors[slot["id"]] = str(exc)
        self.background_mask = background_mask
        self.orb = cv2.ORB_create(nfeatures=2500, edgeThreshold=15)
        self.setup_keypoints, self.setup_descriptors = self.orb.detectAndCompute(
            cv2.cvtColor(self.setup, cv2.COLOR_BGR2GRAY), background_mask)

    def alignment(self, image):
        if image.shape != self.setup.shape:
            return {"ok": False, "reason": "resolution_changed", "inliers": 0}
        keypoints, descriptors = self.orb.detectAndCompute(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), self.background_mask)
        if descriptors is None or self.setup_descriptors is None:
            return {"ok": False, "reason": "insufficient_background_features", "inliers": 0}
        matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(self.setup_descriptors, descriptors, k=2)
        good = [pair[0] for pair in matches if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance]
        minimum = self.config.data.get("alignment", {}).get("min_inliers", 12)
        if len(good) < minimum:
            return {"ok": False, "reason": "insufficient_background_matches", "inliers": len(good)}
        a = np.float32([self.setup_keypoints[m.queryIdx].pt for m in good])
        b = np.float32([keypoints[m.trainIdx].pt for m in good])
        transform, inlier_mask = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=3)
        inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
        if transform is None or inliers < minimum or inliers / len(good) < 0.5:
            return {"ok": False, "reason": "background_alignment_failed", "inliers": inliers}
        stable = a[inlier_mask.ravel() != 0]
        span = np.ptp(stable, axis=0)
        if span[0] < self.width * 0.25 or span[1] < self.height * 0.25:
            return {"ok": False, "reason": "background_matches_too_concentrated", "inliers": inliers}
        corners = np.float32([[0, 0], [self.width - 1, 0], [0, self.height - 1], [self.width - 1, self.height - 1]])
        projected = cv2.transform(corners.reshape(1, -1, 2), transform)[0]
        displacement = float(np.linalg.norm(projected - corners, axis=1).max())
        limit = self.config.data.get("alignment", {}).get("max_displacement_pixels", 8)
        return {"ok": displacement <= limit, "reason": None if displacement <= limit else "camera_view_changed",
                "inliers": inliers, "max_displacement_pixels": displacement}

    def slot_score(self, slot_id, image):
        if slot_id not in self.references:
            raise ConfigError("A verified empty reference is required before calibration.")
        if image.shape != self.setup.shape:
            raise ConfigError("Sample resolution differs from the setup view.")
        return difference_score(preprocess(image), self.references[slot_id], self.masks[slot_id])

    def _calibration_valid(self, slot):
        calibration = slot.get("calibration") or {}
        if calibration.get("status") != "calibrated":
            return False
        if calibration.get("reference_pixel_hash") != self.reference_hashes.get(slot["id"]):
            return False
        if calibration.get("setup_pixel_hash") != self.setup_hash:
            return False
        if calibration.get("polygon_signature") != polygon_signature(slot["polygon"]):
            return False
        if calibration.get("preprocessing") != PREPROCESSING:
            return False
        low, high = calibration.get("vacant_max"), calibration.get("occupied_min")
        return type(low) in (float, int) and type(high) in (float, int) and 0 <= low < high <= 1

    def analyze(self, frame: Frame):
        started = perf_counter()
        processing_at = utcnow()
        delay = max(0.0, (processing_at - frame.received_at).total_seconds())
        source_age = (processing_at - frame.captured_at).total_seconds() if frame.captured_at else None
        stale_limit = self.config.data.get("stale_after_seconds", 15)
        stale = delay > stale_limit or (source_age is not None and source_age > stale_limit)
        bad_clock = source_age is not None and source_age < -5
        alignment = self.alignment(frame.image)
        reason = "stale_frame" if stale else "source_timestamp_in_future" if bad_clock else alignment["reason"]
        slots = []
        gray = preprocess(frame.image) if reason is None else None
        for slot in self.slot_config:
            slot_id = slot["id"]
            record = {"slot_id": slot_id, "state": "unknown", "difference_score": None,
                      "reason": reason or self.reference_errors.get(slot_id)}
            if record["reason"] is None:
                score = difference_score(gray, self.references[slot_id], self.masks[slot_id])
                record["difference_score"] = score
                if self._calibration_valid(slot):
                    c = slot["calibration"]
                    record["state"] = classify(score, c["vacant_max"], c["occupied_min"])
                    if record["state"] == "uncertain":
                        record["reason"] = "between_decision_boundaries"
                else:
                    record["reason"] = "missing_or_invalid_calibration"
            slots.append(record)
        return {"schema_version": 1, "source_id": self.config.data["source_id"], "frame_id": frame.frame_id,
                "source_captured_at": iso(frame.captured_at), "capture_time_status": frame.capture_time_status,
                "received_at": iso(frame.received_at), "processing_started_at": iso(processing_at), "processed_at": iso(utcnow()),
                "processing_duration_ms": (perf_counter() - started) * 1000,
                "frame_age_seconds": max(0.0, source_age) if source_age is not None else None,
                "retrieval_age_seconds": delay, "freshness_basis": "source_timestamp" if frame.captured_at else "retrieval_only",
                "retrieval_status": "success", "analysis_status": "unavailable" if reason else "estimated",
                "stale": stale, "error": reason, "alignment": alignment,
                "frame_width": frame.image.shape[1], "frame_height": frame.image.shape[0],
                "summary": occupancy_summary(slots, available=reason is None), "slots": slots,
                "method": "vacant_reference_difference", "preprocessing": PREPROCESSING}

    def failure(self, reason):
        slots = [{"slot_id": s["id"], "state": "unknown", "difference_score": None, "reason": reason} for s in self.slot_config]
        return {"schema_version": 1, "source_id": self.config.data["source_id"], "frame_id": None,
                "source_captured_at": None, "capture_time_status": "unavailable", "received_at": None,
                "processing_started_at": iso(utcnow()), "processed_at": iso(utcnow()), "processing_duration_ms": None,
                "frame_age_seconds": None, "retrieval_age_seconds": None, "freshness_basis": "unavailable",
                "retrieval_status": "failed", "analysis_status": "unavailable", "stale": True, "error": reason,
                "alignment": None, "summary": occupancy_summary(slots, available=False), "slots": slots,
                "method": "vacant_reference_difference", "preprocessing": PREPROCESSING}
