import pytest

from parking_probe.areas import VIEWS, inventory, area_reports, OVERHEAD
from parking_probe.config import validate_polygon
from parking_probe.interface_model import Review, chart_data


def result(clip, states, when=0):
    return {'recording_id': clip, 'reference': {'sample_time_seconds': when},
            'rows': [{'bay_id': bay, 'reference_state': state, 'mog2_state': state} for bay,state in states.items()]}


def test_chad_inventory_has_nine_physical_bays_not_four_copies():
    for key in ('chad-1', 'chad-2', 'chad-3', 'chad-4'):
        slots = inventory(VIEWS[key])
        assert len(slots) == 9
        assert len({b['bay_id'] for b in slots}) == 9
        assert sum(b['area'] == 'chad-far' for b in slots) == 7
        assert sum(b['area'] == 'chad-near' for b in slots) == 2
        assert sum(b.get('calibration_pending', False) for b in slots) == 6
        for b in slots:
            validate_polygon(b['polygon'], 1280, 720)
    for n in (2,3,4):
        slots = inventory(VIEWS[f'chad-camera-{n}'])
        assert len(slots) == {2:5,3:4,4:3}[n]
        assert len({b['bay_id'] for b in slots}) == len(slots)
        assert 'CHAD-P009' in {b['bay_id'] for b in slots}
        for b in slots:
            validate_polygon(b['polygon'],1280,720)


def test_missing_inventory_bays_expand_range_instead_of_becoming_vacant():
    sample = result('chad-1', {'CHAD-P001':'occupied','CHAD-P002':'vacant','CHAD-P003':'vacant'})
    rows, s = chart_data(sample, [b['bay_id'] for b in inventory(VIEWS['chad-1'])])
    assert s['total_monitored_bays'] == 9 and s['unknown'] == 6
    assert s['vacant'] == 2 and s['occupied'] == 1
    assert s['occupancy_pct'] is None
    assert s['occupancy_min_pct'] == pytest.approx(100/9)
    assert s['occupancy_max_pct'] == pytest.approx(700/9)


def test_area_vacancies_are_per_site_and_use_selected_recording_not_all_periods():
    review = Review()
    review.add_samples({'recordings': [result('chad-1', {'CHAD-P001':'occupied','CHAD-P002':'vacant','CHAD-P003':'vacant'}),
        result('chad-2', {'CHAD-P001':'vacant','CHAD-P002':'vacant','CHAD-P003':'vacant'}),
        result('overhead-1', {'OVER-W01':'vacant','OVER-E01':'occupied'}, 0),
        result('overhead-1', {'OVER-W01':'unknown','OVER-E01':'unknown'}, 15)]})
    areas = {r['area_id']:r for r in area_reports(review, {'chad':('chad-1',0), 'overhead':('overhead-1',12)})}
    assert areas['chad-far']['total_monitored_bays'] == 7
    assert areas['chad-far']['vacant'] == 2 and areas['chad-far']['unknown'] == 4
    assert areas['chad-near']['unknown'] == 2 and not areas['chad-near']['available']
    assert areas['overhead-west']['vacant'] == 1 and areas['overhead-west']['unknown'] == 23
    assert areas['overhead-east']['occupied'] == 1
    later = {r['area_id']:r for r in area_reports(review, {'overhead':('overhead-1',15)})}
    assert not later['overhead-east']['available']
    assert later['overhead-east']['vacant'] == 0
    with pytest.raises(ValueError):
        area_reports(review, {'chad':('overhead-1',0)})


def test_other_site_inventory_is_explicit_demonstration_subset():
    slots = inventory(VIEWS[OVERHEAD.id])
    assert len(slots) == 69
    assert len({s['bay_id'] for s in slots}) == 69
    assert sum(s.get('calibration_pending',False) for s in slots) == 66
    assert {a:sum(s['area']==a for s in slots) for a in ('overhead-west','overhead-middle','overhead-east')} == {'overhead-west':24,'overhead-middle':22,'overhead-east':23}
    for slot in slots:
        validate_polygon(slot['polygon'], 1100, 720)
