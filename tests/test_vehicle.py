from copy import deepcopy

import numpy as np
import pytest

from parking_probe.config import polygon_signature
from parking_probe.sources import Frame, utcnow
from parking_probe.vehicle import VehicleBranch, classify_bays, deduplicate, final_decision
from parking_probe.vision import Analyzer
from parking_probe.interface_model import chart_data


SLOTS = [{'id':'A', 'polygon':[[10,10],[90,10],[90,90],[10,90]]},
         {'id':'B', 'polygon':[[100,10],[180,10],[180,90],[100,90]]}]


def detection(box, score=.9):
    return {'box':box, 'detector_score':score, 'class':'car'}


def test_missing_detection_needs_reviewed_empty_appearance():
    rows = classify_bays(SLOTS, [], {}, {})
    assert [s['state'] for s in rows] == ['uncertain','uncertain']
    rows = classify_bays(SLOTS, [], {'A':.01, 'B':.2}, {'A':.02,'B':.02})
    assert [s['state'] for s in rows] == ['vacant','uncertain']


def test_vehicle_assigned_to_one_bay_and_weak_or_ambiguous_boxes_block_vacancy():
    rows = classify_bays(SLOTS, [detection([25,15,80,85])], {'B':0}, {'B':.02})
    assert [s['state'] for s in rows] == ['occupied','vacant']
    rows = classify_bays(SLOTS, [detection([25,15,80,85],.4)], {'A':0}, {'A':.02})
    assert rows[0]['state'] == 'uncertain'
    # A bounding box spanning both slots cannot be counted as two parked cars.
    rows = classify_bays(SLOTS, [detection([15,10,175,90])], {'A':0,'B':0}, {'A':.02,'B':.02})
    assert [s['state'] for s in rows] == ['uncertain','uncertain']
    hidden = [{**SLOTS[0], 'visibility':'occluded'}]
    assert classify_bays(hidden,[],{'A':0},{'A':.02})[0]['state'] == 'unknown'


def test_nested_tile_detections_are_not_duplicate_cars():
    full = detection([10,10,180,180],.99)
    fragment = detection([15,100,175,175],.85)
    separate = detection([200,15,280,180],.92)
    assert deduplicate([fragment,separate,full]) == [full,separate]


@pytest.mark.parametrize('ref,mog,vehicle,expected', [
    ('unknown','unknown','occupied','occupied'), ('unknown','uncertain','vacant','vacant'),
    ('occupied','vacant','occupied','uncertain'), ('vacant','vacant','occupied','uncertain'),
    ('vacant','uncertain','occupied','uncertain'), ('vacant','vacant','unknown','vacant'),
    ('unknown','unknown','unknown','unknown'), ('unknown','unknown','uncertain','uncertain'),
])
def test_final_decision_retains_definite_conflicts(ref,mog,vehicle,expected):
    assert final_decision(ref,mog,vehicle)[0] == expected


def test_frame_failure_and_model_failure_do_not_invent_vacancies(config, scene):
    analyzer = Analyzer(config)
    class MissingCar:
        def detect(self,image): return []
    branch = VehicleBranch(analyzer,MissingCar())
    checked = analyzer.failure('camera_view_changed')
    result = branch.analyze(scene[2](1),checked)
    assert all(s['state']=='unknown' for s in result['slots'])
    assert result['summary']['occupancy_pct'] is None
    for invalid in ({**checked, 'error':None}, {**checked, 'analysis_status':'estimated', 'error':None, 'stale':True}):
        result = branch.analyze(scene[2](1), invalid)
        assert all(s['state']=='unknown' for s in result['slots'])
        assert result['summary']['occupancy_pct'] is None
    frame = Frame(scene[2](1),utcnow())
    branch.detector = None
    result = branch.analyze(frame.image,analyzer.analyze(frame))
    assert result['error']=='vehicle_model_unavailable'


def test_empty_match_provenance_and_changed_reference_are_enforced(config, scene):
    analyzer = Analyzer(config)
    slot = config.data['slots'][0]
    slot['vehicle_empty_match'] = {'max_difference':.02,'vacant_examples':5,
        'reference_pixel_hash':analyzer.reference_hashes['P01'], 'setup_pixel_hash':analyzer.setup_hash,
        'polygon_signature':polygon_signature(slot['polygon'])}
    branch = VehicleBranch(analyzer,None)
    assert branch.empty_limits == {'P01':.02}
    slot['vehicle_empty_match']['reference_pixel_hash'] = 'wrong-reference'
    assert not VehicleBranch(analyzer,None).empty_limits


def test_chart_uses_saved_final_evidence_and_preserves_method_columns():
    pair={'rows':[{'bay_id':'P009','reference_state':'unknown','mog2_state':'unknown',
                  'vehicle_state':'occupied','final_state':'occupied'}]}
    rows, summary = chart_data(pair,['P009'])
    assert rows[0]['reference_state']=='unknown'
    assert summary['occupied']==1 and summary['occupancy_pct']==100
