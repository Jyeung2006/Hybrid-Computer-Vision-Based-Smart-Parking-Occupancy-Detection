"""Guarded vacancy can add evidence but cannot convert bad evidence into empty."""
from copy import deepcopy

import pytest

from parking_probe.config import polygon_signature
from parking_probe.interface_model import PlaybackGuard
from parking_probe.vacancy_guard import GuardedVacancy, near_vehicle_box
from parking_probe.vision import Analyzer, PREPROCESSING


def fixture_guard(config, reviewed=False, reference=True):
    slot = config.data['slots'][0]
    slot['mapping_status'] = 'reviewed_full_visible_inventory'
    if not reference:
        slot.pop('reference_image')
    analyzer = Analyzer(config)
    if reviewed:
        slot['vehicle_empty_match'] = {
            'vacant_examples': 5, 'max_difference': .04,
            'preprocessing': PREPROCESSING,
            'reference_pixel_hash': analyzer.reference_hashes[slot['id']],
            'setup_pixel_hash': analyzer.setup_hash,
            'polygon_signature': polygon_signature(slot['polygon']),
        }
    return GuardedVacancy(analyzer)


def observation(guard, image, position, *, recording='period-a', camera=None,
                ref='unknown', mog='uncertain', yolo_state='uncertain',
                yolo_reason='no_qualifying_detection_is_not_vacancy', detections=(),
                frame_ok=True, inference=True, base='uncertain', aligned=True,
                yolo_error=None, wrong_yolo_frame=False):
    slot_id = guard.analyzer.slot_config[0]['id']
    camera = camera or guard.analyzer.config.data['source_id']
    frame_id = f'{recording}-{position}'
    reference = {'source_id':camera, 'frame_id':frame_id, 'retrieval_status':'success',
                 'analysis_status':'estimated', 'stale':False, 'error':None,
                 'alignment':{'ok':aligned}, 'slots':[{'slot_id':slot_id,'state':ref}]}
    if not frame_ok:
        reference['stale'] = True
    mog2 = {'analysis_status':'estimated', 'error':None,
            'slots':[{'slot_id':slot_id,'state':mog}]}
    yolo = {'source_id':camera, 'frame_id':'wrong' if wrong_yolo_frame else frame_id,
            'analysis_status':'unavailable' if yolo_error else 'estimated',
            'error':yolo_error, 'inference_completed':inference,
            'detections':list(detections), 'slots':[{'slot_id':slot_id,
                'requested':True, 'state':yolo_state, 'reason':yolo_reason}]}
    row = {'slot_id':slot_id, 'reference_state':ref, 'mog2_state':mog,
           'reference_difference':None, 'final_state':base,
           'final_reason':'yolov8_did_not_resolve_occupancy', 'final_confirmed_by':None}
    guard.apply(recording, position, reference, mog2, yolo, image, [row])
    return row


def test_no_reference_is_explicitly_provisional_after_three(config, scene):
    guard = fixture_guard(config, reference=False)
    image = scene[0]
    results = [observation(guard, image, t) for t in (0, 3, 6)]
    assert [r['final_state'] for r in results] == ['uncertain','uncertain','vacant']
    assert [r['vacancy_guard_streak'] for r in results] == [1, 2, 3]
    assert results[-1]['final_provisional'] is True
    assert results[-1]['final_confirmed_by'] is None
    assert results[-1]['vacancy_evidence'] == 'provisional_repeated_no_detection'


def test_reviewed_empty_match_and_mismatch(config, scene):
    guard = fixture_guard(config, reviewed=True)
    empty = scene[0]
    occupied = scene[2](occupied=('P01',))
    assert observation(guard, empty, 0)['vacancy_guard_streak'] == 1
    mismatch = observation(guard, occupied, 3)
    assert mismatch['final_state'] == 'uncertain'
    assert mismatch['vacancy_guard_reason'] == 'reviewed_empty_mismatch'
    assert mismatch['vacancy_reference_difference'] > mismatch['vacancy_reference_limit']
    results = [observation(guard, empty, t) for t in (6, 9, 12)]
    assert [r['vacancy_guard_streak'] for r in results] == [1, 2, 3]
    assert results[-1]['final_state'] == 'vacant'
    assert results[-1]['final_provisional'] is False
    assert results[-1]['final_confirmed_by'] == 'reviewed_empty_and_three_clean_no_detections'


