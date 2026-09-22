from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import time

import cv2

from .config import Config, ConfigError, atomic_json, validate_polygon
from .evaluation import calibrate, evaluate
from .output import Reporter, summary_text
from .sources import CameraSource, Frame, SourceError, iso, read_image, utcnow, write_image
from .vision import Analyzer, pixel_hash


def parser():
    root = argparse.ArgumentParser(description="Experimental parking occupancy using a camera or built-in recorded demo.")
    root.add_argument("--config", default="config.local.json", help="Local configuration file")
    sub = root.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Play a built-in parking video; no URL, key or configuration needed")
    demo.add_argument("--headless", action="store_true", help="Save results without opening a preview window")
    demo.add_argument("--step", type=float, default=.5, help="Video seconds between samples (default: 0.5)")
    demo.add_argument("--frames", type=int, default=0, help="Stop after N samples; default 0 plays the whole clip")
    demo.add_argument("--out", type=Path, help="Results directory; default runs/demo-indoor/TIMESTAMP")
    check = sub.add_parser("check", help="Check online retrieval without parking configuration")
    check.add_argument("--count", type=int, default=3)
    check.add_argument("--out", type=Path, default=Path("runs/connection-check.json"))
    capture = sub.add_parser("capture", help="Save live frames for setup, references or manual labelling")
    capture.add_argument("--directory", type=Path, default=Path("data/captures"))
    capture.add_argument("--session", required=True, help="Recording period ID; keep different periods separate")
    capture.add_argument("--count", type=int, default=1)
    configure = sub.add_parser("configure", help="Mark parking polygons on a setup image")
    configure.add_argument("--frame", type=Path, required=True)
    mode = configure.add_mutually_exclusive_group(required=True)
    mode.add_argument("--slot", help="ID of a bay to draw or redraw with the mouse")
    mode.add_argument("--polygons-file", type=Path, help="Import [{id, polygon}] JSON instead of drawing")
    reference = sub.add_parser("reference", help="Record a manually verified vacant reference for one bay")
    reference.add_argument("--slot", required=True)
    reference.add_argument("--frame", type=Path, required=True)
    reference.add_argument("--confirm-empty", action="store_true", help="Assert that you inspected this bay and it is empty")
    label = sub.add_parser("label", help="Append manual ground truth to a CSV")
    label.add_argument("--frame", type=Path, required=True)
    label.add_argument("--session", required=True)
    label.add_argument("--labels", nargs="+", required=True, metavar="P01=vacant")
    label.add_argument("--manifest", type=Path, required=True)
    for command in ("calibrate", "evaluate"):
        p = sub.add_parser(command, help="Fit boundaries" if command == "calibrate" else "Evaluate held-out manually labelled images")
        p.add_argument("--manifest", type=Path, required=True)
        p.add_argument("--out", type=Path, default=Path("runs") / (command + ".json"))
    run = sub.add_parser("run", help="Analyze current online frames")
    run.add_argument("--frames", type=int, default=20, help="Number of attempts; 0 runs until Ctrl+C")
    run.add_argument("--out", type=Path, default=Path("runs/live"))
    run.add_argument("--preview", action="store_true", help="Show an OpenCV window; press Q to stop")
    offline = sub.add_parser("analyze-image", help="Explicit offline diagnostic; does not validate a live camera")
    offline.add_argument("--frame", type=Path, required=True)
    offline.add_argument("--out", type=Path, default=Path("runs/offline"))
    return root


def pause_until(started, interval):
    time.sleep(max(0, interval - (time.monotonic() - started)))


def check_camera(config, args):
    if not 1 <= args.count <= 100:
        raise ConfigError("Check count must be between 1 and 100.")
    source = None
    observations = []
    try:
        source = CameraSource(config.data["source"])
        for i in range(args.count):
            started = time.monotonic()
            try:
                frame = source.read()
                observations.append({"frame_id": frame.frame_id, "retrieval_status": "success",
                    "source_captured_at": iso(frame.captured_at), "capture_time_status": frame.capture_time_status,
                    "received_at": iso(frame.received_at), "width": frame.image.shape[1], "height": frame.image.shape[0],
                    "retrieval_duration_ms": (time.monotonic() - started) * 1000, "pixel_hash": pixel_hash(frame.image)})
                print(f"Frame {i + 1}: received {frame.image.shape[1]} x {frame.image.shape[0]}; source capture time {iso(frame.captured_at) or 'unknown'}")
            except SourceError as exc:
                observations.append({"retrieval_status": "failed", "error": str(exc), "attempted_at": iso(utcnow())})
                print(f"Frame {i + 1}: {exc}")
            if i + 1 < args.count:
                pause_until(started, config.data.get("interval_seconds", 3))
    except SourceError as exc:
        observations.append({"retrieval_status": "failed", "error": str(exc)})
    finally:
        if source:
            source.close()
    successes = [x for x in observations if x["retrieval_status"] == "success"]
    timestamps = [x["source_captured_at"] for x in successes if x.get("source_captured_at")]
    report = {"source_id": config.data["source_id"], "checked_at": iso(utcnow()),
              "successful_frames": len(successes), "requested_frames": args.count,
              "distinct_pixel_images": len({x["pixel_hash"] for x in successes}),
              "source_timestamps_advanced": len(set(timestamps)) > 1 if timestamps else None,
              "note": "Successful downloads alone do not prove camera freshness or indoor parking suitability.",
              "observations": observations}
    atomic_json(args.out, report)
    print(f"Connection report: {args.out.resolve()}")
    return 0 if len(successes) == args.count else 2


