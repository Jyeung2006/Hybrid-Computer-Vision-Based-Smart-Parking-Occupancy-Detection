"""Opt-in, post-hoc Reference priority. Never replaces the primary Final."""
from copy import deepcopy
import csv
import json
from pathlib import Path

from .config import atomic_json
from .vision import occupancy_summary
from .yolo import final_decision

ALTERNATE_POLICY = 'calibrated_reference_priority_experimental_v1'
DEFINITE = ('occupied', 'vacant')


def final_decision_reference_priority(reference, mog2, verified, *, reference_calibrated=False):
    """Prioritize BOTH definite Reference states, including conflicts with YOLO.

    The caller must establish calibration validity, not just reference presence.
    No inference, threshold fitting, or vacancy-from-missing-detection occurs.
    """
    if reference_calibrated is True and reference in DEFINITE:
        state, reason, confirmed = reference, 'calibrated_reference_priority', 'reference_only_experimental'
    else:
        state, reason = final_decision(reference, mog2, verified)
        confirmed = {'opencv_branches_agree': 'reference_and_mog2',
                     'yolov8_verified_vehicle': 'yolov8'}.get(reason)
    return {'state': state, 'reason': reason, 'confirmed_by': confirmed,
            'decision_policy': ALTERNATE_POLICY, 'experimental': True, 'primary': False}


def add_alternate(pair, calibrated_slots=None):
    """Return an enriched COPY; all primary branch and Final fields are retained."""
    result = deepcopy(pair)
    slots = []
    for row in result['rows']:
        calibrated = (row.get('reference_calibrated') is True if calibrated_slots is None
                      else row['slot_id'] in calibrated_slots)
        alt = final_decision_reference_priority(row['reference_state'], row['mog2_state'],
            row.get('yolo_state', 'unknown'), reference_calibrated=calibrated)
        row.update(reference_calibrated=calibrated, final_alt_state=alt['state'],
            final_alt_reason=alt['reason'], final_alt_confirmed_by=alt['confirmed_by'],
            final_alt_policy=ALTERNATE_POLICY, final_alt_experimental=True,
            final_alt_is_primary=False)
        slots.append({'slot_id': row['slot_id'], 'bay_id': row['bay_id'], **alt})
    result['final_alt'] = {'method': ALTERNATE_POLICY, 'experimental': True, 'primary': False,
        'opt_in_comparison': True, 'slots': slots,
        'summary': occupancy_summary(slots, available=any(s['state'] != 'unknown' for s in slots)),
        'scope_note': 'Experimental comparison only. All primary Final fields and counts remain unchanged.'}
    return result


def export_alternate_review(directory, samples):
    """Explicit opt-in export: combined primary/alternate JSONL and flat CSV.

    Called on the UI thread from already-computed samples, never reruns vision.
    The separate directory prevents overwriting primary observations/history.
    """
    directory = Path(directory) / 'experimental-reference-priority'
    directory.mkdir(parents=True, exist_ok=True)
    pairs = [add_alternate(pair) for records in samples.values() for pair in records]
    atomic_json(directory / 'manifest.json', {'experimental': True, 'primary': False,
        'opt_in': True, 'decision_policy': ALTERNATE_POLICY, 'sample_pairs': len(pairs),
        'note': 'Primary fields retained; no new inference. Disabling display does not delete this historical export.'})
    with (directory / 'history.jsonl').open('w', encoding='utf-8') as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, allow_nan=False) + '\n')
    rows = [row for pair in pairs for row in pair['rows']]
    with (directory / 'observations.csv').open('w', newline='', encoding='utf-8') as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return directory
