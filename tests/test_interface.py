from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import threading
import time
import tkinter as tk

import numpy as np
import cv2
import pytest

from parking_probe import interface
from parking_probe.interface_model import Review, chart_data, ring_segments
from parking_probe.sources import Frame, utcnow


def pair(clip="chad-1", when=0, states=(("occupied", "occupied"), ("vacant", "vacant"), ("occupied", "uncertain"))):
    return {"recording_id": clip, "reference": {"sample_time_seconds": when, "video_position_seconds": when},
            "mog2": {"processed_at": utcnow().isoformat()},
            "rows": [{"bay_id": f"CHAD-P{i+1:03d}", "reference_state": r, "mog2_state": m} for i, (r, m) in enumerate(states)]}


def test_chart_includes_unresolved_and_never_counts_four_recordings_as_twelve():
    review = Review()
    review.add_samples({"recordings": [pair(f"chad-{i}") for i in range(1, 5)]})
    rows, summary = chart_data(review.at("chad-2", 0))
    assert [r["state"] for r in rows] == ["occupied", "vacant", "uncertain"]
    assert summary["total_monitored_bays"] == 3
    assert summary["occupancy_pct"] is None
    assert summary["occupancy_min_pct"] == pytest.approx(100/3)
    assert summary["occupancy_max_pct"] == pytest.approx(200/3)
    assert sum(abs(s[2]) for s in ring_segments(summary)) == pytest.approx(360)
    assert [s[0] for s in ring_segments(summary)] == ["occupied", "vacant", "uncertain"]


def test_seek_uses_only_past_samples_in_selected_recording_and_resets_windows():
    review = Review()
    for when in (0, 3, 6):
        review.add_samples({"recordings": [pair("chad-1", when), pair("chad-2", when)]})
    review.add_windows([{"recording_id": "chad-1", "reference": {"window_end_seconds": 10}},
                        {"recording_id": "chad-1", "reference": {"window_end_seconds": 20}}])
    assert review.at("chad-1", 2.999)["reference"]["sample_time_seconds"] == 0
    assert review.at("chad-2", 3)["reference"]["sample_time_seconds"] == 3
    assert review.at("chad-1", 33)["reference"]["sample_time_seconds"] == 6
    assert review.at("chad-1", -1) is None
    assert review.at("chad-4", 12) is None
    assert review.window_at("chad-1", 9.999) is None
    assert review.window_at("chad-1", 10)["reference"]["window_end_seconds"] == 10
    assert review.window_at("chad-1", 21)["reference"]["window_end_seconds"] == 20
    assert review.window_at("chad-1", 4) is None
    assert review.window_at("chad-2", 21) is None


@pytest.mark.parametrize("value", [None, pair(states=(("unknown", "unknown"),)*3)])
def test_unavailable_is_not_zero_occupancy(value):
    rows, summary = chart_data(value)
    assert summary["unknown"] == 3
    assert summary["occupancy_min_pct"] is None and summary["occupancy_pct"] is None
    assert ring_segments(summary) == [("unknown", 90.0, -360.0)]


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def app(tk_root):
    root = tk.Toplevel(tk_root)
    root.withdraw()
    window = interface.ParkingInterface(root, autostart=False)
    yield window
    window.close()


def test_ui_decisions_render_and_video_failure_clears_chart(app):
    app.render_observation(pair())
    assert app.rate.cget("text") == "11.1 - 88.9% occupied"
    assert len(app.table.get_children()) == 9
    assert app.table.item(app.table.get_children()[2])["values"][-1] == "UNCERTAIN"
    app.playback_failed()
    assert app.rate.cget("text") == "Unavailable"
    assert all(app.table.item(i)["values"][-1] == "UNKNOWN" for i in app.table.get_children())
    assert app.photo is None


def test_switching_camera_uses_its_inventory_without_borrowing_old_evidence(app):
    app.render_observation(pair())
    app.selection.set('chad-camera-2')
    app.select_clip()
    assert app.view.camera == 'Camera 2'
    assert len(app.table.get_children()) == 5
    assert app.rate.cget('text') == 'Unavailable'
    assert '5 unknown' in app.video_counts.cget('text')
    assert app.site_selection.get() == 'CHAD car park'
    app.selection.set('overhead-1')
    app.select_clip()
    assert app.view.site == 'overhead'
    assert len(app.table.get_children()) == 69
    assert all(str(app.table.item(i)['values'][0]).startswith('OVER-') for i in app.table.get_children())


