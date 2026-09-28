"""Replay every mapped view under the OpenCV-first policy and compare saved rows."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from parking_probe.areas import VIEWS, EXTRA_VIEWS, OVERHEAD, inventory, fetch_overhead
from parking_probe.catalog import CLIPS
from parking_probe.comparison import run_comparison
from parking_probe.monitor import prepare_preset
from parking_probe.view_presets import prepare_view
from parking_probe.vehicle import VehicleDetector, prepare_model
from parking_probe.yolo import YOLODetector, VerificationService

BASELINE = ROOT / 'runs/areas/20260923T114108_587187Z'
BASELINE_NAMES = ('chad', 'chad-camera-2', 'chad-camera-3', 'chad-camera-4', 'overhead')
STATES = ('occupied', 'vacant', 'uncertain', 'unknown')


def rows_in(root):
    rows = {}
    for name in BASELINE_NAMES:
        with (root / name / 'observations.csv').open(newline='', encoding='utf-8') as handle:
            for row in csv.DictReader(handle):
                key = (row['recording_id'], row['frame_id'], row['slot_id'])
                if key in rows:
                    raise AssertionError(f'duplicate observation: {key}')
                rows[key] = row
    return rows


def audit(before_root, after_root):
    before, after = rows_in(before_root), rows_in(after_root)
    if before.keys() != after.keys():
        raise AssertionError('replay observation identities differ from baseline')
    counts = defaultdict(lambda: {'before': Counter(), 'after': Counter(),
                                  'yolo_before': 0, 'yolo_after': 0,
                                  'provisional_occupied': 0, 'provisional_vacant': 0})
    by_bay = defaultdict(lambda: {'before': Counter(), 'after': Counter()})
    changes = []
    for key in sorted(after):
        old, new = before[key], after[key]
        for field in ('reference_state', 'mog2_state'):
            if old[field] != new[field]:
                raise AssertionError(f'{key} changed {field}: {old[field]} -> {new[field]}')
        rec = key[0]
        entry, bay = counts[rec], by_bay[(rec, new['bay_id'])]
        for item in (entry, bay):
            item['before'][old['final_state']] += 1
            item['after'][new['final_state']] += 1
        entry['yolo_before'] += old['yolo_requested'] == 'True'
        entry['yolo_after'] += new['yolo_requested'] == 'True'
        entry['provisional_occupied'] += new['final_state'] == 'occupied' and new['final_provisional'] == 'True'
        entry['provisional_vacant'] += new['final_state'] == 'vacant' and new['final_provisional'] == 'True'
        if old['final_state'] != new['final_state']:
            changes.append({'recording': rec, 'time': new['sample_time_seconds'],
                            'bay_id': new['bay_id'], 'slot_id': new['slot_id'],
                            'before': old['final_state'], 'after': new['final_state'],
                            'source': new['final_confirmed_by'], 'reason': new['final_reason'],
                            'provisional': new['final_provisional'] == 'True'})
    def formatted(counter):
        return {state: counter[state] for state in STATES}
    return {'observations': len(after), 'recordings': {
        rec: {**{name: formatted(entry[name]) for name in ('before', 'after')},
              **{name: entry[name] for name in ('yolo_before', 'yolo_after',
                  'provisional_occupied', 'provisional_vacant')}}
        for rec, entry in sorted(counts.items())},
        'bays': {rec + '/' + bay: {name: formatted(entry[name]) for name in ('before', 'after')}
                 for (rec, bay), entry in sorted(by_bay.items())},
        'decision_sources': dict(Counter((row['final_confirmed_by'] or
            ('provisional_' + row['final_state'] if row['final_provisional'] == 'True' else 'none'))
            for row in after.values())),
        'changes': changes,
        'b08_chad4_15': next(row for row in after.values() if row['recording_id'] == 'chad-4'
                          and row['slot_id'] == 'B08' and float(row['sample_time_seconds']) == 15.0),
        'accuracy_note': 'No independent held-out labels; coverage and changes are not accuracy.'}


def main():
    if not BASELINE.exists():
        raise SystemExit('Saved baseline is missing')
    out = ROOT / 'runs/verification/opencv-first' / datetime.now(timezone.utc).strftime('replay-%Y%m%dT%H%M%S_%fZ')
    stop = threading.Event()
    mobilenet = VehicleDetector(prepare_model())
    service = VerificationService(YOLODetector())
    try:
        for view in [VIEWS['chad-1'], *(VIEWS[c.id] for c in EXTRA_VIEWS), VIEWS['overhead-1']]:
            if view.site == 'overhead':
                prepared = prepare_preset(lambda *args: None, stop,
                    ROOT / 'presets/overhead-all-bays.json', [OVERHEAD], fetch_overhead, ROOT / 'data/overhead-all')
                clips, profile, name = [OVERHEAD], 'aerial', 'overhead'
            else:
                prepared = prepare_view(view, lambda *args: None, stop, include_empty_evidence=True)
                clips = CLIPS if view.camera == 'Camera 1' else [view.clip]
                profile = 'coco'
                name = 'chad' if view.camera == 'Camera 1' else view.clip.id
            issues = []
            def emit(kind, value):
                if kind == 'error':
                    issues.append(value)
            code = run_comparison(clips, 3, stop, emit, fast=True, out=out / name,
                prepared=prepared, bay_map={s['id']: s['bay_id'] for s in inventory(view)},
                verification=True, service=service, verification_profile=profile,
                detector=mobilenet, opencv_first=True)
            if code or issues:
                raise AssertionError((name, code, issues))
            print(name, 'complete', flush=True)
    finally:
        service.close()
    report = audit(BASELINE, out)
    report_path = out.parent / 'report.json'
    report['replay_path'] = str(out)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'observations': report['observations'],
                      'recordings': report['recordings'],
                      'decision_sources': report['decision_sources'],
                      'b08_chad4_15': {k: report['b08_chad4_15'][k] for k in
                          ('reference_state', 'mog2_state', 'vehicle_state', 'yolo_state',
                           'final_state', 'final_reason', 'final_provisional')},
                      'changed_count': len(report['changes']),
                      'report': str(report_path)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
