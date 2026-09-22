"""Optional OpenCV DNN vehicle evidence; never treat a missed detection as vacancy."""
from copy import deepcopy
import hashlib
import time

import cv2
import numpy as np
import requests

from .catalog import PROJECT_ROOT, DownloadError
from .config import polygon_signature
from .sources import utcnow, read_image, SourceError
from .vision import difference_score, occupancy_summary, preprocess, pixel_hash

REVISION = "bb17b6c3eef36d80be441ae8e5339be66e8e3b7a"
MODEL_FILES = {
    "deploy.prototxt": (44667, "2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608"),
    "mobilenet_iter_73000.caffemodel": (23306119, "52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7"),
}
MODEL_DIRECTORY = PROJECT_ROOT / "data/models/mobilenet-ssd"
VEHICLE_CLASSES = {6: "bus", 7: "car", 14: "motorbike"}
DETECTION_MIN = .25
OCCUPIED_MIN = .65


def prepare_model(emit=lambda *args: None, cancelled=lambda: False, directory=MODEL_DIRECTORY):
    directory.mkdir(parents=True, exist_ok=True)
    for name, (size, digest) in MODEL_FILES.items():
        target = directory / name
        if target.exists() and target.stat().st_size == size and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        emit("status", "Downloading the pinned OpenCV MobileNet-SSD vehicle model…")
        partial = target.with_suffix(target.suffix + ".part")
        start, count, hasher = time.monotonic(), 0, hashlib.sha256()
        try:
            url = f"https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/{REVISION}/{name}"
            with requests.get(url, stream=True, timeout=(5, 20)) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(262144):
                        if cancelled() or time.monotonic()-start > 120:
                            raise DownloadError("Vehicle model download stopped or timed out.")
                        count += len(chunk)
                        if count > size:
                            raise DownloadError("Vehicle model exceeds its pinned size.")
                        hasher.update(chunk)
                        handle.write(chunk)
            if count != size or hasher.hexdigest() != digest:
                raise DownloadError("Vehicle model integrity check failed.")
            partial.replace(target)
        except requests.RequestException:
            raise DownloadError("Vehicle model download unavailable; check the connection and retry.") from None
        finally:
            partial.unlink(missing_ok=True)
    return directory


def deduplicate(detections):
    """Remove overlapping tile duplicates, including fragments inside a full box."""
    kept = []
    for item in sorted(detections, key=lambda d: d["detector_score"], reverse=True):
        a = item["box"]
        area_a = (a[2]-a[0])*(a[3]-a[1])
        duplicate = False
        for other in kept:
            b = other["box"]
            area_b = (b[2]-b[0])*(b[3]-b[1])
            intersection = max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0, min(a[3],b[3])-max(a[1],b[1]))
            if intersection / (area_a+area_b-intersection) > .35 or intersection / min(area_a,area_b) > .8:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept


class VehicleDetector:
    def __init__(self, directory=MODEL_DIRECTORY):
        self.net = cv2.dnn.readNetFromCaffe(str(directory / "deploy.prototxt"), str(directory / "mobilenet_iter_73000.caffemodel"))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def detect(self, image):
        h, w = image.shape[:2]
        tw, th = round(w*.5625), round(h*5/9)
        tiles = [(0,0,w,h), (0,0,tw,th), (w-tw,0,tw,th), (0,h-th,tw,th), (w-tw,h-th,tw,th)]
        detections = []
        for x,y,cw,ch in tiles:
            self.net.setInput(cv2.dnn.blobFromImage(image[y:y+ch,x:x+cw], 1/127.5, (300,300), (127.5,)*3, swapRB=False))
            for row in self.net.forward()[0,0]:
                label, score = int(row[1]), float(row[2])
                if label not in VEHICLE_CLASSES or not np.isfinite(score) or score < DETECTION_MIN:
                    continue
                box = row[3:7]*[cw,ch,cw,ch]+[x,y,x,y]
                if not np.all(np.isfinite(box)):
                    continue
                x1,y1,x2,y2 = np.rint(box).astype(int)
                box = [int(np.clip(x1,0,w-1)), int(np.clip(y1,0,h-1)), int(np.clip(x2,0,w-1)), int(np.clip(y2,0,h-1))]
                if box[2]-box[0] < 8 or box[3]-box[1] < 8:
                    continue
                detections.append({"class": VEHICLE_CLASSES[label], "detector_score": score, "box": box})
        return deduplicate(detections)


