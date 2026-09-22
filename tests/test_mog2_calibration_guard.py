"""Invalid source frames cannot become calibration evidence or model updates."""
import threading

import cv2
import numpy as np
import pytest

from parking_probe import mog2_calibration
from parking_probe.config import ConfigError
from parking_probe.sources import write_image


@pytest.mark.parametrize("label_invalid_frame", [False, True])
def test_calibration_rejects_invalid_labels_but_skips_unlabelled_drift(
    config, scene, tmp_path, monkeypatch, label_invalid_frame
):
    valid = scene[2](1)
    moved = cv2.warpAffine(valid, np.float32([[1, 0, 35], [0, 1, 0]]), (640, 480))
    frames = [valid, moved]
    index = int(label_invalid_frame)
    sample = tmp_path / f"source-{index:06d}.png"
    write_image(sample, frames[index])
    (tmp_path / "calibration-labels.csv").write_text(
        "frame_path,slot_id,label,session_id\n" + f"{sample.name},P01,vacant,test-source\n"
    )

    class Recording:
        count, fps = 2, 1

        def __init__(self, *args):
            pass

        def read(self, frame_index):
            return frames[frame_index].copy()

        def close(self):
            pass

    models = []
    original = mog2_calibration.MOG2Branch

    class TrackedBranch(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            models.append(self)

    monkeypatch.setattr(mog2_calibration, "recording_for_recipe", lambda path, recipe: Recording())
    monkeypatch.setattr(mog2_calibration, "MOG2Branch", TrackedBranch)
    args = (config, {"source_resolution": [640, 480], "analysis_resolution": [640, 480]},
            {"test-source": tmp_path / "test.avi"}, 1, lambda *args: None, threading.Event())
    if label_invalid_frame:
        with pytest.raises(ConfigError, match="failed alignment/validation"):
            mog2_calibration.prepare_mog2(*args)
        assert not list(tmp_path.glob("mog2-calibration-*.json"))
    else:
        report = mog2_calibration.prepare_mog2(*args)
        assert len(report["samples"]) == 1
        assert report["samples"][0]["frame_index"] == 0
    # The valid chronological frame updates once; the shifted one never does.
    assert models[-1].update_count == 1
