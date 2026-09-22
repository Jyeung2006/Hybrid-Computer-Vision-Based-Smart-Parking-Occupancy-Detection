from datetime import timedelta

import cv2
import numpy as np
import pytest

from parking_probe.config import ConfigError, polygon_signature, validate_polygon
from parking_probe.sources import Frame, utcnow
from parking_probe.vision import Analyzer, PREPROCESSING, classify, occupancy_summary, thresholds


def install_calibration(config):
    analyzer = Analyzer(config)
    for slot in config.data["slots"]:
        slot["calibration"] = {"status": "calibrated", "vacant_max": .015, "occupied_min": .2,
            "reference_pixel_hash": analyzer.reference_hashes[slot["id"]],
            "setup_pixel_hash": analyzer.setup_hash, "polygon_signature": polygon_signature(slot["polygon"]), "preprocessing": PREPROCESSING}
    return Analyzer(config)


@pytest.mark.parametrize("points", [[], [[1, 1], [1, 1], [10, 10]], [[0, 0], [10, 10], [0, 10], [10, 0]],
    [[-1, 1], [20, 1], [20, 20]], [[1, 1], [100, 1], [20, 20]], [[1.5, 1], [20, 1], [20, 20]],
    [[1, 1], [2, 1], [2, 2]], [[1, 1], [20, 1], [20, 20], [10, 1], [1, 20]]])
def test_invalid_polygons(points):
    with pytest.raises(ConfigError):
        validate_polygon(points, 100, 100)


def test_valid_perspective_polygon():
    assert validate_polygon([[10, 10], [50, 15], [70, 80], [5, 80]], 100, 100).shape == (4, 2)


@pytest.mark.parametrize("score,expected", [(.099, "vacant"), (.1, "vacant"), (.1001, "uncertain"), (.2999, "uncertain"), (.3, "occupied"), (.9, "occupied")])
def test_boundary_rules(score, expected):
    assert classify(score, .1, .3) == expected


def test_overlap_and_sample_minimum():
    assert thresholds([.1] * 4, [.8] * 5)["status"] == "uncalibrated"
    assert thresholds([.2] * 5, [.2] * 5)["status"] == "uncalibrated"
    assert thresholds([.4] * 5, [.2] * 5)["status"] == "uncalibrated"
    assert thresholds([.1] * 5, [.5] * 5)["status"] == "calibrated"


def test_arithmetic_with_unknowns():
    partial = occupancy_summary([{"state": s} for s in ["occupied", "vacant", "uncertain", "unknown"]])
    assert partial["occupancy_pct"] is None
    assert partial["occupancy_min_pct"] == 25
    assert partial["occupancy_max_pct"] == 75
    assert partial["decision_coverage_pct"] == 50
    assert occupancy_summary([])["occupancy_pct"] is None
    assert occupancy_summary([{"state": "occupied"}], False)["occupancy_min_pct"] is None


def test_comparison_is_per_bay(config, scene):
    analyzer = install_calibration(config)
    result = analyzer.analyze(Frame(scene[2](1, ("P02",)), utcnow()))
    assert result["alignment"]["ok"]
    assert [s["state"] for s in result["slots"]] == ["vacant", "occupied"]
    assert result["summary"]["occupancy_pct"] == 50
    assert result["source_captured_at"] is None
    assert result["frame_age_seconds"] is None
    assert result["freshness_basis"] == "retrieval_only"


def test_missing_reference_is_unknown(config, scene):
    analyzer = install_calibration(config)
    config.data["slots"][0]["reference_image"] = "missing.png"
    result = Analyzer(config).analyze(Frame(scene[2](1), utcnow()))
    assert result["slots"][0]["state"] == "unknown"
    assert result["slots"][0]["difference_score"] is None


def test_reference_without_calibration_remains_unknown(config, scene):
    for slot in config.data["slots"]:
        slot["calibration"] = None
    result = Analyzer(config).analyze(Frame(scene[2](1), utcnow()))
    assert all(s["state"] == "unknown" for s in result["slots"])
    assert all(s["reason"] == "missing_or_invalid_calibration" for s in result["slots"])


def test_changed_polygon_invalidates_calibration(config, scene):
    install_calibration(config)
    config.data["slots"][0]["polygon"][0][0] += 5
    result = Analyzer(config).analyze(Frame(scene[2](1), utcnow()))
    assert result["slots"][0]["reason"] == "missing_or_invalid_calibration"


def test_resolution_and_movement_rejected(config, scene):
    analyzer = install_calibration(config)
    original = scene[2](1)
    for image, reason in [(cv2.resize(original, (320, 240)), "resolution_changed"),
                           (cv2.warpAffine(original, np.float32([[1, 0, 20], [0, 1, 0]]), (640, 480)), "camera_view_changed")]:
        result = analyzer.analyze(Frame(image, utcnow()))
        assert result["error"] == reason
        assert all(s["state"] == "unknown" for s in result["slots"])
        assert result["summary"]["occupancy_min_pct"] is None


def test_no_texture_not_treated_as_vacant(config):
    result = install_calibration(config).analyze(Frame(np.zeros((480, 640, 3), np.uint8), utcnow()))
    assert result["analysis_status"] == "unavailable"
    assert result["slots"][0]["state"] == "unknown"


@pytest.mark.parametrize("received_age,captured_age,reason", [(20, None, "stale_frame"), (0, 20, "stale_frame"), (0, -60, "source_timestamp_in_future")])
def test_stale_and_bad_clock(config, scene, received_age, captured_age, reason):
    now = utcnow()
    frame = Frame(scene[2](1), now - timedelta(seconds=received_age), now - timedelta(seconds=captured_age) if captured_age is not None else None)
    result = install_calibration(config).analyze(frame)
    assert result["error"] == reason
    assert result["summary"]["occupancy_pct"] is None


def test_failure_clears_current_counts(config):
    result = Analyzer(config).failure("retrieval_timeout")
    assert result["stale"] and result["frame_id"] is None
    assert result["summary"]["unknown"] == 2
    assert result["summary"]["occupancy_max_pct"] is None
