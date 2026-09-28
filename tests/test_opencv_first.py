"""The selected method, YOLO request and displayed source must agree."""
import pytest

from parking_probe.opencv_first import before_yolo, after_yolo, provisional_occupied_allowed
from parking_probe.interface_model import PlaybackGuard


@pytest.mark.parametrize('reference,mog2,mobilenet,requested,state,source', [
    ('vacant', 'vacant', 'occupied', False, 'vacant', 'reference_and_mog2'),
    ('occupied', 'uncertain', 'vacant', False, 'occupied', 'reference'),
    ('unknown', 'vacant', 'occupied', False, 'vacant', 'mog2'),
    ('unknown', 'uncertain', 'vacant', False, 'vacant', 'mobilenet_reviewed_empty'),
    ('uncertain', 'unknown', 'occupied', False, 'occupied', 'mobilenet_ssd'),
    ('occupied', 'vacant', 'uncertain', True, 'uncertain', None),
    ('unknown', 'uncertain', 'uncertain', True, 'uncertain', None),
])
def test_selection_before_yolo(reference, mog2, mobilenet, requested, state, source):
    result = before_yolo(reference, mog2, mobilenet)
    assert (result[0], result[2], result[3]) == (state, source, requested)


@pytest.mark.parametrize('reference,mog2,mobilenet,yolo,state,source', [
    ('vacant', 'uncertain', 'occupied', 'occupied', 'vacant', 'reference'),
    ('occupied', 'vacant', 'unknown', 'occupied', 'occupied', 'yolov8'),
    ('vacant', 'occupied', 'unknown', 'uncertain', 'vacant', 'reference'),
    ('occupied', 'vacant', 'unknown', 'unknown', 'occupied', 'reference'),
    ('unknown', 'uncertain', 'vacant', 'occupied', 'vacant', 'mobilenet_reviewed_empty'),
    ('unknown', 'uncertain', 'unknown', 'occupied', 'occupied', 'yolov8'),
    ('unknown', 'uncertain', 'unknown', 'uncertain', 'uncertain', None),
])
def test_yolo_cannot_override_resolved_opencv(reference, mog2, mobilenet, yolo, state, source):
    decision = after_yolo(reference, mog2, mobilenet, yolo)
    assert (decision[0], decision[2]) == (state, source)


def test_provisional_occupied_requires_valid_same_frame_verification():
    reference = {'analysis_status': 'estimated', 'stale': False, 'error': None,
                 'alignment': {'ok': True}}
    mog2 = {'analysis_status': 'estimated', 'error': None}
    yolo = {'inference_completed': True, 'error': None}
    slot = {'visibility': 'visible'}
    evidence = {'requested': True, 'state': 'uncertain'}
    args = [reference, mog2, yolo, object(), slot, evidence]
    assert provisional_occupied_allowed(*args)
    for index, changed in ((0, {'stale': True}), (1, {'error': 'mog2_failed'}),
                           (2, {'inference_completed': False}),
                           (4, {'visibility': 'occluded'}),
                           (5, {'requested': False}), (5, {'state': 'unknown'})):
        invalid = [dict(item) if isinstance(item, dict) else item for item in args]
        invalid[index].update(changed)
        assert not provisional_occupied_allowed(*invalid)
    assert not provisional_occupied_allowed(reference, mog2, yolo, None, slot, evidence)


def test_seeking_to_guarded_vacancy_uses_provisional_occupied_until_streak_rebuilds():
    pair = {'recording_id': 'clip',
            'reference': {'source_id': 'camera', 'frame_id': 'frame-6', 'sample_time_seconds': 6},
            'rows': [{'slot_id': 'B01', 'bay_id': 'P001', 'final_state': 'vacant',
                      'final_reason': 'guarded_vacant_reviewed_empty_three_no_detections',
                      'final_confirmed_by': 'reviewed_empty_and_three_clean_no_detections',
                      'final_provisional': False, 'base_final_state': 'uncertain',
                      'base_final_reason': 'opencv_and_yolov8_unresolved',
                      'base_final_confirmed_by': None,
                      'pre_guard_fallback_state': 'occupied',
                      'pre_guard_fallback_reason': 'provisional_occupied_no_definite_evidence',
                      'vacancy_evidence': 'reviewed_empty_and_three_clean_no_detections',
                      'vacancy_guard_reason': 'reviewed_empty_and_three_clean_no_detections'}],
            'final': {'slots': [{'slot_id': 'B01', 'state': 'vacant', 'reason': 'guarded_vacant',
                                 'provisional': False}]}}
    shown = PlaybackGuard().observe(pair)
    assert shown['rows'][0]['final_state'] == 'occupied'
    assert shown['rows'][0]['final_provisional'] is True
    assert shown['final']['slots'][0]['state'] == 'occupied'
    assert shown['final']['summary']['provisional_occupied'] == 1
