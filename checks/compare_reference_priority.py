"""Opt-in post-hoc comparison of frozen PKLot predictions; never runs inference."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parking_probe.alternate_policy import final_decision_reference_priority, ALTERNATE_POLICY
from parking_probe.config import atomic_json
from parking_probe.evaluation import ClassificationMetrics
from parking_probe.yolo import final_decision


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(output):
    source = ROOT / 'runs/verification/pklot'
    output = Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Output must be separate from the frozen experiment.')
    frozen_path = source / 'frozen.json'
    frozen, identity = read(frozen_path), sha(frozen_path)
    files = {frozen_path, source / 'evaluation.json', ROOT / 'data/pklot/partitions.json'}
    # Verify the original code as archived BEFORE adding the alternate path.
    # Do not change the freeze to match today's additive comparison/UI code.
    archive = ROOT / 'runs/verification/reference-priority/frozen-source'
    for name, digest in frozen['code'].items():
        path = archive / name
        if sha(path) != digest:
            raise ValueError('Original frozen source archive failed integrity: ' + name)
        files.add(path)
    for name, digest in frozen['artifacts'].items():
        path = ROOT / 'data/pklot' / name
        if sha(path) != digest:
            raise ValueError('Frozen calibration artifact changed: ' + name)
        files.add(path)
    for split in ('calibrate', 'test'):
        files.update((source / split).glob('*.json'))
    fingerprints = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sorted(files)}
    config = read(ROOT / 'data/pklot/experiment/config.json')
    calibrated = {s['id'] for s in config['slots'] if s.get('calibration', {}).get('status') == 'calibrated'}
    partitions = read(ROOT / 'data/pklot/partitions.json')
    prior_report = read(source / 'evaluation.json')
    if prior_report['frozen_sha256'] != identity:
        raise ValueError('Saved evaluation and freeze identity differ.')
    profile = frozen['selected_profile']  # Use the pre-test selection; never select again.
    results, exported, primary_checks = {}, [], 0
    for split in ('calibrate', 'test'):
        primary, alternate, transitions, conflicts = ClassificationMetrics(), ClassificationMetrics(), Counter(), 0
        seen = set()
        paths = sorted((source / split).glob('*.json'))
        expected = {r['frame_id']: r for r in partitions['partitions'][split]}
        expected_frames = set(expected)
        seen_frames = set()
        for path in paths:
            files.add(path)
            day = read(path)
            expected_identity = identity if split == 'test' else frozen['calibrate_identity']
            if day['identity'] != expected_identity:
                raise ValueError('Checkpoint identity does not match freeze: ' + str(path))
            for frame in day['frames']:
                if frame['frame_id'] in seen_frames:
                    raise ValueError('Duplicate checkpoint frame.')
                seen_frames.add(frame['frame_id'])
                if frame['frame_id'] not in expected:
                    raise ValueError('Unexpected frame outside the frozen partition.')
                labels = expected[frame['frame_id']]['labels']
                if {row['slot_id']: row['truth'] for row in frame['observations']} != labels:
                    raise ValueError('Saved observation truth differs from the original partition.')
                for row in frame['observations']:
                    key = (frame['frame_id'], row['slot_id'])
                    if key in seen:
                        raise ValueError('Duplicate labelled observation.')
                    seen.add(key)
                    states = row['states']
                    ref, mog, yolo = states['reference'], states['mog2'], states['yolo_' + profile]
                    current, reason = final_decision(ref, mog, yolo)
                    if current != states['final_' + profile] or reason != row['reasons']['final_' + profile]:
                        raise ValueError('Stored primary prediction does not match original policy.')
                    alt = final_decision_reference_priority(ref, mog, yolo, reference_calibrated=row['slot_id'] in calibrated)
                    primary.add(row['truth'], current); alternate.add(row['truth'], alt['state'])
                    primary_checks += 1
                    if current != alt['state']:
                        transitions[current + ' -> ' + alt['state']] += 1
                    conflicts += int(yolo == 'occupied' and alt['state'] == 'vacant')
                    exported.append({'partition': split, 'frame_id': frame['frame_id'], 'slot_id': row['slot_id'],
                        'truth': row['truth'], 'profile': profile, 'reference_calibrated': row['slot_id'] in calibrated,
                        'reference_state': ref, 'mog2_state': mog, 'yolo_state': yolo,
                        'final_state': current, 'final_reason': reason,
                        'final_confirmed_by': {'opencv_branches_agree': 'reference_and_mog2', 'yolov8_verified_vehicle': 'yolov8'}.get(reason),
                        'final_alt_state': alt['state'], 'final_alt_reason': alt['reason'],
                        'final_alt_confirmed_by': alt['confirmed_by'], 'final_alt_policy': ALTERNATE_POLICY,
                        'final_alt_experimental': True, 'final_alt_is_primary': False})
        if seen_frames != expected_frames:
            raise ValueError('Saved checkpoint frame set does not match the frozen partition.')
        if primary.result() != prior_report[split]['methods']['final_' + profile]['all']:
            raise ValueError('Re-derived primary metrics do not match original report.')
        results[split] = {'frames': len(seen_frames), 'primary': primary.result(),
            'experimental_alternate': alternate.result(), 'state_changes': dict(transitions),
            'yolo_occupied_overridden_to_vacant': conflicts}
    report = {'schema_version': 1, 'experimental': True, 'primary': False, 'opt_in': True,
        'post_hoc_only': True, 'new_inference_count': 0, 'frozen_sha256': identity,
        'selected_profile_unchanged': profile, 'alternate_policy': ALTERNATE_POLICY,
        'reference_calibrated_bays': sorted(calibrated), 'primary_predictions_verified': primary_checks,
        'results': results, 'input_sha256': fingerprints,
        'alternate_source_sha256': sha(ROOT / 'src/parking_probe/alternate_policy.py'),
        'script_sha256': sha(Path(__file__)),
        'note': 'Policy designed after inspecting the original held-out results. This is a post-hoc comparison, not a new preregistered test.'}
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'pklot-reference-priority.json', report)
    with (output / 'pklot-observations.jsonl').open('w', encoding='utf-8') as handle:
        for row in exported:
            handle.write(json.dumps(row, allow_nan=False) + '\n')
    with (output / 'pklot-observations.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(exported[0])); writer.writeheader(); writer.writerows(exported)
    if any(sha(ROOT / p) != digest for p, digest in fingerprints.items()):
        raise ValueError('An input changed during post-hoc derivation.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'runs/verification/reference-priority')
    args = parser.parse_args()
    report = compare(args.out)
    print(json.dumps(report['results'], indent=2))
    print('Saved:', args.out / 'pklot-reference-priority.json')