def capture_frames(config, args):
    if not 1 <= args.count <= 10000:
        raise ConfigError("Capture count must be between 1 and 10000.")
    Config.validate_id(args.session)
    directory = args.directory.resolve() / args.session
    source = CameraSource(config.data["source"])
    try:
        for i in range(args.count):
            started = time.monotonic()
            frame = source.read()
            stem = frame.received_at.strftime("%Y%m%dT%H%M%S_%fZ") + "_" + frame.frame_id[:8]
            path = directory / (stem + ".png")
            write_image(path, frame.image)
            atomic_json(path.with_suffix(".json"), {"source_id": config.data["source_id"], "frame_id": frame.frame_id,
                "session_id": args.session, "source_captured_at": iso(frame.captured_at), "received_at": iso(frame.received_at),
                "capture_time_status": frame.capture_time_status, "origin": "online_camera_retrieval",
                "pixel_hash": pixel_hash(frame.image)})
            print(f"Saved {path}")
            if i + 1 < args.count:
                pause_until(started, config.data.get("interval_seconds", 3))
    finally:
        source.close()
    return 0


def draw_polygon(image, existing, slot_id):
    height, width = image.shape[:2]
    scale = min(1.0, 1200 / width, 650 / height)
    points = []
    title = "Parking setup: left click corners, right click undo, Enter save, Esc cancel"
    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)

    def click(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([min(width - 1, max(0, round(x / scale))), min(height - 1, max(0, round(y / scale)))])
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    cv2.setMouseCallback(title, click)
    try:
        while True:
            preview = cv2.resize(image, (round(width * scale), round(height * scale)))
            import numpy as np
            for slot in existing:
                if slot["id"] != slot_id:
                    cv2.polylines(preview, [np.int32(np.array(slot["polygon"]) * scale)], True, (150, 150, 150), 1)
            if points:
                p = np.int32(np.array(points) * scale)
                cv2.polylines(preview, [p], len(points) >= 3, (0, 220, 255), 2)
                for point in p:
                    cv2.circle(preview, tuple(point), 4, (0, 220, 255), -1)
            cv2.imshow(title, preview)
            key = cv2.waitKey(30) & 0xFF
            if key == 27 or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                return None
            if key in (10, 13):
                try:
                    validate_polygon(points, width, height)
                    return points
                except ConfigError as exc:
                    print(exc)
    finally:
        cv2.destroyAllWindows()


def configure_slots(config, args):
    image = read_image(args.frame)
    old_setup = config.resolve(config.data.get("setup_image"))
    if old_setup and pixel_hash(read_image(old_setup)) != pixel_hash(image):
        raise ConfigError("This configuration already uses a different setup view. Start a new configuration for a new camera view.")
    if args.slot:
        Config.validate_id(args.slot)
        points = draw_polygon(image, config.data["slots"], args.slot)
        if points is None:
            print("Cancelled; configuration unchanged.")
            return 0
        additions = [{"id": args.slot, "polygon": points}]
    else:
        additions = json.loads(args.polygons_file.read_text(encoding="utf-8"))
        if not isinstance(additions, list) or not additions:
            raise ConfigError("Polygon import must be a nonempty list.")
    ids = set()
    for slot in additions:
        Config.validate_id(slot.get("id"))
        validate_polygon(slot.get("polygon"), image.shape[1], image.shape[0])
        if slot["id"] in ids:
            raise ConfigError("Duplicate parking ID in polygon import.")
        ids.add(slot["id"])
    existing = {s["id"]: s for s in config.data["slots"]}
    for slot in additions:
        old = existing.get(slot["id"])
        if not old or old["polygon"] != slot["polygon"]:
            existing[slot["id"]] = {"id": slot["id"], "polygon": slot["polygon"], "reference_image": None, "calibration": None}
    destination = config.path.parent / "data" / config.data["source_id"] / "setup.png"
    write_image(destination, image)
    config.data["setup_image"] = config.relative(destination)
    config.data["slots"] = list(existing.values())
    config.save()
    print(f"Configured {len(existing)} parking bays. Edited polygons need new references and calibration.")
    return 0


def set_reference(config, args):
    if not args.confirm_empty:
        raise ConfigError("Inspect the selected bay and use --confirm-empty only when it is visibly vacant.")
    slot = config.slot(args.slot)
    analyzer = Analyzer(config)
    image = read_image(args.frame)
    alignment = analyzer.alignment(image)
    if not alignment["ok"]:
        raise ConfigError("Reference fails setup-view alignment: " + alignment["reason"])
    path = config.path.parent / "data" / config.data["source_id"] / "references" / (args.slot + ".png")
    write_image(path, image)
    slot["reference_image"] = config.relative(path)
    slot["reference_confirmed_empty_at"] = iso(utcnow())
    slot["calibration"] = None
    config.save()
    print(f"Empty reference saved for {args.slot}; recalibrate this bay before interpreting occupancy.")
    return 0


def add_labels(config, args):
    read_image(args.frame)
    Config.validate_id(args.session)
    rows = []
    path = args.manifest.resolve()
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    relative = Path(os.path.relpath(args.frame.resolve(), path.parent)).as_posix()
    for value in args.labels:
        if "=" not in value:
            raise ConfigError("Use labels such as P01=vacant P02=occupied.")
        slot_id, label = value.split("=", 1)
        config.slot(slot_id)
        if label not in ("vacant", "occupied", "ambiguous"):
            raise ConfigError("Label must be vacant, occupied or ambiguous.")
        if any((path.parent / r["frame_path"]).resolve() == args.frame.resolve() and r["slot_id"] == slot_id for r in rows):
            raise ConfigError("This frame/slot already has a label. Edit its CSV row to correct it.")
        rows.append({"frame_path": relative, "slot_id": slot_id, "label": label, "session_id": args.session})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frame_path", "slot_id", "label", "session_id"])
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    print(f"Saved labels: {path}")
    return 0


def run_camera(config, args):
    if args.frames < 0:
        raise ConfigError("--frames must be zero or positive.")
    analyzer = Analyzer(config)
    reporter = Reporter(args.out, config.data["slots"])
    source = None
    all_ok = True
    try:
        try:
            source = CameraSource(config.data["source"])
        except SourceError as exc:
            reporter.write(analyzer.failure(str(exc)))
            print(f"Camera unavailable: {exc}")
            return 2
        count = 0
        while args.frames == 0 or count < args.frames:
            started = time.monotonic()
            image = None
            try:
                frame = source.read()
                retrieval_ms = (time.monotonic() - started) * 1000
                result = analyzer.analyze(frame)
                image = frame.image if result.get("alignment", {}).get("ok") else None
                result["retrieval_duration_ms"] = retrieval_ms
            except SourceError as exc:
                result = analyzer.failure(str(exc))
                result["retrieval_duration_ms"] = (time.monotonic() - started) * 1000
            result["input_mode"] = "online_camera"
            all_ok = all_ok and result["analysis_status"] != "unavailable"
            canvas = reporter.write(result, image)
            print(f'{result["processed_at"]} | {summary_text(result)} | {result.get("error") or result["analysis_status"]}', flush=True)
            count += 1
            if args.preview:
                factor = min(1, 1200 / canvas.shape[1], 800 / canvas.shape[0])
                cv2.imshow("Parking probe - Q to stop", cv2.resize(canvas, None, fx=factor, fy=factor))
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
            if args.frames == 0 or count < args.frames:
                # Pump GUI events during the interval so the preview stays responsive.
                while time.monotonic() - started < config.data.get("interval_seconds", 3):
                    if args.preview and cv2.waitKey(30) & 0xFF in (ord("q"), 27):
                        return 0 if all_ok else 2
                    time.sleep(.03)
    finally:
        if source:
            source.close()
        cv2.destroyAllWindows()
    return 0 if all_ok else 2


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            from .video_demo import run_demo
            return run_demo(args)
        config = Config(args.config)
        handlers = {"check": check_camera, "capture": capture_frames, "configure": configure_slots,
                    "reference": set_reference, "label": add_labels, "run": run_camera}
        if args.command in handlers:
            return handlers[args.command](config, args)
        if args.command == "calibrate":
            result = calibrate(config, args.manifest.resolve())
            atomic_json(args.out, result)
            for slot_id, calibration in result.items():
                print(f'{slot_id}: {calibration["status"]} ({calibration.get("reason") or "boundaries saved"})')
            return 0 if all(s["status"] == "calibrated" for s in result.values()) else 2
        if args.command == "evaluate":
            report = evaluate(config, args.manifest.resolve())
            atomic_json(args.out, report)
            print(json.dumps({k: v for k, v in report.items() if k != "observations"}, indent=2))
            return 0 if report["minimum_evaluation_requirements_met"] else 2
        if args.command == "analyze-image":
            image = read_image(args.frame)
            result = Analyzer(config).analyze(Frame(image, utcnow()))
            result["input_mode"] = "offline_diagnostic"
            result["capture_time_status"] = "offline_capture_time_unknown"
            Reporter(args.out, config.data["slots"]).write(result, image if result["alignment"]["ok"] else None)
            print("OFFLINE DIAGNOSTIC | " + summary_text(result))
            return 0 if result["analysis_status"] != "unavailable" else 2
    except KeyboardInterrupt:
        print("Stopped.")
        return 130
    except (ConfigError, SourceError) as exc:
        print(f"Cannot continue: {exc}")
        return 2
    except (OSError, ValueError, TypeError, KeyError, cv2.error):
        # Do not echo raw exception text, as network/library diagnostics can
        # expose credentials. Anticipated failures above have actionable codes.
        print("Cannot continue: invalid input, unavailable file, or OpenCV operation failed. Check configuration and the README.")
        return 2
    return 0
