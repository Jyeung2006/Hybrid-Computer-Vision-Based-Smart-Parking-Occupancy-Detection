"""Reproducible recorded indoor demo. Public URL is deliberately built in.

This preset is for one visually inspected TEST REGION, not a marked parking bay.
It uses real video frames for reference/calibration, all from the same short clip.
It is an illustration of appearance comparison, not an independent evaluation.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
import time

import cv2
import numpy as np
import requests

from .config import Config, ConfigError, atomic_json, file_hash
from .evaluation import calibrate
from .output import Reporter, summary_text
from .sources import Frame, SourceError, iso, utcnow, write_image
from .vision import Analyzer

# No API key or user-provided URL is required. Pin the media bytes so another
# clip cannot silently reuse these polygons and manually reviewed labels.
VIDEO_URL = "https://videos.pexels.com/video-files/4707190/4707190-hd_1920_1080_24fps.mp4"
VIDEO_PAGE = "https://www.pexels.com/video/a-car-stopping-in-a-parking-lot-4707190/"
VIDEO_CREDIT = "Ricky Esquivel / Pexels"
VIDEO_LICENSE = "https://www.pexels.com/license/"
VIDEO_SHA256 = "95844b91d16bea399a23ac2c4349e754dbf5f78b42c08b362c4da31bc705e2d7"
VIDEO_BYTES = 16_132_001
CACHE_DIRECTORY = Path("data/video-demo/indoor-v1")
SIZE = (960, 540)
POLYGON = [[325, 175], [690, 175], [690, 310], [325, 310]]
LABEL_TIMES = {"vacant": [.5, 1, 1.5, 2, 2.5], "occupied": [14, 15, 16, 17, 18]}


def download_video(directory: Path) -> tuple[Path, str]:
    """Cache the public clip, bounding retries, bytes, inactivity and duration."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "indoor.mp4"
    if path.exists() and file_hash(path) == VIDEO_SHA256:
        return path, "verified_cache"
    partial = directory / "indoor.mp4.part"
    for attempt in range(2):
        started = time.monotonic()
        try:
            print(f"Downloading indoor sample (16.1 MB), attempt {attempt + 1}/2...", flush=True)
            with requests.get(VIDEO_URL, stream=True, timeout=(5, 10)) as response:
                response.raise_for_status()
                count = 0
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(64 * 1024):
                        count += len(chunk)
                        if count > VIDEO_BYTES or time.monotonic() - started > 90:
                            raise SourceError("demo_download_size_or_time_limit")
                        handle.write(chunk)
            if count != VIDEO_BYTES or file_hash(partial) != VIDEO_SHA256:
                raise SourceError("demo_video_changed_or_incomplete")
            partial.replace(path)
            atomic_json(directory / "download.json", {"url": VIDEO_URL, "page": VIDEO_PAGE,
                "credit": VIDEO_CREDIT, "license": VIDEO_LICENSE, "sha256": VIDEO_SHA256,
                "bytes": count, "downloaded_at": iso(utcnow()), "original_capture_time": None})
            return path, "downloaded_and_verified"
        except (requests.RequestException, SourceError):
            if attempt == 1:
                raise SourceError("demo_download_failed_check_internet_or_source_availability") from None
            time.sleep(.5)
        finally:
            partial.unlink(missing_ok=True)
    raise AssertionError("unreachable")