def classify_bays(slots, detections, empty_scores, empty_limits):
    """Single-view geometric association. No cross-camera/time inference."""
    assigned = {s["id"]: [] for s in slots}
    touched = {s["id"]: False for s in slots}
    for detection in detections:
        x1,y1,x2,y2 = detection["box"]
        rectangle = np.float32([[x1,y1],[x2,y1],[x2,y2],[x1,y2]])
        anchor = ((x1+x2)/2, y1 + .82*(y2-y1))
        candidates = []
        for slot in slots:
            polygon = np.float32(slot["polygon"])
            overlap, _ = cv2.intersectConvexConvex(polygon, rectangle)
            cover = overlap / abs(cv2.contourArea(polygon))
            if cover > .15:
                touched[slot["id"]] = True
            distance = cv2.pointPolygonTest(polygon, anchor, True)
            if distance >= 3 and cover >= .2:
                candidates.append(slot["id"])
        if len(candidates) == 1 and detection["detector_score"] >= OCCUPIED_MIN:
            assigned[candidates[0]].append(detection)
    results = []
    for slot in slots:
        key = slot["id"]
        hits = assigned[key]
        score, limit = empty_scores.get(key), empty_limits.get(key)
        if slot.get("visibility") == "occluded":
            state, reason = "unknown", "bay_not_visible_in_this_view"
        elif hits:
            state, reason = "occupied", "vehicle_detected_inside_bay"
        elif touched[key]:
            state, reason = "uncertain", "vehicle_overlap_or_ambiguous_assignment"
        elif score is not None and limit is not None and score <= limit:
            state, reason = "vacant", "reviewed_empty_appearance_matches_and_no_vehicle_detected"
        else:
            state, reason = "uncertain", "no_vehicle_detection_is_not_proof_of_vacancy"
        results.append({"slot_id": key, "state": state, "reason": reason,
                        "detector_score": max((h["detector_score"] for h in hits), default=None),
                        "empty_difference": score, "empty_match_limit": limit,
                        "matched_vehicle_count": len(hits)})
    return results


def final_decision(reference, mog2, vehicle="unknown"):
    definite = {s for s in (reference,mog2,vehicle) if s in ("occupied","vacant")}
    if len(definite) > 1:
        return "uncertain", "methods_disagree"
    if reference == mog2 and reference in definite:
        return reference, "reference_and_mog2_agree"
    if vehicle in ("occupied","vacant"):
        return vehicle, "vehicle_and_visibility_evidence"
    if reference == mog2 == vehicle == "unknown":
        return "unknown", "no_usable_evidence"
    return "uncertain", "insufficient_or_incomplete_evidence"


class VehicleBranch:
    def __init__(self, analyzer, detector):
        self.analyzer, self.detector = analyzer, detector
        self.empty_limits = {}
        self.empty_banks = {}
        for s in analyzer.slot_config:
            c = s.get('vehicle_empty_match') or {}
            limit = c.get('max_difference')
            if (s['id'] in analyzer.references and c.get('vacant_examples', 0) >= 5 and c.get('reference_pixel_hash') == analyzer.reference_hashes.get(s['id'])
                    and c.get('setup_pixel_hash') == analyzer.setup_hash and c.get('polygon_signature') == polygon_signature(s['polygon'])
                    and type(limit) in (int,float) and 0 < limit <= .04):
                self.empty_limits[s['id']] = limit
                self.empty_banks[s['id']] = [analyzer.references[s['id']]]
                for name in s.get('vehicle_empty_reference_images', []):
                    try:
                        image = read_image(analyzer.config.resolve(name))
                    except (SourceError, OSError):
                        continue
                    if pixel_hash(image) in c.get('additional_reference_hashes', []):
                        self.empty_banks[s['id']].append(preprocess(image))

    def analyze(self, image, checked):
        start = time.perf_counter()
        started_at = utcnow().isoformat()
        result = deepcopy(checked)
        reason = None
        if checked.get("stale"):
            reason = checked.get("error") or "stale_frame"
        elif checked.get("analysis_status") != "estimated":
            reason = checked.get("error") or "frame_validation_failed"
        detections, scores = [], {}
        if image is None:
            reason = reason or "frame_unavailable"
        if self.detector is None:
            reason = reason or "vehicle_model_unavailable"
        if not reason:
            try:
                detections = self.detector.detect(image)
                gray = preprocess(image)
                scores = {key: min(difference_score(gray, ref, self.analyzer.masks[key]) for ref in refs)
                          for key,refs in self.empty_banks.items()}
            except (cv2.error, RuntimeError, OSError):
                reason = "vehicle_processing_failed"
        if reason:
            slots = [{"slot_id": s["id"], "state": "unknown", "reason": reason, "detector_score": None,
                      "empty_difference": None, "empty_match_limit": self.empty_limits.get(s["id"]),
                      "matched_vehicle_count": 0} for s in self.analyzer.slot_config]
        else:
            slots = classify_bays(self.analyzer.slot_config, detections, scores, self.empty_limits)
        result.update({"method": "opencv_mobilenet_ssd_plus_reviewed_empty_match", "slots": slots,
                       "summary": occupancy_summary(slots, available=not reason), "detections": detections,
                       "processing_started_at": started_at, "processed_at": utcnow().isoformat(), "processing_duration_ms": (time.perf_counter()-start)*1000,
                       "analysis_status": "unavailable" if reason else "estimated", "error": reason,
                       "model_revision": REVISION, "detector_threshold": OCCUPIED_MIN,
                       "score_note": "Detector score is not a calibrated parking occupancy probability.",
                       "evaluation_status": "experimental_not_independent_accuracy"})
        return result
