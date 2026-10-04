"""Four policy ablations over exactly the same independently supplied labels.

This scorer never generates labels, geometry, or detector predictions. Unknown
and provisional outputs are separate from the definite confusion matrix.
"""
from collections import Counter, defaultdict
import statistics

from .opencv_first import after_yolo, before_yolo

DEFINITE = ('occupied', 'vacant')
METHODS = ('opencv_only', 'yolo_only', 'hybrid', 'hybrid_without_mobilenet')


def classical(reference, mog2):
    state, _, _, requested = before_yolo(reference, mog2, 'unknown')
    return 'uncertain' if requested else state


def predictions(row):
    reference, mog2, vehicle = (row[k] for k in ('reference_state', 'mog2_state', 'vehicle_state'))
    yolo = row['full_yolo_state']
    no_mobile, _, _ = after_yolo(reference, mog2, 'unknown', yolo)
    no_mobile_provisional = False
    if no_mobile not in DEFINITE and row.get('valid_frame') and yolo == 'uncertain':
        no_mobile, no_mobile_provisional = 'occupied', True
    return {
        'opencv_only': (classical(reference, mog2), False),
        'yolo_only': (yolo, False),
        'hybrid': (row['final_state'], bool(row.get('final_provisional'))),
        'hybrid_without_mobilenet': (no_mobile, no_mobile_provisional),
    }


def score(rows):
    """Confusion denominators exclude unknown truth and provisional decisions."""
    outputs = {}
    groups = defaultdict(list)
    for row in rows:
        if row['truth'] not in (*DEFINITE, 'unknown'):
            raise ValueError('Unknown truth label')
        groups[(row['view'], row['condition'])].append(row)
        groups[(row['view'], 'all')].append(row)
    for group, members in groups.items():
        methods = {}
        for method in METHODS:
            counts = Counter()
            request_bays = 0
            times = []
            for row in members:
                state, provisional = predictions(row)[method]
                truth = row['truth']
                counts['observations'] += 1
                counts['labelled_binary'] += truth in DEFINITE
                counts['truth_occupied'] += truth == 'occupied'
                counts['truth_vacant'] += truth == 'vacant'
                counts['visually_indeterminate'] += truth == 'unknown'
                counts['provisional'] += provisional
                counts['uncertain_or_unknown'] += state not in DEFINITE
                counts['vacant_on_indeterminate'] += truth == 'unknown' and state == 'vacant'
                if truth in DEFINITE and state in DEFINITE and not provisional:
                    counts['definite'] += 1
                    counts[f'{truth}_to_{state}'] += 1
                if method == 'yolo_only':
                    request_bays += int(bool(row.get('valid_frame')))
                    cost = row.get('full_yolo_ms')
                elif method == 'hybrid':
                    request_bays += int(bool(row.get('yolo_requested')))
                    cost = sum(float(row.get(k) or 0) for k in ('reference_ms', 'mog2_ms', 'vehicle_ms', 'yolo_ms'))
                elif method == 'hybrid_without_mobilenet':
                    request_bays += int(before_yolo(row['reference_state'], row['mog2_state'], 'unknown')[3])
                    cost = sum(float(row.get(k) or 0) for k in ('reference_ms', 'mog2_ms'))
                    if before_yolo(row['reference_state'], row['mog2_state'], 'unknown')[3]:
                        cost += float(row.get('full_yolo_ms') or 0)
                else:
                    cost = sum(float(row.get(k) or 0) for k in ('reference_ms', 'mog2_ms'))
                if cost is not None:
                    times.append(float(cost))
            occupied = counts['occupied_to_occupied'] + counts['occupied_to_vacant']
            vacant = counts['vacant_to_vacant'] + counts['vacant_to_occupied']
            predicted_vacant = counts['vacant_to_vacant'] + counts['occupied_to_vacant']
            methods[method] = {'counts': dict(counts), 'confusion': {
                'true_occupied_pred_occupied': counts['occupied_to_occupied'],
                'true_occupied_pred_vacant': counts['occupied_to_vacant'],
                'true_vacant_pred_occupied': counts['vacant_to_occupied'],
                'true_vacant_pred_vacant': counts['vacant_to_vacant']},
                'definite_coverage': counts['definite'] / counts['labelled_binary'] if counts['labelled_binary'] else None,
                'false_vacant_rate': counts['occupied_to_vacant'] / occupied if occupied else None,
                'false_occupied_rate': counts['vacant_to_occupied'] / vacant if vacant else None,
                'false_vacant_over_all_occupied': counts['occupied_to_vacant'] / counts['truth_occupied']
                    if counts['truth_occupied'] else None,
                'false_occupied_over_all_vacant': counts['vacant_to_occupied'] / counts['truth_vacant']
                    if counts['truth_vacant'] else None,
                'vacancy_prediction_reliability': counts['vacant_to_vacant'] / predicted_vacant if predicted_vacant else None,
                'yolo_requested_bay_observations': request_bays,
                'processing_ms_median': statistics.median(times) if times else None,
                'processing_ms_p95': sorted(times)[min(len(times)-1, int(.95 * len(times)))] if times else None}
        outputs[f'{group[0]}:{group[1]}'] = {'observations': len(members), 'methods': methods}
    return outputs
