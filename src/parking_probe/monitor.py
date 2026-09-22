"""Recorded camera replay through the existing OpenCV detector and reporter.

The GUI runs this in one worker thread. No camera URL, keys, or input prompts
are needed. A source recording's encode date is never treated as capture time.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from .catalog import CLIPS, PROJECT_ROOT, fetch_clip
from .config import Config, ConfigError, atomic_json
from .display_model import sample_indices, replay_delay
from .evaluation import calibrate
from .output import COLORS, Reporter
from .sources import Frame, SourceError, utcnow, validate_image, write_image
from .vision import Analyzer

RECIPE = PROJECT_ROOT / "presets" / "chad-camera-1.json"


class Recording:
    def __init__(self, path, source_resolution=(1920, 1080), analysis_resolution=(1280, 720)):
        self.stabilizer = None
        self.registration = None
        self.source_resolution = tuple(source_resolution)
        self.analysis_resolution = tuple(analysis_resolution)
        self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            self.capture.release()
            raise SourceError("recorded_video_open_failed")
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        try:
            next(sample_indices(self.count, self.fps, 3))
        except (ValueError, StopIteration):
            self.close()
            raise SourceError("invalid_recorded_video_timing") from None
        self.duration = self.count / self.fps

    def read(self, index):
        if not 0 <= index < self.count:
            raise SourceError("recorded_frame_out_of_bounds")
        if not self.capture.set(cv2.CAP_PROP_POS_FRAMES, index):
            raise SourceError("recorded_video_seek_failed")
        ok, image = self.capture.read()
        if not ok:
            raise SourceError("recorded_video_decode_failed")
        validate_image(image)
        # Validate the original resolution before resizing: a changed source
        # must not be silently reshaped to fit old parking polygons.
        if (image.shape[1], image.shape[0]) != self.source_resolution:
            raise SourceError("resolution_changed")
        image = cv2.resize(image, self.analysis_resolution, interpolation=cv2.INTER_AREA)
        if self.stabilizer:
            image, self.registration = self.stabilizer.apply(image)
        return image

    def close(self):
        self.capture.release()


def recording_for_recipe(path, recipe):
    recording = Recording(path, recipe['source_resolution'], recipe['analysis_resolution'])
    if recipe.get('stabilization'):
        from .registration import FrameRegistration
        try:
            recording.stabilizer = FrameRegistration(recording.read(0), recipe['stabilization'])
        except Exception:
            recording.close()
            raise
    return recording


def prepare_preset(emit, stop, recipe_path=None, clips=None, fetcher=None, cache_root=None):
    recipe_path = Path(recipe_path) if recipe_path else RECIPE
    clips = CLIPS if clips is None else clips
    fetcher = fetcher or fetch_clip
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    required = {recipe["setup"][0]}
    for slot in recipe["slots"]:
        if slot.get("reference"):
            required.add(slot["reference"][0])
        required.update(item[0] for item in slot.get('vehicle_empty_references', []))
        required.update(slot[state]["clip"] for state in ("vacant", "occupied"))
        for state in ("vacant", "occupied"):
            required.update(group["clip"] for group in slot.get("additional_samples", {}).get(state, []))
    paths = {}
    for clip in clips:
        if clip.id in required:
            if stop.is_set():
                raise SourceError("Run stopped during preparation.")
            paths[clip.id] = fetcher(clip, lambda message: emit("status", message), stop.is_set)
    # Version by recipe, source digests, and decoder version. Reuse previous
    # references only with exactly these inputs; never overwrite reviewed
    # references or recalibrate as a response to an analysis failure.
    signature = hashlib.sha256(recipe_path.read_bytes() + cv2.__version__.encode() +
                               "".join(c.sha256 for c in clips if c.id in required).encode()).hexdigest()[:16]
    directory = (Path(cache_root) if cache_root else PROJECT_ROOT / "data/chad") / f"preset-{signature}"
    config_path = directory / "config.json"
    if (directory / "ready.json").exists():
        return Config(config_path), recipe, paths
    directory.mkdir(parents=True, exist_ok=True)
    emit("status", f"Preparing {len(recipe['slots'])} bays and reviewed empty/occupied examples...")
    recordings, extracted = {}, {}

    def extract(clip_id, second):
        if stop.is_set():
            raise SourceError("Run stopped during preparation.")
        key = clip_id, second
        if key not in extracted:
            if clip_id not in recordings:
                recordings[clip_id] = recording_for_recipe(paths[clip_id], recipe)
            recording = recordings[clip_id]
            index = round(second * recording.fps)
            path = directory / "frames" / f"{clip_id}-{index:06d}.png"
            write_image(path, recording.read(index))
            extracted[key] = path.relative_to(directory).as_posix()
        return extracted[key]

    try:
        data = {"version": 1, "source_id": recipe.get("source_id", "chad-camera-1"), "source": {"type": "recorded_video"},
                "setup_image": extract(*recipe["setup"]), "interval_seconds": 3,
                "stale_after_seconds": 15, "alignment": {"min_inliers": 12, "max_displacement_pixels": 8}, "slots": []}
        labels = []
        for slot in recipe["slots"]:
            data["slots"].append({"id": slot["id"], "polygon": slot["polygon"],
                                  "reference_image": extract(*slot["reference"]) if slot.get("reference") else None})
            if slot.get('vehicle_empty_references'):
                data['slots'][-1]['vehicle_empty_reference_images'] = [extract(*item) for item in slot['vehicle_empty_references']]
            for state in ("vacant", "occupied"):
                groups = [slot[state], *slot.get("additional_samples", {}).get(state, [])]
                for examples in groups:
                    for second in examples["seconds"]:
                        labels.append({"frame_path": extract(examples["clip"], second), "slot_id": slot["id"],
                                       "label": state, "session_id": examples["clip"]})
        atomic_json(config_path, data)
        manifest = directory / "calibration-labels.csv"
        with manifest.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("frame_path", "slot_id", "label", "session_id"))
            writer.writeheader()
            writer.writerows(labels)
        config = Config(config_path)
        try:
            calibration = calibrate(config, manifest)
        except ConfigError as exc:
            # Keep the guard. Failed alignment or invalid samples leave these
            # bays unknown rather than assigning convenient thresholds.
            calibration = {"status": "uncalibrated", "reason": str(exc)}
            emit("status", "Calibration could not be validated. Bays will remain unknown; see calibration-report.json.")
        atomic_json(directory / "calibration-report.json", calibration)
        atomic_json(directory / "ready.json", {"recipe_signature": signature,
                    "created_at": utcnow().isoformat(), "source_clip_ids": sorted(required),
                    "evaluation_status": "demonstration_only_not_independent_accuracy"})
        return config, recipe, paths
    finally:
        for recording in recordings.values():
            recording.close()


def camera_preview(image, result, slots):
    if image is None:
        return None
    canvas = image.copy()
    states = {s["slot_id"]: s for s in result["slots"]}
    for slot in slots:
        points = np.int32(slot["polygon"])
        color = COLORS[states[slot["id"]]["state"]]
        cv2.polylines(canvas, [points], True, color, 3)
        x, y = points.mean(axis=0).astype(int)
        # Put readable IDs beneath the far-row bays, keeping the cars visible.
        y = int(points[:, 1].max()) + 27
        cv2.rectangle(canvas, (x - 27, y - 23), (x + 31, y + 6), (24, 40, 59), -1)
        cv2.putText(canvas, slot["id"], (x - 23, y), cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2, cv2.LINE_AA)
    canvas = cv2.resize(canvas, (840, 472), interpolation=cv2.INTER_AREA)
    ok, png = cv2.imencode(".png", canvas)
    if not ok:
        raise SourceError("preview_encoding_failed")
    return png.tobytes()


def run_recording(clip, interval, stop, emit, fast=False, frame_limit=0):
    if frame_limit < 0:
        raise ValueError("Frame limit must be zero (whole video) or positive.")
    # Check before any download.
    next(sample_indices(1000, 30, interval))
    config, recipe, paths = prepare_preset(emit, stop)
    if stop.is_set():
        emit("done", "Stopped.")
        return 0
    if clip.id not in paths:
        paths[clip.id] = fetch_clip(clip, lambda message: emit("status", message), stop.is_set)
    analyzer = Analyzer(config)
    out = PROJECT_ROOT / "runs" / "chad" / clip.id / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    reporter = Reporter(out, config.data["slots"])
    recording = None
    begun = time.monotonic()
    previous_published = None
    sampled, skipped = 0, 0
    durations = []
    status = "complete"
    position, index = 0.0, 0
    duration = 0.0

    def metadata(result):
        result.update({"input_mode": "recorded_video", "monitoring_scope": "monitored_bays",
                       "video_id": clip.id, "video_filename": clip.member, "video_sha256": clip.sha256,
                       "video_position_seconds": position, "video_frame_index": index,
                       "video_duration_seconds": duration, "original_capture_time_known": False,
                       "freshness_basis": "local_recorded_frame_decode", "update_interval_seconds": interval,
                       "skipped_replay_samples": skipped, "evaluation_status": "demonstration_not_held_out"})
        return result

    try:
        recording = Recording(paths[clip.id], recipe["source_resolution"], recipe["analysis_resolution"])
        duration = recording.duration
        for number, index in sample_indices(recording.count, recording.fps, interval):
            position = index / recording.fps
            if stop.is_set():
                status = "stopped"
                break
            if not fast:
                wait = replay_delay(begun, number, interval, time.monotonic(), previous_published)
                if wait is None:
                    skipped += 1
                    continue
                if stop.wait(wait):
                    status = "stopped"
                    break
            decoded_at = time.perf_counter()
            image = recording.read(index)
            decode_ms = (time.perf_counter() - decoded_at) * 1000
            result = metadata(analyzer.analyze(Frame(image, utcnow(), frame_id=f"{clip.id}-{index:06d}")))
            result["retrieval_duration_ms"] = decode_ms
            png = camera_preview(image, result, config.data["slots"])
            result["replay_elapsed_seconds"] = time.monotonic() - begun
            reporter.write(result, image)
            emit("observation", (result, png))
            previous_published = time.monotonic()
            sampled += 1
            durations.append(result["processing_duration_ms"])
            if frame_limit and sampled >= frame_limit:
                status = "frame_limit"
                break
        emit("done", f"{status.replace('_', ' ').capitalize()} | {sampled} observations saved in {out}. Recorded history only.")
        return 0
    except KeyboardInterrupt:
        status = "stopped"
        raise
    except Exception:
        status = "failed"
        result = metadata(analyzer.failure("recorded_video_processing_failed"))
        reporter.write(result)
        emit("observation", (result, None))
        raise
    finally:
        if recording:
            recording.close()
        atomic_json(out / "run.json", {"video_id": clip.id, "video_filename": clip.member,
                    "status": status, "sampled_frames": sampled, "skipped_samples": skipped,
                    "update_interval_seconds": interval, "wall_clock_waits_enabled": not fast,
                    "elapsed_seconds": time.monotonic() - begun,
                    "analysis_latency_ms": {"median": float(np.median(durations)) if durations else None,
                                            "p95": float(np.percentile(durations, 95)) if durations else None},
                    "preset_path": str(config.path), "monitoring_scope": "three_configured_bays",
                    "independent_accuracy_measured": False, "original_capture_time_known": False})
