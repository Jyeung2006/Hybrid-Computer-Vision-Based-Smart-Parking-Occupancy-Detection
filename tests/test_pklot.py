from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json

import cv2
import pytest

from parking_probe.config import ConfigError, polygon_signature
from parking_probe.evaluation import ClassificationMetrics
from parking_probe.mog2 import MOG2Branch, PARAMETERS
from parking_probe.pklot import annotation, partition, ufpr04_member
from parking_probe.pklot_evaluation import (SnapshotRecording, forbid_after_test,
                                           select_profile, summarize_days)
from parking_probe.sources import Frame, utcnow, write_image
from parking_probe.vision import Analyzer, pixel_hash


def test_xml_conversion_preserves_ids_polygons_and_unlabelled_truth(tmp_path):
    path = tmp_path/'frame.xml'
    polygon = '<contour><point x="10" y="10"/><point x="80" y="10"/><point x="80" y="80"/><point x="10" y="80"/></contour>'
    path.write_text(f'<parking><space id="1" occupied="0">{polygon}</space>'
                    f'<space id="28" occupied="1">{polygon}</space><space id="2">{polygon}</space></parking>')
    slots, labels = annotation(path)
    assert [s['id'] for s in slots] == ['UFPR04-P01', 'UFPR04-P02', 'UFPR04-P28']
    assert labels == {'UFPR04-P01': 'vacant', 'UFPR04-P28': 'occupied'}
    assert slots[0]['polygon'] == [[10,10],[80,10],[80,80],[10,80]]
    path.write_text(path.read_text().replace('<point ', '<Point '))
    assert annotation(path) == (slots, labels)
    path.write_text(f'<parking><space id="1" occupied="0">{polygon}</space><space id="1">{polygon}</space></parking>')
    with pytest.raises(ConfigError, match='unique'):
        annotation(path)
    path.write_text('<!DOCTYPE parking [<!ENTITY x "boom">]><parking/>')
    with pytest.raises(ConfigError, match='DTD'):
        annotation(path)


def test_archive_allowlist_cannot_escape_cache_or_select_segmented_crops():
    name = 'PKLot/PKLot/UFPR04/Sunny/2012-12-07/2012-12-07_20_17_28.jpg'
    assert ufpr04_member(name).as_posix() == 'UFPR04/Sunny/2012-12-07/2012-12-07_20_17_28.jpg'
    for bad in (name.replace('UFPR04','UFPR05'), name.replace('Sunny','..'), '../'+name,
                name.replace('/PKLot/UFPR04','/PKLotSegmented/UFPR04'), name.replace('.jpg','.exe')):
        assert ufpr04_member(bad) is None


