"""Manual physical-bay identity, conservative view fusion and time summaries.

An appearance difference is not a probability. Cameras are reconciled by their
discrete decisions, then each physical bay contributes exactly once to time
and site totals. No vehicle tracking or automatic cross-camera matching.
"""
from collections import Counter
from copy import deepcopy
import math

from .vision import occupancy_summary

STATES = ("occupied", "vacant", "uncertain", "unknown")


def fuse_views(bay_ids, cameras, observations, timeline, max_age=4.5, max_skew=.1):
    bays = []
    for bay_id in bay_ids:
        views = []
        for camera in cameras:
            for local_id, physical_id in camera["slot_map"].items():
                if physical_id != bay_id:
                    continue
                observation = observations.get(camera["camera_id"], {})
                slot = next((s for s in observation.get("slots", []) if s["slot_id"] == local_id), {})
                sampled = observation.get("sample_time_seconds")
                age = timeline - sampled if sampled is not None else None
                reason = slot.get("reason")
                state = slot.get("state", "unknown")
                if (observation.get("analysis_status") != "estimated" or observation.get("stale", True)
                        or age is None or age < 0 or age > max_age):
                    state = "unknown"
                    reason = observation.get("error") or "missing_or_stale_view"
                views.append({"camera_id": camera["camera_id"], "slot_id": local_id, "state": state,
                              "difference_score": slot.get("difference_score"), "reason": reason,
                              "sample_age_seconds": age, "frame_id": observation.get("frame_id"),
                              "frame_time_seconds": observation.get("frame_time_seconds"),
                              "source_captured_at": observation.get("source_captured_at"),
                              "processed_at": observation.get("processed_at")})
        usable = [v for v in views if v["state"] != "unknown"]
        states = {v["state"] for v in usable}
        frame_times = [v["frame_time_seconds"] for v in usable if v["frame_time_seconds"] is not None]
        if not usable:
            state, reason = "unknown", "no_usable_view"
        elif len(usable) > 1 and (len(frame_times) != len(usable) or max(frame_times) - min(frame_times) > max_skew):
            state, reason = "uncertain", "views_not_synchronized"
        elif "occupied" in states and "vacant" in states:
            state, reason = "uncertain", "views_disagree"
        elif "uncertain" in states:
            state, reason = "uncertain", "view_uncertain"
        else:
            state = next(iter(states))
            reason = "views_agree" if len(usable) > 1 else "single_view"
        bays.append({"bay_id": bay_id, "state": state, "reason": reason, "views": views,
                     "usable_views": len(usable), "expected_views": len(views),
                     "degraded": len(usable) < len(views)})
    summary = occupancy_summary(bays, available=any(b["state"] != "unknown" for b in bays))
    return {"timeline_seconds": timeline, "bays": bays, "summary": summary}


class TimeWindow:
    """Integrate the last fused state between scheduled observations.

    The runner sends UNKNOWN on a missed sample, decode failure or camera end.
    Rates describe sampled state duration, not unseen ground truth. Closing a
    window at t happens before a sample at t: windows are [start, end).
    """
    def __init__(self, initial):
        self.latest = deepcopy(initial)
        self.start = self.cursor = 0.0
        self.durations = {b["bay_id"]: Counter({s: 0.0 for s in STATES}) for b in initial["bays"]}
        self.samples = 0

    def advance(self, when):
        if not math.isfinite(when) or when < self.cursor:
            raise ValueError("Timeline must be finite and monotonic.")
        elapsed = when - self.cursor
        for bay in self.latest["bays"]:
            self.durations[bay["bay_id"]][bay["state"]] += elapsed
        self.cursor = when

    def update(self, when, fused, sample=True):
        self.advance(when)
        self.latest = deepcopy(fused)
        self.samples += int(sample)

    def close(self, when, partial=False):
        self.advance(when)
        duration = when - self.start
        if duration <= 0:
            return None
        bays = []
        for bay in self.latest["bays"]:
            seconds = dict(self.durations[bay["bay_id"]])
            unresolved = seconds["uncertain"] + seconds["unknown"]
            low = 100 * seconds["occupied"] / duration
            high = 100 * (seconds["occupied"] + unresolved) / duration
            bays.append({**deepcopy(bay), "state_seconds": seconds,
                         "occupied_time_pct": low if unresolved < 1e-9 else None,
                         "occupied_time_min_pct": low, "occupied_time_max_pct": high,
                         "classified_time_pct": 100 * (duration - unresolved) / duration})
        result = {"window_start_seconds": self.start, "window_end_seconds": when,
                  "window_duration_seconds": duration, "partial_window": partial,
                  "sample_count": self.samples, "rate_basis": "sampled_state_duration_over_window",
                  "state_basis": "latest_fused_state_before_window_end",
                  "bays": bays, "summary": deepcopy(self.latest["summary"])}
        self.start = when
        self.durations = {b["bay_id"]: Counter({s: 0.0 for s in STATES}) for b in bays}
        self.samples = 0
        return result


def format_window(result):
    def clock(seconds):
        minutes, sec = divmod(round(seconds), 60)
        return f"{minutes:02d}:{sec:02d}"

    def rate(low, high):
        if low is None:
            return "Unavailable"
        return f"{low:.1f}%" if abs(high - low) < 1e-8 else f"{low:.1f}-{high:.1f}%"

    start, end = result["window_start_seconds"], result["window_end_seconds"]
    label = "FINAL PARTIAL WINDOW" if result["partial_window"] else "10-SECOND SUMMARY"
    rows = ["", "=" * 88,
            f"{label} | Video {clock(start)} - {clock(end)} | {end-start:.3f}s | {result.get('display_time', '')}",
            f"{'BAY ID':<17} {'LATEST STATE':<13} {'OCCUPIED TIME':<19} {'CLASSIFIED':<12} {'VIEWS':<7} DETAIL",
            "-" * 88]
    for bay in result["bays"]:
        occupied = rate(bay["occupied_time_min_pct"], bay["occupied_time_max_pct"])
        detail = bay["reason"].replace("_", " ")
        if bay["degraded"]:
            detail += "; missing view"
        rows.append(f"{bay['bay_id']:<17} {bay['state'].upper():<13} {occupied:<19} "
                    f"{bay['classified_time_pct']:>6.1f}%      {bay['usable_views']}/{bay['expected_views']:<5} {detail}")
    s = result["summary"]
    rows.append(f"At window end: {s['occupied']} occupied | {s['vacant']} vacant | "
                f"{s['uncertain']} uncertain | {s['unknown']} unknown | {s['total_monitored_bays']} unique bays")
    rows.append("Site occupancy at window end: " + rate(s["occupancy_min_pct"], s["occupancy_max_pct"]))
    rows.append("Occupied time = estimated time occupied within this window; a range includes unresolved time.")
    return "\n".join(rows)
