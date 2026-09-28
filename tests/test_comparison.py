from copy import deepcopy
import json
import threading

import cv2
import pytest

from parking_probe import comparison, monitor
from parking_probe.catalog import CLIPS
from parking_probe.config import ConfigError, polygon_signature
from parking_probe.mog2 import MOG2Branch
from parking_probe.sources import SourceError
from parking_probe.vision import Analyzer, PREPROCESSING
from parking_probe.opencv_first import before_yolo, DECISION_POLICY as OPENCV_FIRST_POLICY


def prepare(config, scene, tmp_path, monkeypatch):
    analyzer = Analyzer(config)
    for slot in config.data["slots"]:
        slot["calibration"] = {"status": "calibrated", "vacant_max": .015, "occupied_min": .2,
            "reference_pixel_hash": analyzer.reference_hashes[slot["id"]], "setup_pixel_hash": analyzer.setup_hash,
            "polygon_signature": polygon_signature(slot["polygon"]), "preprocessing": PREPROCESSING}
    paths = {}
    for clip, duration, states in zip(CLIPS, (12, 9, 5, 12), (("P01",), (), ("P02",), ("P01",)), strict=True):
        path = tmp_path / f"{clip.id}.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"FFV1"), 2, (640, 480))
        if not writer.isOpened():
            pytest.skip("FFV1 unavailable")
        try:
            for i in range(duration*2):
                writer.write(scene[2](0, states))
        finally:
            writer.release()
        paths[clip.id] = path
    recipe = {"source_resolution": [640, 480], "analysis_resolution": [640, 480]}
    model = MOG2Branch(analyzer)
    calibration = {"model_signature": model.signature,
        "slots": {s["id"]: {"status": "calibrated", "vacant_max": .05, "occupied_min": .4} for s in config.data["slots"]}}
    monkeypatch.setattr(monitor, "prepare_preset", lambda emit, stop: (config, recipe, paths))
    monkeypatch.setattr(comparison, "prepare_mog2", lambda *args: calibration)
    monkeypatch.setattr(comparison, "BAY_MAP", {"P01": "shared-1", "P02": "shared-2"})


def test_four_recordings_run_together_with_separate_models_and_paired_outputs(config, scene, tmp_path, monkeypatch):
    prepare(config, scene, tmp_path, monkeypatch)
    events = []
    out = tmp_path / "out"
    assert comparison.run_comparison(CLIPS, 3, threading.Event(), lambda *e: events.append(e), fast=True, out=out) == 0
    batches = [e[1] for e in events if e[0] == "comparison_samples"]
    assert [b["timeline_seconds"] for b in batches] == [0, 3, 6, 9]
    assert [len(b["recordings"]) for b in batches] == [4, 4, 3, 2]
    for batch in batches:
        for recording in batch["recordings"]:
            if recording["recording_id"] in ("chad-1", "chad-4"):
                assert recording["rows"][0]["reference_state"] == recording["rows"][0]["mog2_state"] == "occupied"
            if recording["recording_id"] == "chad-2":
                assert all(r["reference_state"] == r["mog2_state"] == "vacant" for r in recording["rows"])
            assert recording["reference"]["frame_id"] == recording["mog2"]["frame_id"]
    assert batches[-1]["ended_recordings"] == ["chad-2", "chad-3"]
    run = json.loads((out / "run.json").read_text())
    assert run["samples_by_recording"] == {"chad-1":4,"chad-2":3,"chad-3":2,"chad-4":4}
    for clip in CLIPS:
        saved = json.loads((out / clip.id / "latest-window.json").read_text())
        assert saved["reference"]["summary"]["total_monitored_bays"] == 2
        assert saved["mog2"]["summary"]["total_monitored_bays"] == 2
        assert (out / clip.id / "mog2/foreground.png").exists()
    assert (out / "observations.csv").exists() and (out / "bay-windows.csv").exists()
    assert not json.loads((out / "latest.json").read_text())["current_occupancy_available"]
    final = json.loads((out / "final-summary.json").read_text())
    assert final["historical"] and final["summaries_by_recording"]["chad-1"]["occupied"] == 1
    assert final["summaries_by_recording"]["chad-2"]["vacant"] == 2
    assert (out / "final-summary.csv").exists()
    assert "REFERENCE" in comparison.format_samples(batches[0]) and "MOG2" in comparison.format_samples(batches[0])
    # Cross-recording joins cannot silently compare two different frames.
    pair = batches[0]["recordings"][0]
    bad = deepcopy(pair["mog2"])
    bad["frame_id"] = "other-recording"
    with pytest.raises(ConfigError):
        comparison.join_branches("chad-1", pair["reference"], bad)


