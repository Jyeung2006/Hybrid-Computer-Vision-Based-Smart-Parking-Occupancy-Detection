"""Formatting and replay scheduling, independent of OpenCV and the GUI."""
from datetime import datetime
import math


def video_clock(seconds):
    # A source frame nearest 18 seconds can be at 17.9846 s (29.97 fps).
    # Round the display label; exact positions remain in the JSON and CSV.
    seconds = max(0, round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def occupancy_text(summary):
    if summary.get("occupancy_min_pct") is None:
        return "Unavailable"
    exact = summary.get("occupancy_pct")
    if exact is not None:
        return f"{exact:.1f}%"
    return f'{summary["occupancy_min_pct"]:.1f} - {summary["occupancy_max_pct"]:.1f}%'


def occupancy_table(result):
    """Compact ASCII table; failed frames must not look like zero occupancy."""
    summary = result["summary"]
    available = result.get("analysis_status") != "unavailable"
    stamp = datetime.fromisoformat(result["processed_at"]).astimezone().strftime("%H:%M:%S.%f")[:-3]
    duration = result.get("processing_duration_ms")
    columns = [("TIME", stamp, 12), ("VIDEO", video_clock(result["video_position_seconds"]), 6)]
    columns += [(slot["slot_id"], slot["state"].upper(), max(9, len(slot["slot_id"]))) for slot in result["slots"]]
    columns += [("PARKED", str(summary["occupied"]) if available else "--", 6),
                ("VACANT", str(summary["vacant"]) if available else "--", 6),
                ("UNRESOLVED", str(summary["unresolved"]), 10),
                ("OCCUPANCY", occupancy_text(summary), 17),
                ("CV ms", f"{duration:.1f}" if duration is not None else "--", 6)]
    return tuple("  ".join(str(c[index]).ljust(c[2]) for c in columns).rstrip() for index in (0, 1))


def sample_indices(frame_count, fps, interval):
    if frame_count <= 0 or not math.isfinite(fps) or fps <= 0 or not math.isfinite(interval) or interval <= 0:
        raise ValueError("Invalid video timing.")
    if interval * fps < 1:
        raise ValueError("Interval must be at least one source frame.")
    number = 0
    while True:
        index = round(number * interval * fps)
        if index >= frame_count:
            return
        yield number, index
        number += 1


def local_time(value):
    return datetime.fromisoformat(value).astimezone().strftime("%d %b %Y  %H:%M:%S %z") if value else "Unknown"


def replay_delay(start, number, interval, now, previous_published=None):
    """Time to the next 3-second deadline; skip overdue samples, never burst.

    A slow detector can miss a deadline. Skip overdue samples rather than
    replaying a backlog rapidly. Normal deadlines stay on the original grid.
    """
    deadline = start + number * interval
    if number and now - deadline >= interval:
        return None
    if previous_published is not None and deadline < previous_published + min(1.0, interval / 2):
        return None
    return max(0.0, deadline - now)


def runtime_error(exc):
    if isinstance(exc, ModuleNotFoundError):
        return "A Python dependency is missing. Run setup.ps1, then run main.py again."
    if isinstance(exc, ImportError) and "application control" in str(exc).lower():
        return ("OpenCV could not load. Windows reported an Application Control/DLL error. "
                "No occupancy was calculated. See TROUBLESHOOTING.md; the blocked library "
                "must be reviewed by your device administrator. Video previews and source links remain available.")
    if isinstance(exc, ImportError) and "dll load failed" in str(exc).lower():
        return "OpenCV could not load a required DLL. No occupancy was calculated. See TROUBLESHOOTING.md."
    return "Processing stopped. " + str(exc)[:300]