def test_pinned_downloader_checks_bytes_and_bounds_retries(tmp_path, monkeypatch):
    from parking_probe import pklot
    from parking_probe.sources import SourceError
    import requests
    data=b'known test archive bytes'
    monkeypatch.setattr(pklot,'ARCHIVE_SIZE',len(data))
    monkeypatch.setattr(pklot,'ARCHIVE_SHA256',hashlib.sha256(data).hexdigest())
    calls=[]
    class Response:
        status_code=200
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,size):yield data
    def get(url, **kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr(pklot.requests,'get',get)
    path=pklot.fetch_archive(tmp_path,lambda _:None)
    assert path.read_bytes()==data and calls[0]['timeout']==(10,30)
    pklot.fetch_archive(tmp_path,lambda _:None)
    assert len(calls)==1
    path.write_bytes(b'wrong checksum cache')
    with pytest.raises(SourceError,match='integrity'):
        pklot.fetch_archive(tmp_path,lambda _:None)
    failures=[]
    def fail(*args,**kwargs):
        failures.append(True)
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(pklot.requests,'get',fail)
    with pytest.raises(SourceError,match='three_attempts'):
        pklot.fetch_archive(tmp_path/'offline',lambda _:None)
    assert len(failures)==3


def test_partition_whole_days_across_weather_reproducible_no_leakage():
    rows = []
    for i in range(31):
        day = (datetime(2012,1,1)+timedelta(days=i)).date().isoformat()
        for weather in ('sunny','rainy'):
            rows.append({'day': day, 'weather': weather, 'sha256': f'{day}-{weather}'})
    result = partition(rows)
    assert result == partition(rows)
    sets = {k: {r['day'] for r in v} for k,v in result.items()}
    assert [len(sets[k]) for k in ('fit','calibrate','test')] == [19,6,6]
    assert not sets['fit'] & sets['test'] and not sets['calibrate'] & sets['fit']
    for group in result.values():
        assert all(value == 2 for value in Counter(r['day'] for r in group).values())
    rows[-1]['sha256'] = rows[0]['sha256']
    with pytest.raises(ConfigError, match='Duplicate'):
        partition(rows)


def test_metrics_distinguish_abstentions_from_conditional_accuracy():
    metrics = ClassificationMetrics()
    for truth, state in [('occupied','occupied')]*8 + [('occupied','vacant')]*2 + [('occupied','unknown')]*10 + [('vacant','vacant')]*6 + [('vacant','occupied')]*4 + [('vacant','uncertain')]*10:
        metrics.add(truth, state)
    m = metrics.result()
    assert m['accuracy_on_classified_pct'] == 70
    assert m['decision_coverage_pct'] == 50
    assert m['precision_on_classified_pct'] == pytest.approx(100*8/12)
    assert m['recall_on_classified_pct'] == 80
    assert m['f1_on_classified_pct'] == pytest.approx(100*16/22)
    assert m['false_vacant_rate_all_occupied_pct'] == 10
    assert m['false_occupied_rate_all_vacant_pct'] == 20
    assert m['false_vacant_rate_on_classified_occupied_pct'] == 20
    assert m['correct_decisions_all_truth_pct'] == 35
    assert sum(sum(row.values()) for row in m['confusion_matrix'].values()) == 40
    empty = ClassificationMetrics().result()
    assert empty['accuracy_on_classified_pct'] is None and empty['f1_on_classified_pct'] is None


def test_mog2_default_signature_identical_and_snapshot_gap_relative(config, scene):
    analyzer = Analyzer(config)
    legacy = {'parameters': PARAMETERS, 'interval': 3, 'opencv': cv2.__version__,
        'setup_hash': analyzer.setup_hash,
        'polygons': {s['id']: polygon_signature(s['polygon']) for s in analyzer.slot_config},
        'references': analyzer.reference_hashes}
    default = MOG2Branch(analyzer)
    legacy['seed_hash'] = pixel_hash(default.seed)
    assert default.signature == hashlib.sha256(json.dumps(legacy,sort_keys=True).encode()).hexdigest()
    assert default.signature == MOG2Branch(analyzer, expected_sample_interval=3).signature
    assert MOG2Branch(analyzer, interval=1).parameters == PARAMETERS
    periodic = MOG2Branch(analyzer, interval=300, expected_sample_interval=300)
    assert periodic.parameters['gap_reset_seconds'] == 1500
    for position in (0, 300, 600, 2100):
        frame = Frame(scene[2](position), utcnow(), frame_id=str(position))
        periodic.analyze(frame, position, analyzer.analyze(frame))
    assert periodic.update_count == 4 and periodic.reset_count == 0
    frame = Frame(scene[2](4), utcnow(), frame_id='long-gap')
    result = periodic.analyze(frame, 3601, analyzer.analyze(frame))
    assert result['model_reset_count'] == 1
    assert all(s['reason'] == 'mog2_restabilizing_after_gap' for s in result['slots'])
    for bad in (0, -1, float('inf'), float('nan'), True):
        with pytest.raises(ConfigError, match='interval'):
            MOG2Branch(analyzer, expected_sample_interval=bad)


def test_snapshot_adapter_chronology_and_real_300_second_positions(tmp_path, scene):
    # Adapter verifies original UFPR04 resolution; fixture pixels are resized,
    # not used to estimate any real external-dataset accuracy.
    rows=[]
    for i in range(3):
        path = tmp_path/f'{i}.png'
        write_image(path, cv2.resize(scene[2](i),(1280,720)))
        rows.append({'day':'2012-01-01', 'frame_id':str(i), 'image':path.name,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'captured_local':f'2012-01-01T12:{i*5:02d}:00'})
    result = list(SnapshotRecording(tmp_path, list(reversed(rows))))
    assert [r[2] for r in result] == [0,300,600]
    assert result[0][1].captured_at is None  # Historical metadata is not live freshness.
    assert result[0][0]['captured_local'].startswith('2012')
    rows[1]['day']='2012-01-02'
    with pytest.raises(ConfigError, match='one day'):
        SnapshotRecording(tmp_path,rows)


def test_profile_selection_uses_decision_success_instead_of_inflated_accuracy():
    report = {'methods': {'final_coco': {'all': {'correct_decisions_all_truth_pct':70,
        'accuracy_on_classified_pct':90,'confusion':{'false_vacant':10}}},
        'final_aerial': {'all': {'correct_decisions_all_truth_pct':10,
        'accuracy_on_classified_pct':100,'confusion':{'false_vacant':0}}}}}
    assert select_profile(report) == 'coco'
    report['methods']['final_aerial']['all']['correct_decisions_all_truth_pct'] = 70
    assert select_profile(report) == 'aerial'


def test_test_opening_locks_fitting_and_calibration(tmp_path):
    forbid_after_test(tmp_path)
    (tmp_path/'test-started.json').write_text('{}')
    with pytest.raises(ConfigError, match='locked'):
        forbid_after_test(tmp_path)


def test_external_runner_calls_real_branches_and_reuses_completed_day(config, scene, tmp_path, monkeypatch):
    from parking_probe import pklot_evaluation as experiment
    from parking_probe.evaluation import reference_boundaries
    from parking_probe.yolo import VerificationService, final_decision
    analyzer = Analyzer(config)
    for slot in config.data['slots']:
        slot['calibration'] = reference_boundaries(analyzer, slot, [.01]*5, [.4]*5, [], ['fit-day'])
    analyzer = Analyzer(config)
    branch = experiment.make_branch(analyzer)
    calibration = {'model_signature': branch.signature,
        'slots': {s['id']: {'status':'calibrated','vacant_max':.05,'occupied_min':.4} for s in config.data['slots']}}
    rows = [{'frame_id': str(i), 'day': '2012-01-01', 'weather': 'rainy' if i%2 else 'sunny',
        'captured_local': f'2012-01-01T12:{i*5:02d}:00',
        'labels': {'P01':'occupied','P02':'vacant'}} for i in range(4)]
    def recordings(directory, day_rows):
        for i,row in enumerate(day_rows):
            image=scene[2](i+10, ('P01',))
            yield row, Frame(image,utcnow(),frame_id=row['frame_id']), i*300, 1.0
    monkeypatch.setattr(experiment,'SnapshotRecording',recordings)
    class Detector:
        def detect(self,image,profile):
            return []
    service=VerificationService(Detector())
    try:
        report,pixels=experiment.evaluate_partition(tmp_path,rows,tmp_path/'output','test',
            analyzer,calibration,service,set(),'frozen-identity',lambda _: None)
        assert report['frames']==4 and report['mog2_updates']==4 and report['mog2_gap_resets']==0
        assert report['methods']['final_coco']['all']['accuracy_on_classified_pct']==100
        assert report['methods']['final_coco']['sunny']['binary_observations']==4
        assert report['methods']['final_coco']['rainy']['binary_observations']==4
        saved=json.loads((tmp_path/'output/test/2012-01-01.json').read_text())
        for frame in saved['frames']:
            for row in frame['observations']:
                s=row['states']
                for p in ('coco','aerial'):
                    assert s['final_'+p]==final_decision(s['reference'],s['mog2'],s['yolo_'+p])[0]
        def no_more_inference(*args):
            raise AssertionError('Completed test day must not be inferred twice')
        monkeypatch.setattr(experiment,'SnapshotRecording',no_more_inference)
        repeated, repeated_pixels=experiment.evaluate_partition(tmp_path,rows,tmp_path/'output','test',
            analyzer,calibration,service,set(),'frozen-identity',lambda _: None)
        assert repeated==report and repeated_pixels==pixels
        with pytest.raises(ConfigError,match='checkpoint'):
            experiment.evaluate_partition(tmp_path,rows,tmp_path/'output','test',
                analyzer,calibration,service,set(),'changed-identity',lambda _:None)
    finally:
        service.close()
