"""Saved-log diagnostic only: no frames, inference, calibration or accuracy claims."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parking_probe.alternate_policy import add_alternate, DEFINITE
from parking_probe.config import atomic_json
from parking_probe.yolo import final_decision

DEFAULT_RUN = ROOT / 'runs/areas/20260921T161408_115721Z'
LIMITATION = 'CHAD/overhead have no independent labels beyond the calibration set; this measures agreement and coverage, not accuracy.'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentage(n, d):
    return 100 * n / d if d else None


def contribution(rows):
    overlap = [r for r in rows if r['reference_state'] in DEFINITE and r['mog2_state'] in DEFINITE]
    agree = sum(r['reference_state'] == r['mog2_state'] for r in overlap)
    mog_only = sum(r['mog2_state'] in DEFINITE and r['reference_state'] not in DEFINITE for r in rows)
    ref_only = sum(r['reference_state'] in DEFINITE and r['mog2_state'] not in DEFINITE for r in rows)
    classic = [r for r in rows if r['final_confirmed_by'] == 'reference_and_mog2']
    no_other = sum(not r['yolo_requested'] or r['yolo_state'] != 'occupied' for r in classic)
    primary, alternate = Counter(r['final_state'] for r in rows), Counter(r['final_alt_state'] for r in rows)
    return {'observations': len(rows), 'overlapping_definite': len(overlap), 'agreeing_definite': agree,
        'agreement_pct_of_overlapping_definite': percentage(agree, len(overlap)),
        'mog2_only_definite': mog_only, 'mog2_only_pct_of_all_selected': percentage(mog_only, len(rows)),
        'reference_only_definite': ref_only, 'reference_only_pct_of_all_selected': percentage(ref_only, len(rows)),
        'primary_reference_and_mog2_confirmations': len(classic),
        'classic_confirmations_without_alternate_recorded_route': no_other,
        'primary_states': dict(primary), 'experimental_alternate_states': dict(alternate),
        'primary_coverage_pct': percentage(sum(primary[s] for s in DEFINITE), len(rows)),
        'experimental_alternate_coverage_pct': percentage(sum(alternate[s] for s in DEFINITE), len(rows)),
        'state_changes': dict(Counter(f"{r['final_state']} -> {r['final_alt_state']}" for r in rows if r['final_state'] != r['final_alt_state'])),
        'accuracy': None, 'false_vacant_rate': None, 'ground_truth_limitation': LIMITATION}


def diagnose(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    if output == run or run in output.parents:
        raise ValueError('Choose an output outside the original replay directory.')
    fingerprints, selected, inventory, seen = {}, [], {}, set()
    for site_path in sorted(run.rglob('site.json')):
        site = json.loads(site_path.read_text(encoding='utf-8'))
        config_path = Path(site['reference_config'])
        # Stored absolute paths are preferred; permit a moved project with the same data suffix.
        if not config_path.exists():
            config_path = ROOT / 'data' / str(config_path).split('data\\', 1)[1]
        config = json.loads(config_path.read_text(encoding='utf-8'))
        mog_path = site_path.parent / 'mog2-calibration.json'
        mog = json.loads(mog_path.read_text(encoding='utf-8'))
        if mog['model_signature'] != site['mog2_signature']:
            raise ValueError('Saved MOG2 calibration does not match this replay.')
        ref_set = {s['id'] for s in config['slots'] if s.get('calibration', {}).get('status') == 'calibrated'}
        mog_set = {k for k, v in mog['slots'].items() if v.get('status') == 'calibrated'}
        calibrated = ref_set & mog_set
        inventory[site['camera_id']] = {'reference': sorted(ref_set), 'mog2': sorted(mog_set),
                                      'selected_bays': sorted(calibrated), 'configured_bays': len(config['slots'])}
        history = site_path.parent / 'history.jsonl'
        for path in (site_path, config_path, mog_path, history):
            fingerprints[str(path)] = sha(path)
        for line in history.read_text(encoding='utf-8').splitlines():
            for pair in json.loads(line).get('recordings', []):
                if pair['mog2']['model_signature'] != site['mog2_signature']:
                    raise ValueError('Observation model signature differs from its calibration.')
                enriched = add_alternate(pair, ref_set)
                for row in enriched['rows']:
                    if row['slot_id'] not in calibrated:
                        continue
                    identity = tuple(row[k] for k in ('camera_id', 'recording_id', 'frame_id', 'slot_id'))
                    if identity in seen:
                        raise ValueError('Duplicate observation in input history.')
                    seen.add(identity)
                    expected = final_decision(row['reference_state'], row['mog2_state'], row['yolo_state'])
                    if expected != (row['final_state'], row['final_reason']):
                        raise ValueError('Replay does not use the current primary Final rule.')
                    selected.append(row)
    if not selected:
        raise ValueError('No observations of jointly calibrated bays found.')
    groups = defaultdict(list)
    for row in selected:
        groups[row['camera_id']].append(row)
    report = {'schema_version': 1, 'input_run': str(run), 'scope': 'currently jointly calibrated bays only',
        'experimental_comparison_opt_in': True, 'primary_policy_unchanged': True,
        'ground_truth_limitation': LIMITATION,
        'counterfactual_note': 'Remove the classic agreement route, leaving only actually recorded YOLO confirmation. '
            'YOLO was skipped on classic agreement; an unrun detector outcome is unknowable. '
            'This is not proof those decisions require MOG2 under every possible policy.',
        'percentage_denominators': 'Agreement uses overlapping definite observations; one-branch percentages use all selected observations.',
        'inventory': inventory, 'all': contribution(selected),
        'by_camera': {k: contribution(v) for k, v in groups.items()},
        'by_bay': {bay: contribution([r for r in selected if r['bay_id'] == bay]) for bay in sorted({r['bay_id'] for r in selected})},
        'input_sha256': fingerprints}
    assert all(sha(Path(p)) == digest for p, digest in fingerprints.items())
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'mog2-contribution.json', report)
    with (output / 'calibrated-bay-comparison.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader(); writer.writerows(selected)
    atomic_json(output / 'calibrated-bay-comparison.json', {'experimental': True, 'primary': False, 'rows': selected})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--out', type=Path, default=ROOT / 'runs/verification/reference-priority')
    args = parser.parse_args()
    result = diagnose(args.run, args.out)
    print(json.dumps({'selected_inventory': result['inventory'], 'by_camera': result['by_camera'], 'all': result['all']}, indent=2))
    print('Saved:', args.out / 'mog2-contribution.json')


if __name__ == '__main__':
    main()
