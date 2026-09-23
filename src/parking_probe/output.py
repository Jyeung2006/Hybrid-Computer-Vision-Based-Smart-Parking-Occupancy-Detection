from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

from .config import atomic_json
from .sources import write_image

COLORS = {"vacant": (70, 185, 70), "occupied": (70, 70, 230), "uncertain": (0, 195, 255), "unknown": (160, 160, 160)}


def summary_text(result):
    s = result["summary"]
    regions = result.get("monitoring_scope") == "test_regions"
    subject = "Region occupancy" if regions else "Occupancy"
    if s["occupancy_min_pct"] is None:
        rate = f"{subject} unavailable"
    elif s["occupancy_pct"] is not None:
        rate = f'{subject} {s["occupancy_pct"]:.1f}%'
    else:
        rate = f'{subject} range {s["occupancy_min_pct"]:.1f}-{s["occupancy_max_pct"]:.1f}%'
    count = s["total_monitored_regions"] if regions else s["total_monitored_bays"]
    units = "test regions" if regions else "bays"
    return f'{rate} | {s["occupied"]} occupied, {s["vacant"]} vacant, {s["unresolved"]} unresolved / {count} {units}'


def annotate(image, result, slots):
    if image is None:
        canvas = np.full((480, 960, 3), 30, np.uint8)
    else:
        canvas = image.copy()
    states = {s["slot_id"]: s for s in result["slots"]}
    if image is not None:
        for slot in slots:
            state = states[slot["id"]]
            points = np.int32(slot["polygon"])
            color = (18, 100, 149) if state.get('provisional') else COLORS[state["state"]]
            cv2.polylines(canvas, [points], True, color, 2)
            x, y = points.mean(axis=0).astype(int)
            if len(slots)>20:
                text=slot['id']+' '+('P?' if state.get('provisional') else
                                   {'occupied':'O','vacant':'V','uncertain':'?','unknown':'-'}[state['state']])
                left,top=map(int,points[0]+[2,2])
                (width,height),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,.32,1)
                cv2.rectangle(canvas,(left,top),(left+width+4,top+height+6),(20,20,20),-1)
                cv2.putText(canvas,text,(left+2,top+height+2),cv2.FONT_HERSHEY_SIMPLEX,.32,color,1,cv2.LINE_AA)
                continue
            if "bay_id" in state:
                # Two centered lines below the bay keep long shared IDs from
                # colliding with neighbouring labels or covering the vehicle.
                lines = [state["bay_id"], 'VACANT (P)' if state.get('provisional') else state["state"].upper()]
                scale = min(.43, max(40, int(np.ptp(points[:, 0])) - 12) /
                            max(cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1, 1)[0][0] for line in lines))
                y = min(int(points[:, 1].max()) + 17, canvas.shape[0] - 24)
                for number, line in enumerate(lines):
                    (width, height), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
                    left = max(3, min(int(x) - width // 2, canvas.shape[1] - width - 3))
                    baseline = y + number * 17
                    cv2.rectangle(canvas, (left - 3, baseline - height - 3), (left + width + 3, baseline + 3), (20, 20, 20), -1)
                    cv2.putText(canvas, line, (left, baseline), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)
            else:
                label = f'{slot["id"]}: {"vacant (P)" if state.get("provisional") else state["state"]}'
                cv2.putText(canvas, label, (max(0, x - 40), y), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(canvas, label, (max(0, x - 40), y), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
    # Add a separate footer so status text never hides the parking spaces.
    display_width = max(canvas.shape[1], 1000)
    padded = np.full((canvas.shape[0], display_width, 3), 20, np.uint8)
    padded[:, :canvas.shape[1]] = canvas
    footer = np.full((170, display_width, 3), 20, np.uint8)
    capture = result.get("source_captured_at") or "unknown (retrieval time is not capture time)"
    recorded = result.get("input_mode") == "recorded_video"
    title = (f'RECORDED DEMO | video {result["video_position_seconds"]:.2f}s / {result["video_duration_seconds"]:.2f}s | NOT LIVE'
             if recorded else f'EXPERIMENTAL | {result["source_id"]} | {result["analysis_status"]}')
    if result.get("method") == "mog2_foreground":
        title += " | MOG2"
    evidence_note = "Foreground proportion, not vehicle recognition" if result.get("method") == "mog2_foreground" else "Appearance difference, not vehicle recognition"
    if result.get('method') == 'opencv_mobilenet_ssd_plus_reviewed_empty_match':
        title += ' | VEHICLE + EMPTY MATCH'
        evidence_note = 'OpenCV MobileNet-SSD; detector score is not parking occupancy probability'
    elif result.get('method') == 'combined_experimental_estimate':
        title += ' | FINAL ESTIMATE'
        evidence_note = 'Reference/MOG2 agreement or vehicle evidence; conflicting definite states stay uncertain'
    elif result.get('method') == 'selective_yolov8s_verification':
        title += ' | YOLOv8s VERIFICATION'
        evidence_note = 'Only unresolved/conflicting bays verified; absent or weak detection is not vacancy'
    elif result.get('method') == 'selective_yolov8_final_estimate':
        title += ' | FINAL HYBRID ESTIMATE'
        evidence_note = 'Reference + MOG2 agreement, YOLOv8 vehicle, or guarded vacancy; P = provisional no-detection'
    lines = [title,
             summary_text(result), f'Source captured: {capture}',
             f'{"Decoded locally" if recorded else "Received"}: {result.get("received_at") or "unavailable"}',
             f'Processed: {result["processed_at"]} | duration: {result.get("processing_duration_ms") or 0:.1f} ms',
             f'Stale: {result["stale"]} | {result.get("error") or evidence_note}']
    for i, line in enumerate(lines):
        scale = min(.52, (display_width - 24) / max(1, cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1, 1)[0][0]))
        cv2.putText(footer, line, (12, 24 + i * 26), cv2.FONT_HERSHEY_SIMPLEX, scale, (230, 230, 230), 1, cv2.LINE_AA)
    return np.vstack((padded, footer))


def rotate(path: Path, maximum=10 * 1024 * 1024, backups=3):
    if not path.exists() or path.stat().st_size < maximum:
        return
    oldest = path.with_name(path.name + f".{backups}")
    oldest.unlink(missing_ok=True)
    for number in range(backups - 1, 0, -1):
        existing = path.with_name(path.name + f".{number}")
        if existing.exists():
            existing.replace(path.with_name(path.name + f".{number + 1}"))
    path.replace(path.with_name(path.name + ".1"))


class Reporter:
    def __init__(self, directory: Path, slots):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.slots = slots

    def _csv(self, name, rows):
        path = self.directory / name
        rotate(path)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            if new:
                writer.writeheader()
            writer.writerows(rows)

    def write(self, result, image=None):
        canvas = annotate(image, result, self.slots)
        write_image(self.directory / "latest.png", canvas)
        atomic_json(self.directory / "latest.json", result)
        history = self.directory / "history.jsonl"
        rotate(history)
        with history.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, allow_nan=False) + "\n")
        common = {k: result.get(k) for k in ("source_id", "frame_id", "source_captured_at", "capture_time_status", "received_at", "processing_started_at", "processed_at", "processing_duration_ms", "retrieval_duration_ms", "frame_age_seconds", "retrieval_age_seconds", "freshness_basis", "retrieval_status", "analysis_status", "stale", "error")}
        if result.get("input_mode") == "recorded_video":
            common.update({k: result.get(k) for k in ("input_mode", "monitoring_scope", "video_id", "video_filename", "video_position_seconds", "video_frame_index", "video_duration_seconds", "original_capture_time_known", "update_interval_seconds", "skipped_replay_samples", "replay_elapsed_seconds")})
        self._csv("summary.csv", [{**common, **result["summary"]}])
        if result["slots"]:
            self._csv("slots.csv", [{**common, **slot, "slot_reason": slot["reason"]} for slot in result["slots"]])
        return canvas
