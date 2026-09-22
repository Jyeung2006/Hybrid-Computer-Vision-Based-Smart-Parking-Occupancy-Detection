from copy import deepcopy
import json
import threading

import cv2
import pytest

from parking_probe import site_replay, monitor
from parking_probe.config import atomic_json, polygon_signature
from parking_probe.vision import Analyzer, PREPROCESSING


def make_site(config, scene, tmp_path, lengths=(12, 12)):
    analyzer = Analyzer(config)
    site = {"version": 1, "site_id": "fixture", "mapping_verified": True,
            "synchronization": {"verified": True, "note": "Synthetic videos generated on the same timeline"},
            "bay_ids": ["shared-1", "shared-2"], "cameras": []}
    for number, length in enumerate(lengths):
        camera_id = f"camera-{number}"
        data = deepcopy(config.data)
        data["source_id"] = camera_id
        data["source"] = {"type": "recorded_video"}
        for slot in data["slots"]:
            slot["calibration"] = {"status": "calibrated", "vacant_max": .015, "occupied_min": .2,
                "reference_pixel_hash": analyzer.reference_hashes[slot["id"]], "setup_pixel_hash": analyzer.setup_hash,
                "polygon_signature": polygon_signature(slot["polygon"]), "preprocessing": PREPROCESSING}
        config_path = tmp_path / f"{camera_id}.json"
        atomic_json(config_path, data)
        path = tmp_path / f"{camera_id}.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"FFV1"), 2, (640, 480))
        if not writer.isOpened():
            pytest.skip("Lossless FFV1 encoder unavailable")
        try:
            for i in range(length * 2):
                # Deliberate disagreement for the first six seconds, then both vacant.
                writer.write(scene[2](i, ("P01",) if number == 0 and i < 12 else ()))
        finally:
            writer.release()
        site["cameras"].append({"camera_id": camera_id, "config": str(config_path), "video_path": str(path),
            "source_resolution": [640, 480], "analysis_resolution": [640, 480], "video_offset_seconds": 0,
            "slot_map": {"P01": "shared-1", "P02": "shared-2"}})
    return site


def test_two_real_decoders_fuse_shared_ids_and_write_windows(config, scene, tmp_path):
    site = make_site(config, scene, tmp_path)
    events = []
    out = tmp_path / "output"
    assert site_replay.run_site(site, 3, threading.Event(), lambda *e: events.append(e), fast=True, out=out) == 0
    windows = [e[1] for e in events if e[0] == "window"]
    assert [w["window_end_seconds"] for w in windows] == [10, 12]
    assert [w["partial_window"] for w in windows] == [False, True]
    first = windows[0]
    assert first["sample_count"] == 4 and first["summary"]["total_monitored_bays"] == 2
    assert first["summary"]["vacant"] == 2  # counts physical bays, not four polygons
    bay = first["bays"][0]
    assert bay["occupied_time_min_pct"] == 0 and bay["occupied_time_max_pct"] == 60
    assert bay["classified_time_pct"] == 40 and bay["usable_views"] == 2
    saved = json.loads((out / "latest-window.json").read_text())
    assert saved["window_duration_seconds"] == 2
    assert saved["bays"][0]["occupied_time_pct"] == 0
    latest = json.loads((out / "latest.json").read_text())
    assert not latest["run_active"] and latest["summary"]["occupancy_pct"] is None
    assert all((out / name).exists() for name in ("summary.csv", "bays.csv", "windows.jsonl"))
    camera = json.loads((out / "cameras/camera-0/latest.json").read_text())
    assert camera["slots"][0]["bay_id"] == "shared-1"
    assert camera["source_captured_at"] is None
    assert (out / "cameras/camera-1/latest.png").exists()


def test_decode_failure_uses_other_view_and_does_not_reuse_stale_decision(config, scene, tmp_path, monkeypatch):
    site = make_site(config, scene, tmp_path)
    original = monitor.Recording.read
    broken = []

    def read(self, index):
        if not broken:
            broken.append(self)
        if self is broken[0] and index >= 6:
            raise RuntimeError("Simulated failure")
        return original(self, index)

    monkeypatch.setattr(monitor.Recording, "read", read)
    events = []
    assert site_replay.run_site(site, 3, threading.Event(), lambda *e: events.append(e), fast=True, out=tmp_path / "out") == 2
    observations = [e[1] for e in events if e[0] == "observation"]
    assert observations[0]["bays"][0]["state"] == "uncertain"
    bay = observations[1]["bays"][0]
    assert bay["state"] == "vacant" and bay["degraded"] and bay["usable_views"] == 1
    assert bay["views"][0]["state"] == "unknown" and bay["views"][0]["difference_score"] is None


def test_shorter_camera_end_is_unknown_without_ending_other_camera(config, scene, tmp_path):
    site = make_site(config, scene, tmp_path, lengths=(6, 12))
    events = []
    site_replay.run_site(site, 3, threading.Event(), lambda *e: events.append(e), fast=True, out=tmp_path / "out")
    last = [e[1] for e in events if e[0] == "window"][-1]
    assert last["window_end_seconds"] == 12
    assert last["bays"][0]["degraded"] and last["bays"][0]["usable_views"] == 1
    assert last["bays"][0]["views"][0]["reason"] == "recording_ended"


def test_failed_camera_open_does_not_stop_working_view(config, scene, tmp_path):
    site = make_site(config, scene, tmp_path)
    site["cameras"][0]["video_path"] = str(tmp_path / "absent.avi")
    events = []
    assert site_replay.run_site(site, 3, threading.Event(), lambda *e: events.append(e), fast=True, out=tmp_path / "out") == 2
    bay = [e[1] for e in events if e[0] == "window"][0]["bays"][0]
    assert bay["state"] == "vacant" and bay["degraded"]
    assert bay["occupied_time_pct"] == 0


def test_resolution_change_retains_reconfiguration_reason(config, scene, tmp_path):
    site = make_site(config, scene, tmp_path, lengths=(3, 3))
    site["cameras"][0]["source_resolution"] = [1920, 1080]
    out = tmp_path / "out"
    assert site_replay.run_site(site, 3, threading.Event(), lambda *e: None, fast=True, out=out) == 2
    camera = json.loads((out / "cameras/camera-0/latest.json").read_text())
    assert camera["error"] == "resolution_changed"
    assert camera["stale"] and camera["summary"]["occupancy_pct"] is None
    summary = json.loads((out / "latest-window.json").read_text())
    assert summary["bays"][0]["degraded"]
