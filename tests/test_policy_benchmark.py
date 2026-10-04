from parking_probe.policy_benchmark import predictions, score


def test_four_policies_share_denominator_but_preserve_abstentions():
    rows = [
        dict(view='CHAD', condition='pedestrian', truth='vacant', reference_state='uncertain',
             mog2_state='uncertain', vehicle_state='vacant', full_yolo_state='uncertain',
             final_state='vacant', final_provisional=False, valid_frame=True, yolo_requested=False),
        dict(view='CHAD', condition='motorcycle', truth='occupied', reference_state='unknown',
             mog2_state='unknown', vehicle_state='occupied', full_yolo_state='occupied',
             final_state='occupied', final_provisional=False, valid_frame=True, yolo_requested=False),
        dict(view='CHAD', condition='occluded', truth='unknown', reference_state='unknown',
             mog2_state='unknown', vehicle_state='uncertain', full_yolo_state='uncertain',
             final_state='occupied', final_provisional=True, valid_frame=True, yolo_requested=True),
    ]
    result = score(rows)['CHAD:all']
    assert result['observations'] == 3
    hybrid = result['methods']['hybrid']
    assert hybrid['counts']['provisional'] == 1
    assert hybrid['counts']['definite'] == 2
    assert hybrid['definite_coverage'] == 1
    assert result['methods']['yolo_only']['counts']['definite'] == 1
    assert result['methods']['yolo_only']['yolo_requested_bay_observations'] == 3
    assert predictions(rows[0])['hybrid_without_mobilenet'] == ('occupied', True)
