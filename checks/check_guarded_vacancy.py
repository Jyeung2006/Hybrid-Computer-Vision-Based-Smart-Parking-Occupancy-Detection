"""Replay every mapped view and compare guarded Final to the saved strict baseline."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parking_probe.areas import VIEWS, EXTRA_VIEWS, OVERHEAD, inventory, fetch_overhead
from parking_probe.catalog import CLIPS
from parking_probe.comparison import run_comparison
from parking_probe.monitor import prepare_preset
from parking_probe.view_presets import prepare_view
from parking_probe.vacancy_guard import GUARDED_DECISION_POLICY
from parking_probe.yolo import YOLODetector, VerificationService

BASELINE = ROOT / 'runs/areas/20260922T152412_835535Z'
REPORT = ROOT / 'runs/verification/guarded-vacancy-report.json'
STATES = ('occupied', 'vacant', 'uncertain', 'unknown')


def observations(directory):
    items = {}
    for path in directory.glob('*/history.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            for pair in json.loads(line).get('recordings', []):
                for row in pair['rows']:
                    key = (pair['recording_id'], row['frame_id'], row['slot_id'])
                    if key in items:
                        raise AssertionError(f'Duplicate observation: {key}')
                    items[key] = row
    return items


def compare(before_dir, after_dir, elapsed):
    before, after = observations(before_dir), observations(after_dir)
    if before.keys() != after.keys():
        missing = sorted(before.keys() - after.keys())[:5]
        extra = sorted(after.keys() - before.keys())[:5]
        raise AssertionError(f'Observation identity mismatch: missing={missing}, extra={extra}')
    counts = defaultdict(lambda: {'before':Counter(), 'after':Counter(), 'changes':Counter()})
    changed = defaultdict(lambda: {'count':0, 'from':Counter(), 'evidence':Counter(), 'frames':[]})
    method_differences = []
    invalid_changes = []
    for key, current in after.items():
        old = before[key]
        clip, frame, slot = key
        entry = counts[clip]
        entry['before'][old['final_state']] += 1
        entry['after'][current['final_state']] += 1
        if current['decision_policy'] != GUARDED_DECISION_POLICY:
            raise AssertionError(f'Wrong decision policy: {key}')
        for method in ('reference_state','mog2_state','yolo_state','yolo_reason','yolo_profile'):
            if old[method] != current[method]:
                method_differences.append({'key':key, 'method':method, 'old':old[method], 'new':current[method]})
        if old['final_state'] != current['final_state']:
            route = f"{old['final_state']} -> {current['final_state']}"
            entry['changes'][route] += 1
            detail = changed[(clip,current['bay_id'])]
            detail['count'] += 1
            detail['from'][old['final_state']] += 1
            detail['evidence'][current.get('vacancy_evidence') or 'none'] += 1
            detail['frames'].append(frame)
            if (old['final_state'] not in ('uncertain','unknown') or current['final_state'] != 'vacant'
                    or current['vacancy_guard_streak'] != 3 or current['final_reason'] not in (
                        'provisional_vacant_three_no_detections',
                        'guarded_vacant_reviewed_empty_three_no_detections')):
                invalid_changes.append({'key':key,'before':old['final_state'],'after':current['final_state']})
        if current.get('final_provisional') and (current['final_state'] != 'vacant' or current['final_confirmed_by'] is not None):
            invalid_changes.append({'key':key,'reason':'provisional_was_mislabelled'})
    if method_differences or invalid_changes:
        raise AssertionError(f'Method differences={method_differences[:5]}; invalid changes={invalid_changes[:5]}')
    by_view = {}
    for clip, entry in sorted(counts.items()):
        by_view[clip] = {'observations':sum(entry['after'].values()),
            'before':{s:entry['before'][s] for s in STATES},
            'after':{s:entry['after'][s] for s in STATES},
            'changes':dict(entry['changes'])}
    totals = {'before':{s:sum(v['before'][s] for v in by_view.values()) for s in STATES},
              'after':{s:sum(v['after'][s] for v in by_view.values()) for s in STATES}}
    changes = [{'recording_id':clip, 'bay_id':bay, 'changed_observations':d['count'],
                'from_states':dict(d['from']), 'reason_evidence':dict(d['evidence']),
                'frame_ids':d['frames']} for (clip,bay),d in sorted(changed.items())]
    window_checks = 0
    guard_durations = []
    for folder in after_dir.iterdir():
        if not folder.is_dir() or not (folder/'run.json').exists():
            continue
        if json.loads((folder/'run.json').read_text())['status'] != 'complete':
            raise AssertionError(f'Incomplete replay: {folder}')
        for line in (folder/'history.jsonl').read_text(encoding='utf-8').splitlines():
            guard_durations.extend(pair['final']['guard_processing_duration_ms']
                for pair in json.loads(line).get('recordings', []))
        for line in (folder/'windows.jsonl').read_text(encoding='utf-8').splitlines():
            window = json.loads(line)['final']
            observed = Counter(b['state'] for b in window['bays'])
            for state in STATES:
                if observed[state] != window['summary'][state]:
                    raise AssertionError(f'Window count mismatch: {folder}')
            window_checks += 1
        final = json.loads((folder/'final-summary.json').read_text(encoding='utf-8'))
        if final['decision_rule'] != GUARDED_DECISION_POLICY:
            raise AssertionError(f'Final summary policy mismatch: {folder}')
    return {'baseline':str(before_dir), 'replay':str(after_dir), 'elapsed_seconds':elapsed,
            'bay_observations':len(after), 'by_recording':by_view, 'totals':totals,
            'changed_bays':changes, 'checked_ten_second_or_partial_windows':window_checks,
            'guard_duration_ms_median':float(np.median(guard_durations)),
            'guard_duration_ms_p95':float(np.percentile(guard_durations,95)),
            'unchanged_reference_mog2_yolo':True,
            'independent_accuracy_measured':False,
            'accuracy_note':'No independently labelled frame set for these exact replay observations was supplied; false-vacant rate and accuracy are not established.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing-run', type=Path)
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    args = parser.parse_args()
    if not args.baseline.exists():
        raise SystemExit(f'Baseline missing: {args.baseline}')
    started = time.perf_counter()
    out = args.existing_run or ROOT/'runs/areas'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if not args.existing_run:
        stop = threading.Event()
        service = VerificationService(YOLODetector())
        try:
            for view in [VIEWS['chad-1'], *(VIEWS[c.id] for c in EXTRA_VIEWS), VIEWS['overhead-1']]:
                if view.site == 'overhead':
                    prepared = prepare_preset(lambda *args:None, stop, ROOT/'presets/overhead-all-bays.json',
                        [OVERHEAD], fetch_overhead, ROOT/'data/overhead-all')
                    clips, profile, name = [OVERHEAD], 'aerial', 'overhead'
                else:
                    prepared = prepare_view(view, lambda *args:None, stop, include_empty_evidence=True)
                    clips = CLIPS if view.camera == 'Camera 1' else [view.clip]
                    profile, name = 'coco', ('chad' if view.camera == 'Camera 1' else view.clip.id)
                issues=[]
                def emit(kind,value):
                    if kind == 'error': issues.append(value)
                code = run_comparison(clips, 3, stop, emit, fast=True, out=out/name, prepared=prepared,
                    bay_map={s['id']:s['bay_id'] for s in inventory(view)}, verification=True,
                    service=service, verification_profile=profile)
                if code or issues:
                    raise AssertionError((name,code,issues))
                print(name,'complete',flush=True)
        finally:
            service.close()
    report = compare(args.baseline,out,time.perf_counter()-started)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Guarded replay checked:',report['bay_observations'],'observations',flush=True)
    print('Before:',report['totals']['before'],flush=True)
    print('After:',report['totals']['after'],flush=True)
    print('Changed bays:',len(report['changed_bays']),flush=True)
    print(REPORT,flush=True)


if __name__ == '__main__':
    main()
