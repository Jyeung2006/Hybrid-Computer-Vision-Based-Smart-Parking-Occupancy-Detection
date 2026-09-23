import csv

import pytest

from parking_probe.config import Config, ConfigError
from parking_probe.evaluation import calibrate, evaluate
from parking_probe.sources import write_image


def dataset(tmp_path, scene, count, start, name, sessions):
    rows = []
    for i in range(count):
        occupied = ("P01",) if i % 2 else ("P02",)
        path = tmp_path / f"{name}-{i}.png"
        write_image(path, scene[2](start + i, occupied))
        for slot in scene[1]:
            rows.append(dict(frame_path=path.name, slot_id=slot["id"],
                             label="occupied" if slot["id"] in occupied else "vacant", session_id=sessions[i % len(sessions)]))
    manifest = tmp_path / f"{name}.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def test_calibration_and_held_out_evaluation(config, scene, tmp_path):
    fitting = dataset(tmp_path, scene, 20, 1, "cal", ["cal-session"])
    result = calibrate(config, fitting)
    assert all(v["status"] == "calibrated" for v in result.values())
    heldout = dataset(tmp_path, scene, 30, 101, "heldout", ["test-am", "test-pm"])
    report = evaluate(Config(config.path), heldout)
    assert report["minimum_evaluation_requirements_met"]
    assert report["unique_frames"] == 30
    assert report["accuracy_on_classified_pct"] == 100
    assert report["decision_coverage_pct"] > 70
    assert report["live_camera_validation"] == "not_performed_by_this_command"


def test_session_leakage_rejected(config, scene, tmp_path):
    calibrate(config, dataset(tmp_path, scene, 10, 1, "cal", ["same-session"]))
    with pytest.raises(ConfigError, match="sessions"):
        evaluate(config, dataset(tmp_path, scene, 30, 100, "heldout", ["same-session"]))


def test_content_leakage_rejected(config, scene, tmp_path):
    calibrate(config, dataset(tmp_path, scene, 10, 1, "cal", ["cal-session"]))
    with pytest.raises(ConfigError, match="duplicates"):
        evaluate(config, dataset(tmp_path, scene, 30, 1, "renamed", ["new-session"]))


def test_reference_cannot_be_calibration(config, tmp_path):
    manifest = tmp_path / "bad.csv"
    manifest.write_text("frame_path,slot_id,label,session_id\nP01-reference.png,P01,vacant,session1\n")
    with pytest.raises(ConfigError, match="Reference images"):
        calibrate(config, manifest)

