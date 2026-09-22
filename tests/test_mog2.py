from datetime import timedelta

import cv2
import numpy as np
import pytest

from parking_probe.config import ConfigError
from parking_probe.mog2 import MOG2Branch, clean_foreground
from parking_probe.sources import Frame, utcnow
from parking_probe.vision import Analyzer


def branch(config):
    analyzer = Analyzer(config)
    model = MOG2Branch(analyzer)
    model.calibration = {"model_signature": model.signature,
        "slots": {s["id"]: {"status": "calibrated", "vacant_max": .05, "occupied_min": .4}
                  for s in config.data["slots"]}}
    return model


def analyze(model, image, position, update=True):
    frame = Frame(image, utcnow(), frame_id=f"frame-{position}")
    checked = model.analyzer.analyze(frame)
    return model.analyze(frame, position, checked, update=update)


def test_shadow_labels_are_excluded_and_isolated_noise_removed():
    raw = np.zeros((50, 50), np.uint8)
    raw[5:20, 5:20] = 127
    raw[25:45, 25:45] = 255
    raw[2, 40] = 255
    mask = clean_foreground(raw)
    assert np.count_nonzero(mask[5:20, 5:20]) == 0
    assert mask[2, 40] == 0
    assert np.mean(mask[28:42, 28:42] == 255) == 1


def test_first_parked_vehicle_is_not_learned_as_empty_and_model_updates_once(config, scene):
    model = branch(config)
    for i in range(10):
        result = analyze(model, scene[2](0, ("P01",)), i*3)
        assert [s["state"] for s in result["slots"]] == ["occupied", "vacant"]
        assert result["model_update_count"] == i+1  # not once for each bay
        assert result["slots"][0]["foreground_ratio"] > .4
    # A departure restores the empty seed appearance without a motion-only ghost.
    result = analyze(model, scene[2](1, ()), 30)
    assert [s["state"] for s in result["slots"]] == ["vacant", "vacant"]


def test_duplicate_and_backwards_updates_are_rejected(config, scene):
    model = branch(config)
    analyze(model, scene[2](0), 3)
    with pytest.raises(ConfigError, match="only once"):
        analyze(model, scene[2](0), 3)
    with pytest.raises(ConfigError, match="chronological"):
        analyze(model, scene[2](0), 0)
    assert model.update_count == 1


def test_calibration_probes_do_not_change_background_or_update_count(config, scene):
    model, control = branch(config), branch(config)
    for current in (model, control):
        analyze(current, scene[2](0), 0)
    analyze(model, scene[2](1, ("P01",)), 1, update=False)
    analyze(model, scene[2](2, ("P02",)), 2, update=False)
    result = analyze(model, scene[2](3, ("P01",)), 3)
    baseline = analyze(control, scene[2](3, ("P01",)), 3)
    assert result["slots"] == baseline["slots"]
    assert np.array_equal(model.clean_mask, control.clean_mask)
    assert model.update_count == control.update_count == 2


def test_gap_reset_requires_re_stabilization(config, scene):
    model = branch(config)
    analyze(model, scene[2](0), 0)
    for time in (30, 33):
        result = analyze(model, scene[2](1), time)
        assert all(s["state"] == "uncertain" for s in result["slots"])
        assert result["model_reset_count"] == 1
    assert all(s["state"] == "vacant" for s in analyze(model, scene[2](1), 36)["slots"])


def test_stale_and_invalid_alignment_do_not_update_model(config, scene):
    model = branch(config)
    frame = Frame(scene[2](0), utcnow()-timedelta(seconds=60))
    result = model.analyze(frame, 0, model.analyzer.analyze(frame))
    assert result["summary"]["occupancy_pct"] is None
    assert model.update_count == 0 and model.clean_mask is None
    image = cv2.resize(scene[2](0), (320, 240))
    frame = Frame(image, utcnow())
    result = model.analyze(frame, 3, model.analyzer.analyze(frame))
    assert result["error"] == "resolution_changed" and model.update_count == 0


def test_missing_reference_is_unknown_and_missing_calibration_uncertain(config, scene):
    config.resolve(config.slot("P01")["reference_image"]).unlink()
    model = MOG2Branch(Analyzer(config))
    result = analyze(model, scene[2](0), 0)
    assert result["slots"][0]["state"] == "unknown"
    assert result["slots"][0]["foreground_ratio"] is None
    assert result["slots"][1]["state"] == "uncertain"
    assert result["slots"][1]["reason"] == "mog2_uncalibrated"


def test_model_calibration_signature_is_enforced(config, scene):
    model = branch(config)
    model.calibration["model_signature"] = "different-settings"
    assert all(s["state"] == "uncertain" for s in analyze(model, scene[2](0), 0)["slots"])


def test_mog2_does_not_join_mismatched_frame_ids(config, scene):
    model = branch(config)
    frame = Frame(scene[2](0), utcnow())
    checked = model.analyzer.analyze(frame)
    checked["frame_id"] = "different"
    with pytest.raises(ConfigError, match="identifiers"):
        model.analyze(frame, 0, checked)
