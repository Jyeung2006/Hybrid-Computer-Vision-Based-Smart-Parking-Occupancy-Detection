"""Replay all mapped views and require visible method support for every final state."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from parking_probe.areas import VIEWS, EXTRA_VIEWS, OVERHEAD, inventory, fetch_overhead
from parking_probe.catalog import CLIPS
from parking_probe.comparison import run_comparison
from parking_probe.interface_model import chart_data
from parking_probe.monitor import prepare_preset
from parking_probe.view_presets import prepare_view
from parking_probe.vision import occupancy_summary
from parking_probe.yolo import YOLODetector, VerificationService, needs_verification, DECISION_POLICY


def observations(directory):
    for path in sorted(directory.glob('*/history.jsonl')):
        for line in path.read_text().splitlines():
            yield from json.loads(line)['recordings']


def audit_previous(directory):
    result = {}
    for item in observations(directory):
        entry = result.setdefault(item['recording_id'], dict(observations=0,
            vacant_without_classic_agreement=0, vacant_with_all_three_unresolved=0))
        for row in item['rows']:
            entry['observations'] += 1
            if row['final_state'] == 'vacant' and not row['reference_state'] == row['mog2_state'] == 'vacant':
                entry['vacant_without_classic_agreement'] += 1
                if all(row[k] in ('unknown','uncertain') for k in ('reference_state','mog2_state','yolo_state')):
                    entry['vacant_with_all_three_unresolved'] += 1
    return result


def validate(directory, preparation_seconds=None, baseline=None):
    items = list(observations(directory))
    assert len(items) == 60
    assert {item['recording_id'] for item in items} == set(VIEWS)
    count = confirmations = 0
    for item in items:
        assert item['yolo']['inference_completed'] and not item['yolo']['error']
        assert item['final']['decision_policy'] == DECISION_POLICY
        slots = {s['slot_id']:s for s in item['final']['slots']}
        for row in item['rows']:
            count += 1
            ref, mog, yolo, state = (row[k] for k in ('reference_state','mog2_state','yolo_state','final_state'))
            agreement = ref == mog and ref in ('vacant','occupied')
            assert row['yolo_requested'] == (not agreement)
            assert needs_verification(ref, mog) == (not agreement)
            if agreement:
                assert state == ref and row['final_confirmed_by'] == 'reference_and_mog2'
            elif yolo == 'occupied':
                assert state == 'occupied' and row['final_confirmed_by'] == 'yolov8'
            else:
                assert state in ('unknown','uncertain') and row['final_confirmed_by'] is None
            if state == 'vacant':
                assert ref == mog == 'vacant'
            confirmations += state in ('vacant','occupied')
            assert slots[row['slot_id']]['state'] == state
            assert slots[row['slot_id']]['confirmed_by'] == row['final_confirmed_by']
            assert 'empty_candidate' not in row
        rows, chart = chart_data(item)
        expected = occupancy_summary(rows, available=any(r['state']!='unknown' for r in rows))
        assert chart == expected == item['final']['summary']
    assert count == 1088
    sources = {}
    for path in sorted(directory.glob('*/final-summary.json')):
        assert json.loads((path.parent/'run.json').read_text())['status'] == 'complete'
        final = json.loads(path.read_text())
        assert final['decision_rule'] == DECISION_POLICY
        sources[path.parent.name] = final['summaries_by_recording']
        # Ten-second and final partial summaries derive from the same final states.
        for line in (path.parent/'windows.jsonl').read_text().splitlines():
            window = json.loads(line)
            for bay in window['final']['bays']:
                if bay['state'] == 'vacant':
                    for method in ('reference','mog2'):
                        assert next(b['state'] for b in window[method]['bays'] if b['bay_id']==bay['bay_id']) == 'vacant'
    groups = {}
    for name in ('chad','overhead'):
        selected = [x for x in items if ('overhead' if x['recording_id']=='overhead-1' else 'chad') == name]
        states = Counter(r['final_state'] for x in selected for r in x['rows'])
        durations = [x['final']['processing_duration_ms'] for x in selected]
        groups[name] = dict(frames=len(selected), bay_observations=sum(states.values()), counts=dict(states),
            coverage_pct=100*(states['occupied']+states['vacant'])/sum(states.values()),
            branch_sum_median_ms=float(np.median(durations)), branch_sum_p95_ms=float(np.percentile(durations,95)))
    result = dict(analysis_directory=str(directory), decision_policy=DECISION_POLICY,
        samples=len(items), bay_observations=count, definite_observations=confirmations,
        unsupported_definite_observations=0, preparation_seconds=preparation_seconds,
        summaries_by_source=sources, groups=groups, independent_accuracy_measured=False,
        timing_scope='Reference/MOG2/YOLO; excludes decoding/registration/report writing/rendering')
    if baseline:
        result.update(previous_run=str(baseline), previous_audit=audit_previous(baseline))
    target = ROOT/'runs/verification/decision-check.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2)+'\n')
    print('CHECK PASSED:', len(items), 'frames,', count, 'observations; no unsupported final decisions.', flush=True)
    print(str(target), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing-run', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if args.existing_run:
        validate(args.existing_run.resolve(), baseline=args.baseline)
        return
    started = time.perf_counter()
    out = ROOT/'runs/areas'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    stop = threading.Event()
    service = VerificationService(YOLODetector())
    try:
        for view in [VIEWS['chad-1'], *(VIEWS[c.id] for c in EXTRA_VIEWS), VIEWS['overhead-1']]:
            if view.site == 'overhead':
                prepared = prepare_preset(lambda *args:None, stop, ROOT/'presets/overhead-all-bays.json',
                    [OVERHEAD], fetch_overhead, ROOT/'data/overhead-all')
                clips, profile, name = [OVERHEAD], 'aerial', 'overhead'
            else:
                prepared = prepare_view(view, lambda *args:None, stop, include_empty_evidence=False)
                clips = CLIPS if view.camera == 'Camera 1' else [view.clip]
                profile, name = 'coco', ('chad' if view.camera == 'Camera 1' else view.clip.id)
            issues = []
            def emit(kind, value):
                if kind == 'error': issues.append(value)
            code = run_comparison(clips, 3, stop, emit, fast=True, out=out/name, prepared=prepared,
                bay_map={s['id']:s['bay_id'] for s in inventory(view)}, verification=True, service=service,
                verification_profile=profile)
            assert code == 0 and not issues, (name, code, issues)
            print(name, 'complete', flush=True)
    finally:
        service.close()
    validate(out, time.perf_counter()-started, args.baseline)


if __name__ == '__main__':
    main()
