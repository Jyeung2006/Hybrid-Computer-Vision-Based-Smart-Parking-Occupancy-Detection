import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import pytest

from parking_probe.sources import CameraSource, SourceError, parse_capture_time, utcnow
from parking_probe.cli import main


@pytest.fixture
def camera_server(scene):
    image = scene[2](7, ("P02",))
    encoded = cv2.imencode(".jpg", image)[1].tobytes()
    counts = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            counts[self.path] = counts.get(self.path, 0) + 1
            if self.path == "/retry" and counts[self.path] == 1:
                self.send_response(503)
                self.end_headers()
                return
            if self.path == "/auth" and self.headers.get("X-Test-Key") != "private-test-token":
                self.send_response(401)
                self.end_headers()
                return
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/ok")
                self.end_headers()
                return
            if self.path == "/slow":
                time.sleep(.7)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame" if self.path == "/stream" else "image/jpeg")
            self.send_header("X-Capture-Time", utcnow().isoformat())
            self.end_headers()
            try:
                if self.path == "/stream":
                    for _ in range(100):
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(encoded)).encode() + b"\r\n\r\n" + encoded + b"\r\n")
                        self.wfile.flush()
                        time.sleep(.05)
                else:
                    self.wfile.write(b"not an image" if self.path == "/bad" else encoded)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", counts
    server.shutdown()
    server.server_close()
    thread.join(2)


def make_source(config, monkeypatch, url, **changes):
    cfg = dict(config.data["source"], attempts=1, **changes)
    monkeypatch.setenv("PARKING_CAMERA_URL", url)
    return CameraSource(cfg)


def test_http_frame_and_timestamp(config, monkeypatch, camera_server):
    source = make_source(config, monkeypatch, camera_server[0] + "/ok", capture_time_header="X-Capture-Time")
    try:
        frame = source.read()
        assert frame.image.shape == (480, 640, 3)
        assert frame.captured_at is not None and frame.capture_time_status == "supplied"
        assert frame.received_at >= frame.captured_at
        assert source.process is None
    finally:
        source.close()


@pytest.mark.parametrize("path,expected", [("/bad", "invalid_image"), ("/redirect", "http_302"), ("/auth", "http_401")])
def test_http_failures(config, monkeypatch, camera_server, path, expected):
    source = make_source(config, monkeypatch, camera_server[0] + path)
    try:
        with pytest.raises(SourceError, match=expected):
            source.read()
    finally:
        source.close()


def test_http_timeout(config, monkeypatch, camera_server):
    source = make_source(config, monkeypatch, camera_server[0] + "/slow", read_timeout_seconds=.1)
    started = time.monotonic()
    try:
        with pytest.raises(SourceError, match="retrieval_timeout"):
            source.read()
        assert time.monotonic() - started < 7
    finally:
        source.close()


def test_auth_headers_and_unknown_capture_time(config, monkeypatch, camera_server):
    monkeypatch.setenv("PARKING_CAMERA_HEADERS", json.dumps({"X-Test-Key": "private-test-token"}))
    source = make_source(config, monkeypatch, camera_server[0] + "/auth")
    try:
        frame = source.read()
        assert frame.captured_at is None
    finally:
        source.close()


def test_bounded_retry_recovers(config, monkeypatch, camera_server):
    source = make_source(config, monkeypatch, camera_server[0] + "/retry")
    source.cfg["attempts"] = 2
    try:
        assert source.read().image is not None
        assert camera_server[1]["/retry"] == 2
    finally:
        source.close()


def test_stream_worker_reads_and_closes(config, monkeypatch, camera_server):
    source = make_source(config, monkeypatch, camera_server[0] + "/stream", type="stream")
    try:
        frame = source.read()
        assert frame.image.shape == (480, 640, 3)
        assert frame.captured_at is None
        assert source.process.is_alive()
        time.sleep(.15)
        next_frame = source.read()
        assert next_frame.received_at >= frame.received_at
        assert (utcnow() - next_frame.received_at).total_seconds() < 2
    finally:
        source.close()
    assert source.process is None


def test_image_size_limit(config, monkeypatch, camera_server):
    source = make_source(config, monkeypatch, camera_server[0] + "/ok", max_image_bytes=1024)
    try:
        with pytest.raises(SourceError, match="image_too_large"):
            source.read()
    finally:
        source.close()


def test_local_recordings_not_accepted_as_live(config, monkeypatch):
    with pytest.raises(SourceError, match="camera_url_missing_or_invalid"):
        make_source(config, monkeypatch, "C:/video.mp4")


def test_bad_urls_do_not_echo_credentials(config, monkeypatch):
    with pytest.raises(SourceError) as caught:
        make_source(config, monkeypatch, "secret-api-key")
    assert "secret-api-key" not in str(caught.value)


def test_timestamp_timezone_required():
    assert parse_capture_time("2026-09-09T12:00:00") is None
    assert parse_capture_time("not a time") is None
    assert parse_capture_time("2026-09-09T12:00:00+08:00").hour == 4


def test_online_run_writes_current_result_then_clears_failure(config, monkeypatch, camera_server, tmp_path):
    config.data["source"]["attempts"] = 1
    for slot in config.data["slots"]:
        slot["calibration"] = None
    config.save()
    monkeypatch.setenv("PARKING_CAMERA_URL", camera_server[0] + "/ok")
    arguments = ["--config", str(config.path), "run", "--frames", "1", "--out", str(tmp_path / "live")]
    assert main(arguments) == 0
    success = json.loads((tmp_path / "live/latest.json").read_text())
    assert success["input_mode"] == "online_camera"
    assert success["retrieval_status"] == "success"
    assert success["summary"]["occupancy_min_pct"] == 0
    assert success["summary"]["occupancy_max_pct"] == 100
    monkeypatch.setenv("PARKING_CAMERA_URL", camera_server[0] + "/auth")
    assert main(arguments) == 2
    failed = json.loads((tmp_path / "live/latest.json").read_text())
    assert failed["stale"] and failed["retrieval_status"] == "failed"
    assert failed["summary"]["occupancy_min_pct"] is None
    history = (tmp_path / "live/history.jsonl").read_text().splitlines()
    assert len(history) == 2 and json.loads(history[0])["frame_id"] == success["frame_id"]
