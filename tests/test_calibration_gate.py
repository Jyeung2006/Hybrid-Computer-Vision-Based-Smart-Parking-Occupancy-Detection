from parking_probe.calibration_gate import review_candidate


def test_requires_both_states_and_non_regression():
    labels = {'a': {'bay_id': 'B01', 'truth': 'vacant'},
              'b': {'bay_id': 'B01', 'truth': 'occupied'}}
    old = {'a': 'unknown', 'b': 'occupied'}
    assert review_candidate('B01', labels, old, {'a': 'vacant', 'b': 'occupied'})['promote']
    assert not review_candidate('B01', labels, old, {'a': 'occupied', 'b': 'occupied'})['promote']
    assert not review_candidate('B01', labels, old, {'a': 'unknown', 'b': 'unknown'})['promote']
    assert not review_candidate('B01', {'a': labels['a']}, {'a': 'vacant'}, {'a': 'vacant'})['promote']