@pytest.mark.parametrize('change,reason', [
    ({'ref':'occupied'}, 'classic_occupied_or_conflicting_evidence'),
    ({'ref':'occupied','mog':'vacant'}, 'classic_occupied_or_conflicting_evidence'),
    ({'yolo_state':'occupied','yolo_reason':'qualifying_yolov8_vehicle_in_unique_bay'}, 'vehicle_overlap_or_verification_unavailable'),
    ({'yolo_reason':'weak_or_ambiguous_yolov8_vehicle'}, 'vehicle_overlap_or_verification_unavailable'),
    ({'frame_ok':False}, 'frame_or_model_unusable'),
    ({'inference':False}, 'frame_or_model_unusable'),
    ({'aligned':False}, 'frame_or_model_unusable'),
    ({'yolo_error':'model_failed'}, 'frame_or_model_unusable'),
    ({'wrong_yolo_frame':True}, 'frame_or_model_unusable'),
    ({'image':None}, 'frame_or_model_unusable'),
    ({'detections':({'box':[95,145,105,155],'detector_score':.2,'class':'car'},)}, 'weak_or_nearby_vehicle_box'),
])
def test_bad_middle_observation_resets_streak(config, scene, change, reason):
    guard = fixture_guard(config, reference=False)
    assert observation(guard, scene[0], 0)['vacancy_guard_streak'] == 1
    options = dict(change)
    middle = observation(guard, options.pop('image', scene[0]), 3, **options)
    assert middle['vacancy_guard_reason'] == reason
    assert middle['final_state'] != 'vacant'
    assert [observation(guard, scene[0], t)['vacancy_guard_streak'] for t in (6,9,12)] == [1,2,3]


def test_occluded_or_unreviewed_mapping_blocks_vacancy(config, scene):
    guard = fixture_guard(config, reference=False)
    guard.slots['P01']['visibility'] = 'occluded'
    assert observation(guard, scene[0], 0)['vacancy_guard_reason'] == 'bay_visibility_not_reviewed_or_occluded'
    guard.slots['P01']['visibility'] = 'visible'
    guard.slots['P01']['mapping_status'] = 'unverified'
    assert observation(guard, scene[0], 3)['vacancy_guard_reason'] == 'bay_visibility_not_reviewed_or_occluded'


def test_recording_camera_gaps_replay_and_backwards_reset(config, scene):
    guard = fixture_guard(config, reference=False)
    image = scene[0]
    assert [observation(guard,image,t)['vacancy_guard_streak'] for t in (0,3)] == [1,2]
    assert observation(guard,image,9)['vacancy_guard_streak'] == 1
    assert observation(guard,image,6)['vacancy_guard_streak'] == 1
    assert observation(guard,image,6)['vacancy_guard_streak'] == 1
    assert observation(guard,image,0,recording='period-b')['vacancy_guard_streak'] == 1
    assert observation(guard,image,0,camera='other-camera')['vacancy_guard_streak'] == 1
    assert observation(guard,image,3,camera='other-camera')['vacancy_guard_streak'] == 2
    guard.reset()
    assert observation(guard,image,0)['vacancy_guard_streak'] == 1


def test_definite_base_result_is_unchanged(config, scene):
    guard = fixture_guard(config, reference=False)
    row = observation(guard,scene[0],0,ref='vacant',mog='vacant',base='vacant')
    assert row['final_state'] == 'vacant'
    assert row['final_provisional'] is False
    assert row['vacancy_guard_reason'] == 'existing_definite_route'


def test_configured_reference_without_reviewed_match_cannot_use_provisional_path(config, scene):
    guard = fixture_guard(config, reviewed=False, reference=True)
    rows = [observation(guard,scene[0],t) for t in (0,3,6)]
    assert all(r['final_state']=='uncertain' for r in rows)
    assert all(r['vacancy_guard_reason']=='reviewed_empty_match_unavailable' for r in rows)


def test_weak_detection_near_edge_blocks(config):
    polygon = config.data['slots'][0]['polygon']
    assert near_vehicle_box(polygon,[{'box':[95,145,105,155]}])
    assert not near_vehicle_box(polygon,[{'box':[10,10,20,20]}])


def test_gui_playback_restarts_three_sample_guard_after_seek(config, scene):
    guard = fixture_guard(config, reference=False)
    player = PlaybackGuard()
    pairs=[]
    for time in (0,3,6):
        row = observation(guard,scene[0],time)
        pairs.append({'recording_id':'period-a', 'reference':{'source_id':guard.analyzer.config.data['source_id'],
                      'sample_time_seconds':time,'frame_id':f'period-a-{time}'},
                      'rows':[{'bay_id':'P01',**deepcopy(row)}]})
    assert [player.observe(p)['rows'][0]['final_state'] for p in pairs] == ['uncertain','uncertain','vacant']
    player.reset()
    assert player.observe(pairs[-1])['rows'][0]['final_state'] == 'uncertain'
    assert player.observe(pairs[0])['rows'][0]['final_state'] == 'uncertain'
