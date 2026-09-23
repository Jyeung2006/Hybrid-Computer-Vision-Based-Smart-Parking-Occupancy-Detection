"""Recorded-review state. Never borrow results from a future sample or another clip."""
from bisect import bisect_right
from copy import deepcopy

from .comparison import BAY_MAP, consensus
from .vision import occupancy_summary

STATES = ("occupied", "vacant", "uncertain", "unknown")


class Review:
    def __init__(self):
        self.samples = {}
        self.windows = {}

    def add_samples(self, batch):
        for pair in batch["recordings"]:
            self.samples.setdefault(pair["recording_id"], []).append(pair)

    def add_windows(self, windows):
        for window in windows:
            self.windows.setdefault(window["recording_id"], []).append(window)

    def at(self, clip, position):
        records = self.samples.get(clip, [])
        times = [r["reference"]["sample_time_seconds"] for r in records]
        index = bisect_right(times, position + 1e-8) - 1
        return records[index] if index >= 0 else None

    def window_at(self, clip, position):
        records = self.windows.get(clip, [])
        times = [r["reference"]["window_end_seconds"] for r in records]
        index = bisect_right(times, position + 1e-8) - 1
        return records[index] if index >= 0 else None


class PlaybackGuard:
    """Recount guarded vacancies during GUI playback after any seek or replay.

    Saved analysis history remains immutable; the current display requires three
    consecutive *played* samples before showing a guarded vacancy again.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.last = None
        self.streaks = {}
        self.cached = None

    def observe(self, pair):
        if pair is None:
            self.reset()
            return None
        key = (pair['reference']['source_id'], pair['recording_id'],
               pair['reference']['sample_time_seconds'], pair['reference']['frame_id'])
        if key == self.last:
            return self.cached
        if (self.last is None or key[:2] != self.last[:2] or key[3] == self.last[3]
                or abs(key[2] - self.last[2] - 3.0) > 1e-6):
            self.streaks.clear()
        self.last = key
        display = deepcopy(pair)
        for row in display['rows']:
            bay = row['slot_id']
            if row.get('base_final_state') in ('occupied', 'vacant'):
                self.streaks[bay] = 0
                continue
            candidate = row.get('vacancy_evidence') in (
                'provisional_repeated_no_detection', 'reviewed_empty_and_three_clean_no_detections') and row.get('vacancy_guard_reason') in (
                'streak_incomplete', 'provisional_repeated_no_detection',
                'reviewed_empty_and_three_clean_no_detections')
            self.streaks[bay] = min(3, self.streaks.get(bay, 0) + 1) if candidate else 0
            if candidate and self.streaks[bay] < 3:
                row['final_state'] = row['base_final_state']
                row['final_reason'] = 'playback_guard_streak_incomplete'
                row['final_confirmed_by'] = row.get('base_final_confirmed_by')
                row['final_provisional'] = False
            row['vacancy_guard_streak'] = self.streaks[bay]
        if 'final' in display:
            by_slot = {r['slot_id']: r for r in display['rows']}
            for slot in display['final']['slots']:
                row = by_slot[slot['slot_id']]
                slot.update(state=row['final_state'], reason=row['final_reason'],
                            confirmed_by=row.get('final_confirmed_by'),
                            provisional=row.get('final_provisional', False),
                            vacancy_guard_streak=row.get('vacancy_guard_streak', 0))
            display['final']['summary'] = occupancy_summary(display['final']['slots'])
        self.cached = display
        return display

def chart_data(pair, bay_ids=None):
    if bay_ids is None:
        bay_ids = [r['bay_id'] for r in pair['rows']] if pair else list(BAY_MAP.values())
    source = {r['bay_id']: r for r in pair['rows']} if pair else {}
    rows = []
    for bay in bay_ids:
        r = source.get(bay, {"bay_id": bay, "reference_state": "unknown", "mog2_state": "unknown",
                             "reference_reason": "calibration_or_observation_missing", "mog2_reason": "calibration_or_observation_missing"})
        rows.append({**r, "state": r.get("final_state", consensus(r["reference_state"], r["mog2_state"]))})
    return rows, occupancy_summary(rows, available=any(r["state"] != "unknown" for r in rows))


def ring_segments(summary):
    """Clockwise Tk canvas angles. Unknown and uncertain consume their own area."""
    total = summary["total_monitored_bays"]
    start = 90.0
    result = []
    for state in STATES:
        extent = 360.0 * summary[state] / total if total else 0.0
        if extent:
            result.append((state, start, -extent))
        start -= extent
    return result


def window_text(window):
    if window is None:
        return "The first 10-second summary appears at video 00:10."
    ref = window["reference"]
    label = "Final partial window" if ref["partial_window"] else "10-second summary"
    lines = [f"{label}  |  {ref['window_start_seconds']:.1f} - {ref['window_end_seconds']:.1f}s",
             "Latest counts in this window:"]
    for method, title in (("reference", "Reference"), ("mog2", "MOG2"), ("vehicle", "Vehicle + empty match"), ('yolo','YOLOv8 verification'), ("final", "Final estimate")):
        if method not in window:
            continue
        s = window[method]["summary"]
        lines.append(f"{title}: {s['occupied']} occupied / {s['vacant']} vacant / "
                     f"{s['uncertain']} uncertain / {s['unknown']} unknown")
    if 'yolo' in window:
        lines.append('YOLO unknown includes slots skipped because OpenCV already agreed.')
    extra='yolo' if 'yolo' in window else 'vehicle' if 'vehicle' in window else None
    lines.append("Estimated occupied time per bay (Reference / MOG2" + ((" / YOLOv8 / Final):" if extra=='yolo' else " / Vehicle / Final):") if extra else "):"))
    for r, m in zip(ref["bays"], window["mog2"]["bays"], strict=True):
        def rate(b):
            low, high = b["occupied_time_min_pct"], b["occupied_time_max_pct"]
            return f"{low:.0f}%" if abs(high-low) < 1e-8 else f"{low:.0f}-{high:.0f}%"
        suffix = ''
        if extra:
            v = next(b for b in window[extra]['bays'] if b['bay_id'] == r['bay_id'])
            f = next(b for b in window['final']['bays'] if b['bay_id'] == r['bay_id'])
            suffix = f" / {rate(v)} / {rate(f)}  ({f['state']}{' PROVISIONAL' if f.get('provisional') else ''})"
        lines.append(f"{r['bay_id']}: {rate(r)} / {rate(m)}" + suffix)
    return "\n".join(lines)
