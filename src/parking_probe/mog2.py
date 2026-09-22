"""Chronological MOG2 foreground evidence beside vacant-reference distance.

One full-frame model per recording/camera. Verified empty bay patches seed a
background mosaic; a parked car in the first frame is not assumed background.
Foreground fraction is an experimental feature, never a probability.
"""
from copy import deepcopy
import hashlib
import json
import math
from time import perf_counter

import cv2
import numpy as np

from .config import ConfigError, polygon_signature
from .sources import read_image, utcnow
from .vision import classify, occupancy_summary, pixel_hash

PARAMETERS = {"version": 1, "history": 500, "var_threshold": 16.0, "detect_shadows": True,
              "learning_rate": .001, "bootstrap_applications": 30, "morphology_kernel": 3,
              "gap_reset_seconds": 15, "restabilization_samples": 2,
              "colour": "BGR-gaussian-5x5", "seed": "verified-empty-bay-mosaic"}


def clean_foreground(mask, kernel_size=3):
    # Shadows are 127, foreground 255. Never threshold at >0.
    foreground = np.uint8(mask == 255) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)


class MOG2Branch:
    def __init__(self, analyzer, calibration=None, interval=3, *, expected_sample_interval=None):
        self.analyzer = analyzer
        self.interval = interval
        # Omitted preserves every existing video signature/threshold, including
        # callers replaying at a different interval. Snapshot sources opt in.
        expected = 3 if expected_sample_interval is None else expected_sample_interval
        if type(expected) not in (int, float) or not math.isfinite(expected) or expected <= 0:
            raise ConfigError('Expected sample interval must be positive and finite.')
        self.expected_sample_interval = expected
        self.parameters = dict(PARAMETERS)
        if expected != 3:
            self.parameters['gap_reset_seconds'] = 5 * expected
        self.calibration = calibration or {}
        self.seed = analyzer.setup.copy()
        # References can be captured at different times. Only their own bay's
        # pixels enter the mosaic; the rest is stable setup background.
        for slot in analyzer.slot_config:
            key = slot["id"]
            if key not in analyzer.reference_errors:
                reference = read_image(analyzer.config.resolve(slot["reference_image"]))
                selected = analyzer.masks[key] != 0
                self.seed[selected] = reference[selected]
        self.seed = cv2.GaussianBlur(self.seed, (5, 5), 0)
        signature = {"parameters": self.parameters, "interval": interval, "opencv": cv2.__version__,
                     "setup_hash": analyzer.setup_hash, "seed_hash": pixel_hash(self.seed),
                     "polygons": {s["id"]: polygon_signature(s["polygon"]) for s in analyzer.slot_config},
                     "references": analyzer.reference_hashes}
        self.signature = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        self.last_update = None
        self.last_seen = None
        self.update_count = 0
        self.reset_count = 0
        self.restabilizing = 0
        self.needs_reset = False
        self.raw_mask = self.clean_mask = None
        self._initialize()

    def _initialize(self):
        self.model = cv2.createBackgroundSubtractorMOG2(history=PARAMETERS["history"],
            varThreshold=PARAMETERS["var_threshold"], detectShadows=PARAMETERS["detect_shadows"])
        for i in range(PARAMETERS["bootstrap_applications"]):
            self.model.apply(self.seed, learningRate=1 if i == 0 else .1)

    def failure(self, checked, reason):
        result = deepcopy(checked)
        result.update({"method": "mog2_foreground", "processing_duration_ms": None,
                       "analysis_status": "unavailable", "error": reason, "model_signature": self.signature,
                       "model_update_count": self.update_count, "model_reset_count": self.reset_count})
        result["slots"] = [{"slot_id": s["id"], "state": "unknown", "foreground_ratio": None,
                            "shadow_ratio": None, "reason": reason} for s in self.analyzer.slot_config]
        result["summary"] = occupancy_summary(result["slots"], available=False)
        self.raw_mask = self.clean_mask = None
        return result

    def analyze(self, frame, position, checked, update=True):
        started = perf_counter()
        processing_at = utcnow().isoformat()
        if (checked["frame_id"] != frame.frame_id or checked["source_id"] != self.analyzer.config.data["source_id"]):
            raise ConfigError("Branch frame/camera identifiers must match before joining results.")
        if not math.isfinite(position) or position < 0:
            raise ConfigError("MOG2 position must be finite and nonnegative.")
        if self.last_seen is not None and position < self.last_seen:
            raise ConfigError("MOG2 frames must be chronological.")
        if update and self.last_update is not None and position <= self.last_update:
            raise ConfigError("MOG2 must update only once per chronological frame.")
        if checked.get("analysis_status") != "estimated" or checked.get("stale"):
            return self.failure(checked, checked.get("error") or "unusable_frame")
        if update and (self.needs_reset or (self.last_update is not None and position - self.last_update > self.parameters["gap_reset_seconds"])):
            self._initialize()
            self.reset_count += 1
            self.restabilizing = PARAMETERS["restabilization_samples"]
            self.needs_reset = False
        self.last_seen = position
        prepared = cv2.GaussianBlur(frame.image, (5, 5), 0)
        self.raw_mask = self.model.apply(prepared, learningRate=PARAMETERS["learning_rate"] if update else 0)
        self.clean_mask = clean_foreground(self.raw_mask, PARAMETERS["morphology_kernel"])
        if update:
            self.last_update = position
            self.update_count += 1
        slots = []
        calibrated_model = self.calibration.get("model_signature") == self.signature
        for slot in self.analyzer.slot_config:
            key = slot["id"]
            selected = self.analyzer.masks[key] != 0
            score = float(np.mean(self.clean_mask[selected] == 255))
            shadow = float(np.mean(self.raw_mask[selected] == 127))
            boundary = self.calibration.get("slots", {}).get(key, {})
            reason = self.analyzer.reference_errors.get(key)
            state = "unknown"
            if reason is None:
                if self.restabilizing:
                    state, reason = "uncertain", "mog2_restabilizing_after_gap"
                elif not calibrated_model or boundary.get("status") != "calibrated":
                    state, reason = "uncertain", "mog2_uncalibrated"
                else:
                    state = classify(score, boundary["vacant_max"], boundary["occupied_min"])
                    reason = "between_mog2_boundaries" if state == "uncertain" else None
            slots.append({"slot_id": key, "state": state, "foreground_ratio": score if key not in self.analyzer.reference_errors else None,
                          "shadow_ratio": shadow, "reason": reason})
        if update and self.restabilizing:
            self.restabilizing -= 1
        result = deepcopy(checked)
        result.update({"slots": slots, "summary": occupancy_summary(slots), "method": "mog2_foreground",
                       "preprocessing": "bgr-gaussian-5x5-shadow-exclusion-open-close-v1", "processing_started_at": processing_at,
                       "processed_at": utcnow().isoformat(), "processing_duration_ms": (perf_counter() - started) * 1000,
                       "model_signature": self.signature, "model_update_count": self.update_count,
                       "model_reset_count": self.reset_count, "learning_rate": PARAMETERS["learning_rate"] if update else 0,
                       "model_updated": update, "parameters": self.parameters})
        return result
