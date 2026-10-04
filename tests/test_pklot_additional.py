from pathlib import Path

import pytest

from parking_probe.pklot_additional import original_member, annotation, inventory, VIEWS


def test_only_originals_and_expected_views():
    assert original_member('PKLot/PKLot/UFPR05/Sunny/2013-03-03/2013-03-03_07_45_01.jpg') == Path(
        'UFPR05/Sunny/2013-03-03/2013-03-03_07_45_01.jpg')
    assert original_member('PKLot/PKLotSegmented/UFPR05/Sunny/2013-03-03/Empty/x.jpg') is None
    assert original_member('PKLot/PKLot/UFPR04/Sunny/2013-03-03/2013-03-03_07_45_01.jpg') is None
    assert original_member('PKLot/PKLot/UFPR05/Sunny/../../evil.jpg') is None


@pytest.mark.parametrize('view,number', [('UFPR05', 40), ('PUCPR', 100)])
def test_original_xml_retains_vehicle_truth(tmp_path, view, number):
    xml = (f'<parking><space id="{number}" occupied="1"><contour>'
           '<point x="10" y="10"/><point x="30" y="10"/>'
           '<point x="30" y="30"/><point x="10" y="30"/>'
           '</contour></space></parking>')
    path = tmp_path / 'case.xml'
    path.write_text(xml)
    slots, labels = annotation(path, view)
    assert len(slots) == 1 and labels[slots[0]['id']] == 'occupied'
    assert VIEWS[view] == number


def test_missing_image_is_recorded_as_orphan(tmp_path):
    relative = 'UFPR05/Sunny/2013-03-03/2013-03-03_07_45_01.xml'
    rows, orphans = inventory(tmp_path, 'UFPR05', {relative: 'abc'})
    assert rows == [] and orphans == [relative]
