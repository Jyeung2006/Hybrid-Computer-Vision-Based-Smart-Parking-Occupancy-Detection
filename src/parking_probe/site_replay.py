"""Synchronized local recordings: per-view OpenCV, physical bays, 10s reports."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

import cv2

from .bay_fusion import TimeWindow, fuse_views
from .catalog import PROJECT_ROOT, fetch_clip
from .config import Config, ConfigError, atomic_json
from . import monitor
from .output import Reporter, rotate
from .sources import Frame, SourceError, utcnow
from .vision import Analyzer


def validate_site(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ConfigError("Site configuration version must be 1.")
    Config.validate_id(data.get("site_id"))
    bays, cameras = data.get("bay_ids"), data.get("cameras")
    if not isinstance(bays, list) or not bays or not isinstance(cameras, list) or not cameras:
        raise ConfigError("A site needs bay_ids and cameras.")
    for bay in bays:
        Config.validate_id(bay)
    if len(set(bays)) != len(bays):
        raise ConfigError("Physical bay IDs must be unique.")
    camera_ids, seen_bays = set(), set()
    for camera in cameras:
        if not isinstance(camera, dict):
            raise ConfigError("Each camera must be an object.")
        camera_id = camera.get("camera_id")
        Config.validate_id(camera_id)
        if camera_id in camera_ids:
            raise ConfigError("Each physical camera may appear only once in a synchronized site.")
        camera_ids.add(camera_id)
        mapping = camera.get("slot_map")
        if not isinstance(mapping, dict) or not mapping:
            raise ConfigError("Each camera needs a local-slot to physical-bay slot_map.")
        for local, bay in mapping.items():
            Config.validate_id(local)
            Config.validate_id(bay)
            if bay not in bays:
                raise ConfigError("slot_map references an unregistered physical bay.")
        if len(set(mapping.values())) != len(mapping):
            raise ConfigError("A camera cannot count two polygons as the same physical bay.")
        seen_bays.update(mapping.values())
        offset = camera.get("video_offset_seconds", 0)
        if type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0:
            raise ConfigError("video_offset_seconds must be finite and nonnegative.")
        for key in ("source_resolution", "analysis_resolution"):
            size = camera.get(key)
            if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
                raise ConfigError(f"{key} must be [width, height] with positive integers.")
    if seen_bays != set(bays):
        raise ConfigError("Every physical bay must have at least one mapped view.")
    if len(cameras) > 1:
        sync = data.get("synchronization", {})
        if not isinstance(sync, dict) or sync.get("verified") is not True or not str(sync.get("note", "")).strip():
            raise ConfigError("Multiple cameras require verified synchronization and a note explaining the common recording period/offsets.")
        if data.get("mapping_verified") is not True:
            raise ConfigError("Inspect the views and verify that mapped polygons identify the same physical bays.")
    return data


def load_site(path):
    path = Path(path).resolve()
    try:
        data = validate_site(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        raise ConfigError("Cannot read site configuration JSON.") from None
    paths = set()
    for camera in data["cameras"]:
        for key in ("config", "video_path"):
            if not isinstance(camera.get(key), str) or not camera[key]:
                raise ConfigError(f"Camera {key} must be a local file path.")
            camera[key] = str((path.parent / camera[key]).resolve())
        if camera["video_path"] in paths:
            raise ConfigError("A recording cannot be supplied as two different cameras.")
        paths.add(camera["video_path"])
    return data


def default_site(clip, emit, stop):
    config, recipe, paths = monitor.prepare_preset(emit, stop)
    if clip.id not in paths:
        paths[clip.id] = fetch_clip(clip, lambda message: emit("status", message), stop.is_set)
    return validate_site({"version": 1, "site_id": "CHAD-carpark", "mapping_verified": True,
        "bay_ids": ["CHAD-P001", "CHAD-P002", "CHAD-P003"],
        "synchronization": {"verified": False, "note": "Single physical camera; four clips are separate periods."},
        "cameras": [{"camera_id": "chad-camera-1", "config": str(config.path),
                     "video_path": str(paths[clip.id]), "video_id": clip.id, "video_sha256": clip.sha256,
                     "video_offset_seconds": 0, "source_resolution": recipe["source_resolution"],
                     "analysis_resolution": recipe["analysis_resolution"],
                     "slot_map": {"B01": "CHAD-P001", "B02": "CHAD-P002", "B03": "CHAD-P003"}}]})


class SiteReporter:
    def __init__(self, directory, site):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_json(self.directory / "site.json", site)

    def append(self, name, data):
        path = self.directory / name
        rotate(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(data, allow_nan=False) + "\n")

    def csv(self, name, rows):
        if not rows:
            return
        path = self.directory / name
        rotate(path)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            if new:
                writer.writeheader()
            writer.writerows(rows)

    def observation(self, result):
        atomic_json(self.directory / "latest.json", result)
        self.append("history.jsonl", result)

    def window(self, result):
        atomic_json(self.directory / "latest-window.json", result)
        self.append("windows.jsonl", result)
        common = {k: result[k] for k in ("site_id", "generated_at", "window_start_seconds", "window_end_seconds",
            "window_duration_seconds", "partial_window", "sample_count", "rate_basis", "state_basis", "late_by_seconds")}
        self.csv("summary.csv", [{**common, **result["summary"]}])
        self.csv("bays.csv", [{**common, **{k: b[k] for k in ("bay_id", "state", "reason", "usable_views", "expected_views",
            "degraded", "occupied_time_pct", "occupied_time_min_pct", "occupied_time_max_pct", "classified_time_pct")},
            **{f"{state}_seconds": value for state, value in b["state_seconds"].items()}} for b in result["bays"]])


def run_site(site, interval, stop, emit, fast=False, frame_limit=0, out=None):
    validate_site(site)
    if type(interval) not in (int, float) or not math.isfinite(interval) or interval <= 0 or frame_limit < 0:
        raise ConfigError("Sample interval must be positive and frame limit nonnegative.")
    cameras = site["cameras"]
    out = Path(out) if out else PROJECT_ROOT / "runs" / "sites" / site["site_id"] / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    reporter = SiteReporter(out, site)
    emit("status", f"Results: {out}")
    opened, observations, runtimes = [], {}, {}
    initial = fuse_views(site["bay_ids"], cameras, {}, 0)
    window = TimeWindow(initial)
    sampled, skipped, window_count, errors = 0, 0, 0, 0
    position = 0.0
    status = "preparing"
    begun = time.monotonic()

    def decorate(fused):
        fused.update({"site_id": site["site_id"], "processed_at": utcnow().isoformat(),
                      "input_mode": "recorded_video", "source_captured_at": None,
                      "original_capture_time_known": False, "historical_recording": True,
                      "fusion_policy": "agree_or_uncertain_with_missing_view_fallback",
                      "evaluation_status": "demonstration_not_independent_accuracy",
                      "replay_elapsed_seconds": time.monotonic() - begun})
        return fused

    def publish_window(when, partial=False):
        nonlocal window_count
        result = window.close(when, partial)
        if result is None:
            return
        now = utcnow()
        result.update({"site_id": site["site_id"], "generated_at": now.isoformat(),
                       "display_time": now.astimezone().strftime("%H:%M:%S"),
                       "late_by_seconds": max(0, time.monotonic() - begun - when) if not fast else None,
                       "input_mode": "recorded_video", "source_captured_at": None,
                       "wall_clock_waits_enabled": not fast})
        reporter.window(result)
        emit("window", result)
        window_count += 1

    def view_result(camera, runtime, when, failure=None):
        nonlocal errors
        recording, analyzer = runtime["recording"], runtime["analyzer"]
        local_time = when + camera.get("video_offset_seconds", 0)
        index = round(local_time * recording.fps) if recording else None
        image = None
        start = time.perf_counter()
        try:
            if failure:
                result = analyzer.failure(failure)
            elif runtime["open_error"]:
                result = analyzer.failure(runtime["open_error"])
            elif when >= runtime["end"]:
                result = analyzer.failure("recording_ended")
            else:
                # Near EOF rounding can select the first nonexistent frame.
                index = min(index, recording.count - 1)
                image = recording.read(index)
                decoded = time.perf_counter()
                result = analyzer.analyze(Frame(image, utcnow(), frame_id=f"{camera['camera_id']}-{index:08d}"))
                result["retrieval_duration_ms"] = (decoded - start) * 1000
        except SourceError as exc:
            # Recording emits bounded reason codes, including resolution_changed.
            # Preserve those so a moved/resized view can be reconfigured.
            result = analyzer.failure(str(exc))
            image = None
            errors += 1
        except (RuntimeError, OSError, cv2.error):
            result = analyzer.failure("recorded_video_decode_failed")
            image = None
            errors += 1
        result.update({"camera_id": camera["camera_id"], "input_mode": "recorded_video",
                       "monitoring_scope": "monitored_bays", "sample_time_seconds": when,
                       "frame_time_seconds": index / recording.fps - camera.get("video_offset_seconds", 0) if recording else None,
                       "video_position_seconds": index / recording.fps if recording else local_time,
                       "video_frame_index": index, "video_duration_seconds": recording.duration if recording else 0,
                       "video_filename": Path(camera["video_path"]).name, "video_id": camera.get("video_id"),
                       "video_sha256": camera.get("video_sha256"), "original_capture_time_known": False,
                       "freshness_basis": "local_recorded_frame_decode", "update_interval_seconds": interval,
                       "replay_elapsed_seconds": time.monotonic() - begun})
        for slot in result["slots"]:
            slot["bay_id"] = camera["slot_map"][slot["slot_id"]]
        runtime["reporter"].write(result, image)
        return result

    try:
        for camera in cameras:
            config = Config(camera["config"])
            if config.data["source_id"] != camera["camera_id"]:
                raise ConfigError("Camera ID must match its calibration configuration source_id.")
            if set(camera["slot_map"]) != {s["id"] for s in config.data["slots"]}:
                raise ConfigError("slot_map must map each configured polygon exactly once.")
            analyzer = Analyzer(config)
            if camera["analysis_resolution"] != [analyzer.width, analyzer.height]:
                raise ConfigError("analysis_resolution must match the calibrated setup view.")
            recording, open_error, end = None, None, 0.0
            try:
                recording = monitor.Recording(camera["video_path"], camera["source_resolution"], camera["analysis_resolution"])
                opened.append(recording)
                if interval * recording.fps < 1:
                    raise ConfigError("Sample interval cannot be shorter than a video frame.")
                end = recording.duration - camera.get("video_offset_seconds", 0)
                if end <= 0:
                    raise ConfigError("Camera offset is beyond the end of its recording.")
            except SourceError:
                open_error = "recorded_video_open_failed"
                errors += 1
            runtimes[camera["camera_id"]] = {"recording": recording, "analyzer": analyzer, "open_error": open_error,
                "end": end, "reporter": Reporter(out / "cameras" / camera["camera_id"], config.data["slots"])}
        duration = max(r["end"] for r in runtimes.values())
        if duration <= 0:
            reporter.observation(decorate(initial))
            raise SourceError("No usable recordings. Check the local video paths.")
        begun = time.monotonic()
        status = "complete"
        next_sample, next_window = 0.0, 10.0
        camera_ends = sorted({r["end"] for r in runtimes.values() if r["end"] > 0})
        while position < duration:
            when = min(next_sample, next_window, camera_ends[0], duration)
            if stop.is_set() or (not fast and stop.wait(max(0, begun + when - time.monotonic()))):
                status = "stopped"
                break
            position = when
            # Close [start, t) before a new observation or an EOF at t.
            if abs(when - next_window) < 1e-8:
                publish_window(when)
                next_window += 10
            if when >= duration:
                if when > window.start:
                    publish_window(when, partial=True)
                break
            ended = camera_ends and abs(when - camera_ends[0]) < 1e-8
            if ended:
                camera_ends.pop(0)
                for camera in cameras:
                    runtime = runtimes[camera["camera_id"]]
                    if runtime["end"] == when:
                        observations[camera["camera_id"]] = view_result(camera, runtime, when, "recording_ended")
            is_sample = abs(when - next_sample) < 1e-8
            if is_sample:
                overdue = not fast and time.monotonic() - begun - when >= interval
                skipped += int(overdue)
                for camera in cameras:
                    observations[camera["camera_id"]] = view_result(camera, runtimes[camera["camera_id"]], when,
                                                                    "replay_sample_missed" if overdue else None)
                sampled += 1
                next_sample = sampled * interval
            fused = decorate(fuse_views(site["bay_ids"], cameras, observations, when, max_age=interval * 1.5))
            window.update(when, fused, sample=is_sample)
            reporter.observation(fused)
            if is_sample:
                emit("observation", fused)
            if frame_limit and sampled >= frame_limit:
                status = "frame_limit"
                publish_window(when, partial=True)
                break
        if status == "stopped":
            publish_window(position, partial=True)
        status = "complete_with_errors" if status == "complete" and errors else status
        emit("done", f"{status.replace('_', ' ').capitalize()} | {sampled} samples, {window_count} summaries. Saved in {out}")
        return 0 if not errors else 2
    except KeyboardInterrupt:
        status = "stopped"
        publish_window(position, partial=True)
        raise
    except Exception:
        status = "failed"
        raise
    finally:
        for recording in opened:
            recording.close()
        # Ended/stopped footage is history, never a currently operating camera.
        final = decorate(fuse_views(site["bay_ids"], cameras, {}, position))
        final.update({"run_status": status, "run_active": False, "current_occupancy_available": False})
        reporter.observation(final)
        atomic_json(out / "run.json", {"status": status, "sampled_ticks": sampled, "skipped_ticks": skipped,
            "window_count": window_count, "camera_errors": errors, "sample_interval_seconds": interval,
            "summary_interval_seconds": 10, "wall_clock_waits_enabled": not fast,
            "elapsed_seconds": time.monotonic() - begun, "site_id": site["site_id"],
            "physical_bay_count": len(site["bay_ids"]), "camera_count": len(cameras),
            "independent_accuracy_measured": False, "original_capture_time_known": False})