def test_supplemental_branch_and_final_windows_preserve_separate_method_results(config, scene, tmp_path, monkeypatch):
    prepare(config, scene, tmp_path, monkeypatch)
    class Detector:
        def detect(self, image):
            return []
    events = []
    out = tmp_path / 'supplemental'
    assert comparison.run_comparison(CLIPS[:1],3,threading.Event(),lambda *e:events.append(e),fast=True,
        out=out,supplemental=True,detector=Detector()) == 0
    pair = next(v for k,v in events if k == 'comparison_samples')['recordings'][0]
    assert pair['rows'][0]['reference_state'] == 'occupied'
    assert pair['rows'][0]['vehicle_state'] == 'uncertain'  # No detection alone cannot prove vacancy.
    assert pair['rows'][0]['final_state'] == 'occupied'
    assert pair['rows'][0]['processed_at'] == pair['final']['processed_at'] == pair['vehicle']['processed_at']
    assert pair['vehicle']['processing_started_at'] <= pair['vehicle']['processed_at']
    window = next(v for k,v in events if k == 'comparison_windows')[0]
    assert set(('reference','mog2','vehicle','final')).issubset(window)
    assert window['final']['summary']['occupied'] == 1
    assert (out / 'chad-1/vehicle/latest.json').exists()
    assert (out / 'chad-1/final/latest.png').exists()
    final = json.loads((out / 'final-summary.json').read_text())
    assert final['summaries_by_recording']['chad-1']['occupied'] == 1


def test_opencv_first_replay_exposes_mobilenet_and_requests_only_unresolved_bays(config, scene, tmp_path, monkeypatch):
    prepare(config, scene, tmp_path, monkeypatch)
    class Detector:
        def detect(self, image):
            return []
    class Service:
        def verify(self, image, camera, frame, slots, profile):
            return {'camera_id': camera, 'frame_id': frame, 'slot_ids': slots,
                    'detections': [], 'error': None}
    events = []
    out = tmp_path / 'opencv-first'
    assert comparison.run_comparison(CLIPS[:1], 3, threading.Event(), lambda *e: events.append(e),
        fast=True, out=out, verification=True, service=Service(), detector=Detector(),
        opencv_first=True) == 0
    pairs = [p for kind, batch in events if kind == 'comparison_samples' for p in batch['recordings']]
    assert pairs
    for pair in pairs:
        assert {'reference', 'mog2', 'vehicle', 'yolo', 'final'} <= pair.keys()
        assert pair['final']['method'] == 'opencv_first_final_estimate'
        for row in pair['rows']:
            expected = before_yolo(row['reference_state'], row['mog2_state'], row['vehicle_state'])
            assert row['yolo_requested'] == expected[3]
            assert row['decision_policy'] == OPENCV_FIRST_POLICY
            if not row['yolo_requested']:
                assert row['final_state'] == expected[0]
                assert row['final_confirmed_by'] == expected[2]
    window = next(v for kind, v in events if kind == 'comparison_windows')[0]
    assert {'vehicle', 'yolo', 'final'} <= window.keys()
    assert (out / 'chad-1/vehicle/latest.json').exists()
    assert (out / 'chad-1/final/latest.png').exists()


def test_one_decode_failure_clears_both_branches_and_others_continue(config, scene, tmp_path, monkeypatch):
    prepare(config, scene, tmp_path, monkeypatch)
    original = monitor.Recording.read
    first = []

    def read(self, index):
        if not first:
            first.append(self)
        if self is first[0] and index >= 6:
            raise SourceError("resolution_changed")
        return original(self, index)

    monkeypatch.setattr(monitor.Recording, "read", read)
    out = tmp_path / "out"
    events = []
    assert comparison.run_comparison(CLIPS, 3, threading.Event(), lambda *e: events.append(e), fast=True, out=out) == 2
    batches = [e[1] for e in events if e[0] == "comparison_samples"]
    failed = batches[1]["recordings"][0]
    assert all(r["reference_state"] == r["mog2_state"] == "unknown" for r in failed["rows"])
    assert failed["mog2"]["error"] == "resolution_changed"
    assert not (out / "chad-1/mog2/foreground.png").exists()
    assert batches[-1]["recordings"][-1]["rows"][0]["mog2_state"] == "occupied"


