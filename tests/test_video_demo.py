import hashlib
import json
import cv2
import numpy as np
import pytest
import requests

from parking_probe import video_demo as demo
from parking_probe.cli import main
from parking_probe.output import summary_text
from parking_probe.sources import CameraSource, SourceError


def test_download_and_verified_cache(tmp_path, monkeypatch):
    payload = b"test-media-bytes"
    monkeypatch.setattr(demo, "VIDEO_BYTES", len(payload))
    monkeypatch.setattr(demo, "VIDEO_SHA256", hashlib.sha256(payload).hexdigest())
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield payload[:5]
            yield payload[5:]

    def get(url, **kwargs):
        calls.append(url)
        assert kwargs["timeout"] == (5, 10)
        return Response()

    monkeypatch.setattr(demo.requests, "get", get)
    path, status = demo.download_video(tmp_path)
    assert status == "downloaded_and_verified" and path.read_bytes() == payload
    assert demo.download_video(tmp_path)[1] == "verified_cache"
    assert calls == [demo.VIDEO_URL]
    assert json.loads((tmp_path / "download.json").read_text())["original_capture_time"] is None
    path.write_bytes(b"corrupt cache")
    assert demo.download_video(tmp_path)[1] == "downloaded_and_verified"
    assert len(calls) == 2


def test_download_failure_bounded_and_partial_removed(tmp_path, monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout("raw provider text")

    monkeypatch.setattr(demo.requests, "get", fail)
    monkeypatch.setattr(demo.time, "sleep", lambda _: None)
    (tmp_path / "indoor.mp4.part").write_bytes(b"interrupted")
    with pytest.raises(SourceError, match="demo_download_failed"):
        demo.download_video(tmp_path)
    assert len(calls) == 2
    assert not (tmp_path / "indoor.mp4.part").exists()


def test_local_video_decode_and_bounds(tmp_path):
    path = tmp_path / "test.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (80, 80))
    assert writer.isOpened()
    for i in range(10):
        writer.write(np.full((80, 80, 3), i * 20, np.uint8))
    writer.release()
    video = demo.RecordedVideo(path)
    try:
        assert video.duration == 1
        assert video.frame_at(0).shape == (540, 960, 3)
        assert video.frame_at(9).mean() > video.frame_at(0).mean() + 100
        with pytest.raises(SourceError, match="out_of_range"):
            video.frame_at(10)
    finally:
        video.close()


@pytest.mark.parametrize("failure", [False, True])
def test_demo_eof_and_failure_metadata(tmp_path, config, scene, monkeypatch, failure):
    class Video:
        fps, frame_count, duration = 10, 20, 2.0

        def __init__(self, path):
            pass

        def frame_at(self, index):
            if failure and index >= 10:
                raise SourceError("demo_frame_decode_failed")
            return scene[2](1)

        def close(self):
            pass

    monkeypatch.setattr(demo, "RecordedVideo", Video)
    monkeypatch.setattr(demo, "prepare_preset", lambda *args: config)
    monkeypatch.setattr(demo, "download_video", lambda *args: (tmp_path / "test.mp4", "verified_cache"))
    output = tmp_path / "result"
    args = ["--config", str(tmp_path / "does-not-exist.json"), "demo", "--headless", "--out", str(output)]
    assert main(args) == (2 if failure else 0)
    report = json.loads((output / "run.json").read_text())
    latest = json.loads((output / "latest.json").read_text())
    assert report["status"] == ("failed" if failure else "complete")
    assert report["processed_frames"] == (3 if failure else 4)
    assert latest["video_position_seconds"] == (1 if failure else 1.5)
    assert latest["input_mode"] == "recorded_video"
    assert latest["frame_age_seconds"] is None and latest["source_captured_at"] is None
    assert latest["summary"]["total_monitored_bays"] == 0
    assert "test regions" in summary_text(latest)
    assert (output / "annotated.mp4").stat().st_size > 0
    assert "video_position_seconds" in (output / "summary.csv").read_text().splitlines()[0]
    if failure:
        assert latest["stale"] and latest["summary"]["occupancy_min_pct"] is None
    else:
        assert not latest["stale"]
    # A second run cannot mix its history or overwrite an existing result.
    assert main(args) == 2


def test_recording_cannot_be_opened_as_live_camera():
    with pytest.raises(SourceError, match="not_a_live_camera"):
        CameraSource({"type": "recorded_video"})


@pytest.mark.parametrize("step", ["nan", "0", "-1", "11"])
def test_demo_invalid_step_does_not_need_camera_config(step):
    assert main(["--config", "missing.json", "demo", "--headless", "--step", step]) == 2