class RecordedVideo:
    def __init__(self, path: Path):
        self.capture = cv2.VideoCapture(str(path))
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        count = self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not self.capture.isOpened() or not math.isfinite(self.fps) or self.fps <= 0 or not math.isfinite(count) or count < 1:
            self.close()
            raise SourceError("demo_video_cannot_be_decoded")
        self.frame_count = int(count)
        self.duration = self.frame_count / self.fps
        self.original_size = (int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def frame_at(self, index: int):
        if not 0 <= index < self.frame_count:
            raise SourceError("demo_frame_out_of_range")
        # These are local, checksum-verified media bytes, not a network stream.
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = self.capture.read()
        if not ok or image is None:
            raise SourceError("demo_frame_decode_failed")
        if (image.shape[1], image.shape[0]) != self.original_size:
            raise SourceError("demo_video_resolution_changed")
        return cv2.resize(image, SIZE, interpolation=cv2.INTER_AREA)

    def at_seconds(self, seconds):
        return self.frame_at(round(seconds * self.fps))

    def close(self):
        self.capture.release()


def prepare_preset(video: RecordedVideo, directory: Path) -> Config:
    """Recreate only this generated demo preset; never alter live configuration."""
    setup = video.at_seconds(0)
    write_image(directory / "setup.png", setup)
    config_path = directory / "config.json"
    atomic_json(config_path, {"version": 1, "source_id": "pexels-indoor-4707190",
        "source": {"type": "recorded_video"}, "setup_image": "setup.png",
        "alignment": {"min_inliers": 12, "max_displacement_pixels": 8},
        "monitoring_scope": "test_regions", "generated_demo_preset": True,
        "note": "One test area, not a verified parking bay. Same-clip demonstration only.",
        "slots": [{"id": "ZONE01", "polygon": POLYGON, "reference_image": "setup.png",
                   "reference_review": "Region visibly empty at video time 0; inspected during demo preparation."}]})
    config = Config(config_path)
    rows, thumbs = [], []
    for label, seconds_list in LABEL_TIMES.items():
        for seconds in seconds_list:
            image = video.at_seconds(seconds)
            filename = f"calibration/{label}-{seconds:g}.png"
            write_image(directory / filename, image)
            rows.append({"frame_path": filename, "slot_id": "ZONE01", "label": label,
                         "session_id": "demo-same-clip"})
            preview = image.copy()
            cv2.polylines(preview, [np.int32(POLYGON)], True, (0, 220, 255), 2)
            preview = cv2.resize(preview, (480, 270))
            cv2.rectangle(preview, (0, 0), (480, 27), (15, 15, 15), -1)
            cv2.putText(preview, f"Preset label: {label} at {seconds:g}s", (8, 19), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
            thumbs.append(preview)
    manifest = directory / "calibration.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # Five empty examples in the left column; five occupied ones on the right.
    contact = np.vstack([np.hstack((thumbs[i], thumbs[i + 5])) for i in range(5)])
    write_image(directory / "review-labels.png", contact)
    decisions = calibrate(config, manifest)
    atomic_json(directory / "calibration-result.json", decisions)
    if decisions["ZONE01"]["status"] != "calibrated":
        raise ConfigError("Demo preset could not be calibrated; inspect its review-labels.png.")
    return config


def recorded_metadata(result, video, index):
    result.update({"input_mode": "recorded_video", "monitoring_scope": "test_regions",
        "video_position_seconds": index / video.fps, "video_frame_index": index,
        "video_duration_seconds": video.duration, "video_url": VIDEO_URL, "video_page": VIDEO_PAGE,
        "video_sha256": VIDEO_SHA256, "original_capture_time_known": False,
        "source_captured_at": None, "capture_time_status": "recording_capture_time_unknown",
        "frame_age_seconds": None, "freshness_basis": "local_recorded_frame_decode_only",
        "scope_note": "One test region. Percentages do not describe marked bays or whole-lot occupancy."})
    summary = result["summary"]
    summary["total_monitored_regions"] = summary["total_monitored_bays"]
    summary["total_monitored_bays"] = 0
    return result


def run_demo(args):
    if not math.isfinite(args.step) or not .1 <= args.step <= 10 or args.frames < 0:
        raise ConfigError("Use --step between 0.1 and 10 seconds, and --frames zero or positive.")
    output = (args.out or Path("runs/demo-indoor") / utcnow().strftime("%Y%m%dT%H%M%S_%fZ")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Do not append a new playback to an older run's CSV/video files.
    if any(output.iterdir()):
        raise ConfigError("Demo output directory must be empty; omit --out for a new timestamped run.")
    video = writer = None
    processed, latencies, states, failures = 0, [], {}, 0
    status = "failed"
    try:
        path, retrieval = download_video(CACHE_DIRECTORY.resolve())
        video = RecordedVideo(path)
        print(f"RECORDED indoor demo: {video.duration:.2f}s. One test region; NOT whole-lot occupancy.")
        print("Preparing reviewed demo reference and five examples of each state...", flush=True)
        config = prepare_preset(video, CACHE_DIRECTORY.resolve())
        analyzer = Analyzer(config)
        reporter = Reporter(output, config.data["slots"])
        stride = max(1, round(args.step * video.fps))
        interval = stride / video.fps
        indices = range(0, video.frame_count, stride)
        status = "complete"
        if not args.headless:
            cv2.namedWindow("Indoor parking demo - Q to stop", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Indoor parking demo - Q to stop", 1000, 710)
        for index in indices:
            if args.frames and processed >= args.frames:
                status = "sample_limit_reached"
                break
            started = time.monotonic()
            image = None
            try:
                image = video.frame_at(index)
                decode_ms = (time.monotonic() - started) * 1000
                result = analyzer.analyze(Frame(image, utcnow(), frame_id=f"pexels-4707190-f{index:06d}"))
                result["retrieval_duration_ms"] = decode_ms
            except SourceError as exc:
                result = analyzer.failure(str(exc))
                status = "failed"
            recorded_metadata(result, video, index)
            canvas = reporter.write(result, image if result.get("alignment") and result["alignment"]["ok"] else None)
            # Keep a consistent encoded frame size even for unavailable frames.
            canvas = cv2.resize(canvas, (1000, 710))
            if writer is None:
                writer = cv2.VideoWriter(str(output / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 1 / interval, (1000, 710))
                if not writer.isOpened():
                    raise SourceError("annotated_video_writer_unavailable")
            writer.write(canvas)
            processed += 1
            failures += int(result["analysis_status"] == "unavailable")
            if result["processing_duration_ms"] is not None:
                latencies.append(result["processing_duration_ms"])
            state = result["slots"][0]["state"]
            states[state] = states.get(state, 0) + 1
            print(f'Video {index / video.fps:5.2f}s | {summary_text(result)}', flush=True)
            if not args.headless:
                cv2.imshow("Indoor parking demo - Q to stop", canvas)
                while True:
                    key = cv2.waitKey(20) & 0xFF
                    if key in (ord("q"), 27) or cv2.getWindowProperty("Indoor parking demo - Q to stop", cv2.WND_PROP_VISIBLE) < 1:
                        status = "stopped_by_user"
                        break
                    if time.monotonic() - started >= interval:
                        break
            if status in ("stopped_by_user", "failed"):
                break
        atomic_json(output / "run.json", {"status": status, "input_mode": "recorded_video",
            "video_url": VIDEO_URL, "video_page": VIDEO_PAGE, "credit": VIDEO_CREDIT,
            "video_sha256": VIDEO_SHA256, "retrieval": retrieval, "processed_frames": processed,
            "video_duration_seconds": video.duration, "sample_interval_seconds": interval,
            "states": states, "unavailable_frames": failures,
            "processing_latency_ms": {"median": float(np.median(latencies)), "p95": float(np.percentile(latencies, 95))} if latencies else None,
            "independent_evaluation": False, "live_camera_tested": False,
            "note": "Same-clip calibration and playback for one test region; accuracy is not measured here."})
        print(f"Results: {output}\nOpen annotated.mp4 to replay, latest.png for the final image, or summary.csv for the history.")
        return 2 if status == "failed" or failures else 0
    except (SourceError, ConfigError, OSError, cv2.error):
        atomic_json(output / "run.json", {"status": "failed", "input_mode": "recorded_video",
            "current_occupancy_available": False, "processed_frames": processed,
            "note": "The demo did not complete. Earlier files in this run are timestamped history only."})
        raise
    finally:
        if writer is not None:
            writer.release()
        if video is not None:
            video.close()
        cv2.destroyAllWindows()