def test_mog2_failure_preserves_reference_evidence(config, scene, tmp_path, monkeypatch):
    prepare(config, scene, tmp_path, monkeypatch)
    original = MOG2Branch.analyze
    failed = []

    def analyze(self, *args, **kwargs):
        if not failed:
            failed.append(self)
            raise RuntimeError("Synthetic branch failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MOG2Branch, "analyze", analyze)
    events = []
    assert comparison.run_comparison(CLIPS[:1], 3, threading.Event(), lambda *e: events.append(e), fast=True, out=tmp_path/'out') == 2
    batches = [e[1] for e in events if e[0] == "comparison_samples"]
    first = batches[0]["recordings"][0]["rows"][0]
    assert first["reference_state"] == "occupied" and first["mog2_state"] == "unknown"
    second = batches[1]["recordings"][0]["rows"][0]
    assert second["mog2_state"] == "uncertain" and second["mog2_reason"] == "mog2_restabilizing_after_gap"
    assert batches[-1]["recordings"][0]["rows"][0]["mog2_state"] == "occupied"


@pytest.mark.parametrize("ref,mog,expected", [
    ("occupied", "occupied", "occupied"), ("vacant", "vacant", "vacant"),
    ("occupied", "vacant", "uncertain"), ("occupied", "uncertain", "uncertain"),
    ("unknown", "vacant", "uncertain"), ("uncertain", "uncertain", "uncertain"),
    ("unknown", "unknown", "unknown")])
def test_final_estimate_requires_agreement(ref, mog, expected):
    assert comparison.consensus(ref, mog) == expected


def test_reviewed_empty_bank_cannot_override_unresolved_displayed_methods(config, scene, tmp_path, monkeypatch):
    from parking_probe.yolo import VerificationService
    from parking_probe.vacancy_guard import GUARDED_DECISION_POLICY
    prepare(config, scene, tmp_path, monkeypatch)
    analyzer = Analyzer(config)
    for slot in config.data['slots']:
        slot.pop('calibration')  # Empty-only examples do not calibrate both states.
        slot['vehicle_empty_match'] = {
            'vacant_examples':5, 'max_difference':.04, 'preprocessing':PREPROCESSING,
            'reference_pixel_hash':analyzer.reference_hashes[slot['id']],
            'setup_pixel_hash':analyzer.setup_hash, 'polygon_signature':polygon_signature(slot['polygon'])}
    class NoVehicleDetector:
        def detect(self, image, profile):
            return []
    service = VerificationService(NoVehicleDetector())
    events = []; out = tmp_path/'strict'
    try:
        assert comparison.run_comparison(CLIPS[1:2], 3, threading.Event(), lambda *e:events.append(e),
            fast=True, out=out, verification=True, service=service) == 0
    finally:
        service.close()
    samples = [v['recordings'][0] for k,v in events if k == 'comparison_samples']
    assert len(samples) == 3
    for pair in samples:
        assert pair['final']['summary']['vacant'] == 0
        for row in pair['rows']:
            assert row['reference_state'] == 'unknown'
            assert row['yolo_requested'] and row['yolo_state'] == 'uncertain'
            assert row['final_state'] == 'uncertain' and row['final_confirmed_by'] is None
            assert row['decision_policy'] == GUARDED_DECISION_POLICY
            assert row['vacancy_guard_reason'] == 'bay_visibility_not_reviewed_or_occluded'
            assert 'empty_candidate' not in row
    window = next(v for k,v in events if k == 'comparison_windows')[0]
    assert window['final']['summary']['vacant'] == 0
    saved = json.loads((out/'final-summary.json').read_text())
    assert saved['summaries_by_recording']['chad-2']['vacant'] == 0
