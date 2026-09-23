"""Basic OpenCV import, real-video decode, grayscale/blur and playback check.

Run from main.py. No dashboard, parking calibration or occupancy calculation.
Only the already-selected public video is used; no system settings are changed.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time


def run():
    parser = argparse.ArgumentParser(description="Check OpenCV itself using the supplied parking video.")
    parser.add_argument("--headless", action="store_true", help="Check decoding and processing without a window")
    parser.add_argument("--frames", type=int, default=0, help="Stop after this many frames; 0 means the whole clip")
    args = parser.parse_args()
    if args.frames < 0:
        parser.error("--frames must be zero or positive")
    root = Path(__file__).resolve().parents[2]
    directory = root / "runs" / "opencv-check"
    directory.mkdir(parents=True, exist_ok=True)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "not_started",
              "stage": "opencv_import", "python_version": sys.version.split()[0],
              "opencv_version": None, "decoded_frames": 0, "processed_frames": 0,
              "preview_requested": not args.headless, "preview_frames": 0,
              "saved_grayscale_image": None, "occupancy_tested": False, "error": None}
    capture = None
    cv2 = None
    exit_code = 0
    print("OPENCV BASIC CHECK\n", flush=True)
    print(f"Python {report['python_version']} | No parking dashboard or occupancy calculation", flush=True)
    try:
        print("[1/4] Loading the installed OpenCV library...", flush=True)
        import cv2
        report["opencv_version"] = cv2.__version__
        print(f"      PASS - OpenCV {cv2.__version__} loaded", flush=True)

        report["stage"] = "video_open"
        print("[2/4] Opening the supplied parking video...", flush=True)
        from .catalog import CLIPS, fetch_clip
        path = fetch_clip(CLIPS[0], lambda message: print("      " + message, flush=True))
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise RuntimeError("OpenCV loaded, but could not open the video.")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise RuntimeError("The video has invalid frame-rate metadata.")
        report["video_file"] = path.name
        report["fps"] = fps
        expected_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"      PASS - {path.name}, {fps:.3f} fps", flush=True)

        print("[3/4] Decoding frames and applying grayscale + Gaussian blur...", flush=True)
        begun = time.monotonic()
        next_print = 0.0
        while True:
            report["stage"] = "frame_decode"
            ok, frame = capture.read()
            if not ok:
                if not report["decoded_frames"] or (expected_frames > 0 and report["decoded_frames"] < expected_frames):
                    raise RuntimeError("OpenCV could not decode an expected video frame.")
                report["status"] = "passed"
                break
            report["decoded_frames"] += 1
            if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
                raise RuntimeError("OpenCV returned an invalid color frame.")
            report["stage"] = "image_processing"
            started = time.perf_counter()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            process_ms = (time.perf_counter() - started) * 1000
            report["processed_frames"] += 1
            video_seconds = (report["decoded_frames"] - 1) / fps
            if report["decoded_frames"] == 1:
                report["width"], report["height"] = frame.shape[1], frame.shape[0]
                ok, encoded = cv2.imencode(".png", blurred)
                if not ok:
                    raise RuntimeError("OpenCV could not encode the processed image.")
                output = directory / "first-frame-grayscale.png"
                output.write_bytes(encoded.tobytes())
                report["saved_grayscale_image"] = str(output)
                print(f"      PASS - {frame.shape[1]} x {frame.shape[0]} frame decoded and processed", flush=True)
                print("[4/4] " + ("Continuing decode check; preview deliberately disabled." if args.headless else
                                     "Playing in an OpenCV video window. Press Q or Esc to stop."), flush=True)

            elapsed = time.monotonic() - begun
            if elapsed >= next_print:
                now = datetime.now().astimezone().strftime("%H:%M:%S")
                print(f"{now} | video {video_seconds:5.1f}s | frame {report['decoded_frames']:4d} | "
                      f"{frame.shape[1]}x{frame.shape[0]} | grayscale/blur {process_ms:.2f} ms | OK", flush=True)
                next_print = elapsed + 3
            if not args.headless:
                report["stage"] = "opencv_preview"
                preview = cv2.resize(frame, (960, 540))
                cv2.putText(preview, f"OpenCV check | frame {report['decoded_frames']} | {video_seconds:.1f}s | Q to stop",
                            (15, 525), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("OpenCV video check - Q or Esc to stop", preview)
                report["preview_frames"] += 1
                deadline = begun + report["decoded_frames"] / fps
                delay_ms = max(1, min(1000, round((deadline - time.monotonic()) * 1000)))
                if (cv2.waitKey(delay_ms) & 0xff) in (ord("q"), 27) or cv2.getWindowProperty("OpenCV video check - Q or Esc to stop", cv2.WND_PROP_VISIBLE) < 1:
                    report["status"] = "stopped_after_successful_frames"
                    break
            if args.frames and report["decoded_frames"] >= args.frames:
                report["status"] = "passed_requested_frames"
                break
        report["stage"] = "finished"
        print(f"\nOpenCV decoded and processed {report['processed_frames']} frames. Occupancy was not tested.", flush=True)
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        exit_code = 2
        print(f"\nFAIL at {report['stage']}: {exc}", flush=True)
        if report["stage"] == "opencv_import":
            if isinstance(exc, ModuleNotFoundError):
                print("A required package is missing. See setup.ps1.", flush=True)
            elif "application control" in str(exc).lower():
                print("Windows blocked OpenCV's installed cv2.pyd library. The videos are already downloaded.\n"
                      "Downloading them again will not fix this. No video decoding or image processing ran.\n"
                      "See TROUBLESHOOTING.md for the Windows compatibility issue.", flush=True)
    finally:
        if capture is not None:
            capture.release()
        if cv2 is not None and report["preview_frames"]:
            try:
                cv2.destroyAllWindows()
            except Exception as exc:
                report["preview_cleanup_error"] = str(exc)
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Check report: {directory / 'result.json'}", flush=True)
    return exit_code
