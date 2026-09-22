import json
from pathlib import Path
import threading

import cv2
import pytest

from parking_probe.catalog import CLIPS
from parking_probe.config import polygon_signature
from parking_probe.display_model import occupancy_table
from parking_probe import monitor
from parking_probe.vision import Analyzer, PREPROCESSING, occupancy_summary


def test_terminal_states_and_partial_occupancy_are_explicit():
    slots = [{"slot_id": key, "state": state} for key, state in
             (("B01", "occupied"), ("B02", "vacant"), ("B03", "uncertain"))]
    result = {"processed_at": "2026-09-15T04:00:00+08:00", "analysis_status": "estimated",
              "video_position_seconds": 17.9846, "processing_duration_ms": 25.6,
              "slots": slots, "summary": occupancy_summary(slots)}
    header, row = occupancy_table(result)
    assert all(state in row for state in ("OCCUPIED", "VACANT", "UNCERTAIN"))
    assert "00:18" in row and "33.3 - 66.7%" in row
    assert row[header.index("PARKED"):header.index("VACANT", header.index("PARKED"))].strip() == "1"


def test_terminal_failure_does_not_report_zero_parked(config):
    result = Analyzer(config).failure("recorded_video_decode_failed")
    result["video_position_seconds"] = 3
    header, row = occupancy_table(result)
    assert "Unavailable" in row and "UNKNOWN" in row
    assert row[header.index("PARKED"):header.index("VACANT", header.index("PARKED"))].strip() == "--"
    assert "%" not in row


@pytest.mark.parametrize("fail_second_frame", [False, True])
def test_recording_analysis_reporting_and_failure_history(config, scene, tmp_path, monkeypatch, fail_second_frame):
    # A real lossless local video exercises the new replay/report path. The
    # artificial car shapes are software test fixtures, not accuracy evidence.
    video = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"FFV1"), 2, (640, 480))
    if not writer.isOpened():
        pytest.skip("Lossless FFV1 encoder unavailable")
    try:
        for i in range(8):
            writer.write(scene[2](i, ("P02",) if i < 6 else ("P01",)))
    finally:
        writer.release()
    analyzer = Analyzer(config)
    for slot in config.data["slots"]:
        slot["calibration"] = {"status": "calibrated", "vacant_max": .015, "occupied_min": .2,
            "reference_pixel_hash": analyzer.reference_hashes[slot["id"]], "setup_pixel_hash": analyzer.setup_hash,
            "polygon_signature": polygon_signature(slot["polygon"]), "preprocessing": PREPROCESSING}
    recipe = {"source_resolution": [640, 480], "analysis_resolution": [640, 480]}
    monkeypatch.setattr(monitor, "prepare_preset", lambda emit, stop: (config, recipe, {CLIPS[0].id: video}))
    monkeypatch.setattr(monitor, "PROJECT_ROOT", tmp_path)
    if fail_second_frame:
        original = monitor.Recording.read

        def read(recording, index):
            if index == 6:
                raise RuntimeError("Simulated decode failure")
            return original(recording, index)

        monkeypatch.setattr(monitor.Recording, "read", read)
    events = []
    if fail_second_frame:
        with pytest.raises(RuntimeError, match="Simulated decode"):
            monitor.run_recording(CLIPS[0], 3, threading.Event(), lambda *event: events.append(event), fast=True)
    else:
        assert monitor.run_recording(CLIPS[0], 3, threading.Event(), lambda *event: events.append(event), fast=True) == 0
    observations = [event[1][0] for event in events if event[0] == "observation"]
    assert len(observations) == 2
    assert [slot["state"] for slot in observations[0]["slots"]] == ["vacant", "occupied"]
    assert observations[0]["summary"]["occupancy_pct"] == 50
    assert observations[1]["video_position_seconds"] == 3
    directory = next((tmp_path / "runs/chad/chad-1").iterdir())
    latest = json.loads((directory / "latest.json").read_text())
    run = json.loads((directory / "run.json").read_text())
    history = [json.loads(line) for line in (directory / "history.jsonl").read_text().splitlines()]
    assert len(history) == 2
    assert (directory / "summary.csv").exists() and (directory / "latest.png").exists()
    if fail_second_frame:
        assert run["status"] == "failed"
        assert latest["stale"] and latest["analysis_status"] == "unavailable"
        assert latest["summary"]["occupancy_pct"] is None
        assert history[0]["summary"]["occupancy_pct"] == 50
    else:
        assert run["status"] == "complete"
        assert [slot["state"] for slot in latest["slots"]] == ["occupied", "vacant"]
        assert latest["summary"]["occupancy_pct"] == 50