def test_live_disconnect_and_old_worker_frames_cannot_restore_preview(app):
    image = np.zeros((180, 320, 3), np.uint8)
    frame = (image, utcnow(), None, time.monotonic(), 15)
    app.handle_live_event(0, "frame", frame)
    assert app.live_photo is not None
    assert "unknown" in app.live_status.cget("text")
    app.disconnect_live()
    app.handle_live_event(0, "frame", frame)
    assert app.live_photo is None
    assert app.live_label.cget("text") == "Live camera disconnected"
    app.handle_live_event(1, "frame", frame)
    assert app.live_photo is not None
    app.handle_live_event(1, "error", "retrieval_timeout")
    assert app.live_photo is None
    assert "Occupancy unavailable" in app.live_status.cget("text")


def test_stale_frame_and_expired_preview_clear_live_view(app):
    image = np.zeros((180, 320, 3), np.uint8)
    app.handle_live_event(0, "frame", (image, utcnow(), None, time.monotonic()-20, 15))
    assert app.live_photo is None
    app.handle_live_event(0, "frame", (image, utcnow(), None, time.monotonic(), 15))
    assert app.live_photo is not None
    app.live_deadline = time.monotonic()-1
    # Avoid leaving two scheduled tick callbacks in this directly driven test.
    app.root.after_cancel(app.timer)
    app.tick()
    assert app.live_photo is None


def test_live_worker_sanitizes_error_and_rejects_old_capture(config, monkeypatch):
    channel = queue.Queue(maxsize=2)
    class FakeCamera:
        kind = "snapshot"
        closed = False
        def __init__(self, cfg): pass
        def read(self):
            return Frame(np.zeros((64, 64, 3), np.uint8), utcnow(), utcnow()-timedelta(seconds=60))
        def close(self): FakeCamera.closed = True
    monkeypatch.setattr(interface, "CameraSource", FakeCamera)
    interface.live_worker(config.path, threading.Event(), channel, 7)
    assert channel.get_nowait() == (7, "error", "source_capture_time_stale_or_invalid")
    assert FakeCamera.closed
    def fail(self): raise RuntimeError("https://private:secret@camera.invalid/")
    monkeypatch.setattr(FakeCamera, "read", fail)
    interface.live_worker(config.path, threading.Event(), channel, 8)
    assert channel.get_nowait() == (8, "error", "camera_configuration_or_connection_failed")


def test_live_queue_keeps_recent_packets_bounded():
    channel = queue.Queue(maxsize=2)
    for index in range(10):
        interface.put_latest(channel, (0, "frame", index))
    assert channel.qsize() == 2
    assert channel.get_nowait()[2] == 8
    assert channel.get_nowait()[2] == 9


def test_missing_camera_url_is_actionable(config, monkeypatch):
    monkeypatch.delenv("PARKING_CAMERA_URL", raising=False)
    channel = queue.Queue(maxsize=2)
    interface.live_worker(config.path, threading.Event(), channel, 1)
    assert channel.get_nowait() == (1, "error", "camera_url_missing_or_invalid")


@pytest.mark.parametrize("kind", ["snapshot", "stream"])
def test_live_viewer_worker_decodes_local_http_input(config, monkeypatch, kind):
    # This is a synthetic loopback camera, not evidence of a public live source.
    encoded = cv2.imencode(".jpg", np.full((180, 320, 3), 110, np.uint8))[1].tobytes()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg" if kind == "snapshot" else "multipart/x-mixed-replace; boundary=frame")
            self.send_header("X-Capture-Time", utcnow().isoformat())
            self.end_headers()
            try:
                if kind == "snapshot":
                    self.wfile.write(encoded)
                else:
                    for _ in range(100):
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                         str(len(encoded)).encode() + b"\r\n\r\n" + encoded + b"\r\n")
                        self.wfile.flush()
                        time.sleep(.05)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    monkeypatch.setenv("PARKING_CAMERA_URL", f"http://127.0.0.1:{server.server_port}/camera")
    config.data["source"].update(type=kind, capture_time_header="X-Capture-Time", attempts=1,
                                connect_timeout_seconds=2, read_timeout_seconds=2)
    config.path.write_text(json.dumps(config.data))
    channel, stop = queue.Queue(maxsize=2), threading.Event()
    worker = threading.Thread(target=interface.live_worker, args=(config.path, stop, channel, 2), daemon=True)
    try:
        worker.start()
        generation, event, value = channel.get(timeout=12)
        assert generation == 2 and event == "frame", value
        assert value[0].shape == (540, 960, 3)
        assert (value[2] is not None) == (kind == "snapshot")
    finally:
        stop.set()
        worker.join(8)
        server.shutdown()
        server.server_close()
        server_thread.join(2)
    assert not worker.is_alive()
