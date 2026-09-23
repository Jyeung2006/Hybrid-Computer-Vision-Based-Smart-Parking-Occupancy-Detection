from copy import deepcopy

import pytest

from parking_probe.config import polygon_signature
from parking_probe.empty_evidence import EmptyEvidence, VacancyConfirmation
from parking_probe.sources import Frame, utcnow
from parking_probe.vision import Analyzer, PREPROCESSING
from parking_probe.yolo import final_decision, associate


def prepared(config):
    analyzer = Analyzer(config)
    for slot in config.data['slots']:
        slot['vehicle_empty_match'] = {
            'vacant_examples': 5, 'max_difference': .012, 'preprocessing': PREPROCESSING,
            'reference_pixel_hash': analyzer.reference_hashes[slot['id']],
            'setup_pixel_hash': analyzer.setup_hash, 'polygon_signature': polygon_signature(slot['polygon']),
        }
    return Analyzer(config)


def observation(analyzer, image, detections=()):
    ref = analyzer.analyze(Frame(image, utcnow(), frame_id='f1'))
    mog = deepcopy(ref)
    result = {'inference_completed': True, 'error': None,
              'slots': associate(analyzer.slot_config, detections, {'P01','P02'}, .5)}
    return ref, mog, result


def test_verified_empty_matches_but_a_missed_parked_car_does_not(config, scene):
    analyzer = prepared(config); bank = EmptyEvidence(analyzer)
    image = scene[2](2, occupied=('P01',))
    ref, mog, verification = observation(analyzer, image)
    results = bank.candidates(image, ref, mog, verification)
    assert not results['P01']['candidate']  # Detector missed it; appearance catches it.
    assert results['P01']['reason'] == 'does_not_match_reviewed_empty'
    assert results['P02']['candidate']


@pytest.mark.parametrize('field,value', [('vacant_examples',4), ('max_difference',float('nan')),
    ('max_difference',.2), ('setup_pixel_hash','wrong'), ('reference_pixel_hash','wrong'),
    ('polygon_signature','wrong'), ('preprocessing','different')])
def test_untrusted_empty_metadata_cannot_create_vacancy(config, scene, field, value):
    analyzer = prepared(config)
    analyzer.slot_config[0]['vehicle_empty_match'][field] = value
    assert 'P01' not in EmptyEvidence(analyzer).banks


@pytest.mark.parametrize('kind', ['weak_box','occupied_classic','yolo_error','stale','missing_reference'])
def test_conflicting_or_unavailable_evidence_blocks_vacancy(config, scene, kind):
    analyzer = prepared(config); image = scene[2](2)
    detections = [{'box':[110,160,230,290], 'detector_score':.3}] if kind == 'weak_box' else []
    ref, mog, verification = observation(analyzer, image, detections)
    if kind == 'occupied_classic': mog['slots'][0]['state'] = 'occupied'
    if kind == 'yolo_error': verification.update(error='failed', inference_completed=False)
    if kind == 'stale': ref['stale'] = True
    if kind == 'missing_reference': analyzer.slot_config[0].pop('vehicle_empty_match')
    assert not EmptyEvidence(analyzer).candidates(image, ref, mog, verification)['P01']['candidate']


def candidates(good=True):
    return {'A': {'candidate': good, 'reason':'test', 'difference':.001, 'limit':.012}}


def test_three_distinct_consecutive_samples_and_immediate_revocation():
    tracker = VacancyConfirmation()
    assert not tracker.update(0,'f0',candidates())['A']['confirmed']
    assert not tracker.update(3,'f1',candidates())['A']['confirmed']
    assert tracker.update(6,'f2',candidates())['A']['confirmed']
    assert not tracker.update(9,'f3',candidates(False))['A']['confirmed']
    assert tracker.update(12,'f4',candidates())['A']['consecutive_samples'] == 1


@pytest.mark.parametrize('time,frame', [(30,'next'), (0,'back'), (6,'f1')])
def test_gap_backward_seek_or_duplicate_frame_resets_confirmation(time, frame):
    tracker = VacancyConfirmation()
    tracker.update(0,'f0',candidates()); tracker.update(3,'f1',candidates())
    assert tracker.update(time,frame,candidates())['A']['consecutive_samples'] == 1
    assert VacancyConfirmation().update(6,'other',candidates())['A']['consecutive_samples'] == 1


def test_classic_vacancy_supports_streak_but_final_agreement_is_always_kept():
    tracker = VacancyConfirmation()
    classic = {'A': {'candidate':False, 'supports_vacancy':True}}
    tracker.update(0,'f0',classic); tracker.update(3,'f1',classic)
    assert tracker.update(6,'f2',candidates())['A']['confirmed']
    # A confirmed diagnostic match must not become a hidden final-state input.
    assert final_decision('vacant','vacant','occupied')[0] == 'vacant'
    assert final_decision('occupied','occupied','uncertain')[0] == 'occupied'
    assert final_decision('unknown','uncertain','uncertain')[0] == 'uncertain'
    assert final_decision('occupied','uncertain','uncertain')[0] == 'uncertain'
    assert final_decision('unknown','unknown','unknown')[0] == 'unknown'
    assert final_decision('unknown','unknown','occupied')[0] == 'occupied'
