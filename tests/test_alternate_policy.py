from copy import deepcopy
import csv
from itertools import product
import json
import threading
import tkinter as tk

from parking_probe.alternate_policy import (add_alternate, export_alternate_review,
                                            final_decision_reference_priority)
from parking_probe.yolo import final_decision


def test_alternate_requires_valid_calibration_and_falls_back_exactly():
    states = ('occupied', 'vacant', 'uncertain', 'unknown')
    for ref, mog, yolo in product(states, repeat=3):
        expected = final_decision(ref, mog, yolo)
        for valid in (False, None, 'calibrated', 1):
            alt = final_decision_reference_priority(ref, mog, yolo, reference_calibrated=valid)
            assert (alt['state'], alt['reason']) == expected
        alt = final_decision_reference_priority(ref, mog, yolo, reference_calibrated=True)
        if ref in ('occupied', 'vacant'):
            assert alt['state'] == ref and alt['confirmed_by'] == 'reference_only_experimental'
        else:
            assert (alt['state'], alt['reason']) == expected
        assert alt['experimental'] and not alt['primary']
    # This intentionally risky conflict must be visible, not silently special-cased.
    assert final_decision_reference_priority('vacant', 'uncertain', 'occupied', reference_calibrated=True)['state'] == 'vacant'
    assert final_decision_reference_priority('unknown', 'uncertain', 'uncertain')['state'] == 'uncertain'


def sample():
    return {'recording_id': 'chad-1', 'reference': {'sample_time_seconds': 0, 'video_position_seconds': 0},
        'mog2': {'processed_at': '2026-09-22T00:00:00+00:00'},
        'final': {'processed_at': '2026-09-22T00:00:00+00:00',
                  'slots': [{'slot_id': 'B01', 'state': 'occupied', 'confirmed_by': 'yolov8'}]},
        'rows': [{'slot_id': 'B01', 'bay_id': 'CHAD-P001', 'reference_state': 'vacant',
            'mog2_state': 'uncertain', 'yolo_state': 'occupied', 'yolo_requested': True,
            'reference_calibrated': True, 'final_state': 'occupied', 'final_confirmed_by': 'yolov8'}]}


def test_secondary_export_retains_primary_and_does_not_mutate_input(tmp_path):
    pair = sample(); original = deepcopy(pair)
    comparison = add_alternate(pair)
    assert pair == original and comparison['final'] == original['final']
    assert comparison['rows'][0]['final_alt_state'] == 'vacant'
    assert comparison['final_alt']['slots'][0]['confirmed_by'] == 'reference_only_experimental'
    original_path = tmp_path / 'history.jsonl'; original_path.write_text('original\n')
    out = export_alternate_review(tmp_path, {'chad-1': [pair]})
    assert original_path.read_text() == 'original\n'
    saved = json.loads((out / 'history.jsonl').read_text())
    row = next(csv.DictReader((out / 'observations.csv').open()))
    assert saved == comparison
    assert row['final_state'] == 'occupied' and row['final_alt_state'] == 'vacant'
    assert row['final_alt_is_primary'] == 'False'


def test_ui_opt_in_shows_two_provenances_and_read_only_report(tmp_path):
    from parking_probe.interface import ParkingInterface
    root = tk.Tk(); root.withdraw()
    app = ParkingInterface(root, autostart=False)
    app.out = tmp_path
    pair = sample(); original = deepcopy(pair)
    app.review.samples = {'chad-1': [pair]}
    try:
        assert app.show_alternate.get() is False
        app.render_observation(pair)
        primary_rate = app.rate.cget('text')
        assert tuple(app.table['displaycolumns']) == app.primary_columns
        assert not (tmp_path / 'experimental-reference-priority').exists()
        app.table.selection_set(app.table.get_children()[0])
        app.show_alternate.set(True); app.toggle_alternate()
        assert app.rate.cget('text') == primary_rate
        assert app.table.item(app.table.get_children()[0])['values'][5:7] == ['OCCUPIED', 'EXP: VACANT']
        assert 'YOLOv8' in app.row_details.cget('text')
        assert 'reference_only_experimental' in app.row_details.cget('text')
        assert app.review.samples['chad-1'][0] == original
        assert (tmp_path / 'experimental-reference-priority/observations.csv').exists()
        app.show_alternate.set(False); app.toggle_alternate()
        assert tuple(app.table['displaycolumns']) == app.primary_columns
        assert 'EXP alternate:' not in app.row_details.cget('text')
        app.open_validation_report()
        window, text = app.validation_viewer
        assert text.cget('state') == 'disabled'
        contents = text.get('1.0', 'end')
        text.insert('end', 'should not be added')
        assert text.get('1.0', 'end') == contents
        window.destroy()
    finally:
        app.close()


def test_replay_default_and_explicit_alternate_keep_same_primary(config, scene, tmp_path, monkeypatch):
    from test_comparison import prepare
    from parking_probe import comparison
    from parking_probe.catalog import CLIPS
    from parking_probe.mog2 import MOG2Branch
    from parking_probe.yolo import VerificationService
    prepare(config, scene, tmp_path, monkeypatch)
    monkeypatch.setattr(MOG2Branch, 'analyze', lambda self, frame, position, checked: self.failure(checked, 'test_mog2_failure'))
    class Detector:
        def detect(self, image, profile):
            return []
    service = VerificationService(Detector())
    samples = []
    try:
        for enabled in (False, True):
            events = []
            out = tmp_path / str(enabled)
            comparison.run_comparison(CLIPS[:1], 3, threading.Event(), lambda *e: events.append(e),
                fast=True, frame_limit=1, out=out, verification=True, service=service, alternate_policy=enabled)
            pair = next(v for k, v in events if k == 'comparison_samples')['recordings'][0]
            samples.append(pair)
            assert ('final_alt' in pair) is enabled
            assert all(r['reference_calibrated'] for r in pair['rows'])
            csv_rows = list(csv.DictReader((out / 'observations.csv').open()))
            assert ('final_alt_state' in csv_rows[0]) is enabled
            final = json.loads((out / 'final-summary.json').read_text())
            assert ('final_alt_state' in final['rows'][0]) is enabled
        assert samples[0]['final']['summary'] == samples[1]['final']['summary']
        assert all(r['final_state'] == 'uncertain' for r in samples[1]['rows'])
        assert [r['final_alt_state'] for r in samples[1]['rows']] == ['occupied', 'vacant']
    finally:
        service.close()


def test_saved_log_diagnostic_denominators_and_no_accuracy_claim():
    from checks.diagnose_mog2_contribution import contribution
    rows = []
    for ref, mog, yolo, final, confirmed in [
        ('vacant', 'vacant', 'unknown', 'vacant', 'reference_and_mog2'),
        ('occupied', 'vacant', 'occupied', 'occupied', 'yolov8'),
        ('uncertain', 'occupied', 'uncertain', 'uncertain', None),
        ('vacant', 'unknown', 'uncertain', 'uncertain', None)]:
        rows.append({'reference_state': ref, 'mog2_state': mog, 'yolo_state': yolo, 'yolo_requested': confirmed != 'reference_and_mog2',
            'final_state': final, 'final_confirmed_by': confirmed, 'final_alt_state': final})
    result = contribution(rows)
    assert result['agreement_pct_of_overlapping_definite'] == 50
    assert result['mog2_only_pct_of_all_selected'] == result['reference_only_pct_of_all_selected'] == 25
    assert result['classic_confirmations_without_alternate_recorded_route'] == 1
    assert result['accuracy'] is result['false_vacant_rate'] is None
