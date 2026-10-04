"""Development-only guard for proposed per-bay Reference/MOG2 calibrations."""
from collections import Counter


def review_candidate(bay_id, labels, baseline, candidate):
    """Require both verified states and no extra development vehicle errors.

    The same observation IDs must be evaluated by both configurations. Unknown
    outputs count as coverage loss, never as a correct classification.
    """
    keys = sorted(k for k, row in labels.items() if row['bay_id'] == bay_id)
    if not keys or set(keys) != set(baseline) or set(keys) != set(candidate):
        return {'promote': False, 'reason': 'missing_or_unmatched_development_observations'}
    truth = Counter(labels[k]['truth'] for k in keys)
    if truth['occupied'] < 1 or truth['vacant'] < 1:
        return {'promote': False, 'reason': 'both_verified_states_required', 'truth': dict(truth)}
    def errors(predicted):
        return sum(predicted[k] in ('occupied', 'vacant') and predicted[k] != labels[k]['truth'] for k in keys)
    old, new = errors(baseline), errors(candidate)
    old_coverage = sum(baseline[k] in ('occupied', 'vacant') for k in keys)
    new_coverage = sum(candidate[k] in ('occupied', 'vacant') for k in keys)
    promote = new <= old and new_coverage >= old_coverage
    return {'promote': promote, 'reason': 'non_regression_passed' if promote else 'vehicle_error_or_coverage_regression',
        'truth': dict(truth), 'baseline_errors': old, 'candidate_errors': new,
        'baseline_definite': old_coverage, 'candidate_definite': new_coverage}
