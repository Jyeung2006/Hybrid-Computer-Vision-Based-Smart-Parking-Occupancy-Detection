"""Independent saved-result arithmetic and protected-file audit; no inference."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/verification/reference-priority'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protected = read(OUT / 'protected-before.json')
    protected.update(read(ROOT / 'runs/verification/pklot-protected-before.json'))
    changed = [name for name, digest in protected.items() if sha(ROOT / name) != digest]
    assert not changed, changed
    report = read(OUT / 'pklot-reference-priority.json')
    for name, digest in report['input_sha256'].items():
        assert sha(ROOT / name) == digest, name
    assert sha(ROOT / 'src/parking_probe/alternate_policy.py') == report['alternate_source_sha256']
    rows = [json.loads(line) for line in (OUT / 'pklot-observations.jsonl').read_text().splitlines()]
    for split in ('calibrate', 'test'):
        selected = [r for r in rows if r['partition'] == split]
        for row in selected:
            ref, mog, yolo = (row[k] for k in ('reference_state', 'mog2_state', 'yolo_state'))
            primary = (ref if ref == mog and ref in ('vacant', 'occupied') else
                       'occupied' if yolo == 'occupied' else
                       'unknown' if ref == mog == yolo == 'unknown' else 'uncertain')
            alternate = ref if row['reference_calibrated'] and ref in ('vacant', 'occupied') else primary
            assert row['final_state'] == primary and row['final_alt_state'] == alternate
            assert row['final_alt_experimental'] and not row['final_alt_is_primary']
        for key, field in (('primary', 'final_state'), ('experimental_alternate', 'final_alt_state')):
            counts = Counter((r['truth'], r[field]) for r in selected)
            metric = report['results'][split][key]
            for truth, predictions in metric['confusion_matrix'].items():
                for state, number in predictions.items():
                    assert counts[truth, state] == number
            tp, tn, fn, fp = (counts[t, s] for t, s in [('occupied', 'occupied'), ('vacant', 'vacant'),
                                                       ('occupied', 'vacant'), ('vacant', 'occupied')])
            classified = tp + tn + fn + fp
            assert abs(metric['decision_coverage_pct'] - 100 * classified / len(selected)) < 1e-10
            assert abs(metric['accuracy_on_classified_pct'] - 100 * (tp + tn) / classified) < 1e-10
            assert abs(metric['false_vacant_rate_on_classified_occupied_pct'] - 100 * fn / (tp + fn)) < 1e-10
    diagnostic = read(OUT / 'mog2-contribution.json')
    for name, digest in diagnostic['input_sha256'].items():
        assert sha(Path(name)) == digest
    calibrated = read(OUT / 'calibrated-bay-comparison.json')['rows']
    assert len(calibrated) == 147
    overlap = [r for r in calibrated if r['reference_state'] in ('occupied', 'vacant') and r['mog2_state'] in ('occupied', 'vacant')]
    assert len(overlap) == 101 and all(r['reference_state'] == r['mog2_state'] for r in overlap)
    assert sum(r['mog2_state'] in ('occupied', 'vacant') and r['reference_state'] not in ('occupied', 'vacant') for r in calibrated) == 10
    assert sum(r['reference_state'] in ('occupied', 'vacant') and r['mog2_state'] not in ('occupied', 'vacant') for r in calibrated) == 22
    assert sum(r['final_state'] != r['final_alt_state'] for r in calibrated) == 9
    assert diagnostic['all']['accuracy'] is None and diagnostic['all']['false_vacant_rate'] is None
    result = {'status': 'passed', 'protected_files_unchanged': len(protected),
        'pklot_observations_independently_checked': len(rows), 'calibrated_replay_observations_checked': len(calibrated),
        'primary_policy_unchanged': True, 'freeze_and_original_predictions_unchanged': True,
        'new_inference_count': 0, 'matrices_and_rates_checked': True}
    (OUT / 'delivery-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
