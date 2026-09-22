from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, quote
from uuid import uuid4

import cv2
import numpy as np
import requests


class SourceError(RuntimeError):
    """Messages are fixed reason codes, never camera URLs or raw library errors."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_capture_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_image(image: np.ndarray | None):
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise SourceError("invalid_image")
    h, w = image.shape[:2]
    if min(h, w) < 64 or h * w > 24_000_000 or image.dtype != np.uint8:
        raise SourceError("unsupported_image_dimensions")


def read_image(path) -> np.ndarray:
    try:
        data = np.frombuffer(path.read_bytes(), np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    except (OSError, cv2.error):
        raise SourceError("unreadable_image") from None
    validate_image(image)
    return image


def write_image(path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise SourceError("image_save_failed")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(encoded.tobytes())
    temp.replace(path)


@dataclass
class Frame:
    image: np.ndarray
    received_at: datetime
    captured_at: datetime | None = None
    frame_id: str = ""
    capture_time_status: str = "not_supplied"

    def __post_init__(self):
        if not self.frame_id:
            self.frame_id = str(uuid4())


def _stream_worker(url, connect_ms, read_ms, output):
    # Native FFmpeg diagnostics can include credentials. Suppress them at the OS
    # descriptor level before importing/opening a camera in this child process.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 2)
        os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
        if hasattr(cv2, "setLogLevel"):
            cv2.setLogLevel(0)
        cap = None
        try:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, connect_ms,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, read_ms,
            ])
            if not cap.isOpened():
                output.put(("error", "stream_open_failed"))
                return
            while True:
                ok, image = cap.read()
                if not ok:
                    try:
                        output.get_nowait()
                    except queue.Empty:
                        pass
                    output.put(("error", "stream_read_failed"))
                    return
                packet = ("frame", image, iso(utcnow()))
                try:
                    output.put_nowait(packet)
                except queue.Full:
                    try:
                        output.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        output.put_nowait(packet)
                    except queue.Full:
                        pass
        except Exception:
            try:
                output.put_nowait(("error", "stream_failed"))
            except queue.Full:
                pass
        finally:
            if cap is not None:
                cap.release()


def _snapshot_worker(config, url, headers, auth, output):
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 2)
        camera = CameraSource.__new__(CameraSource)
        camera.cfg, camera.url, camera.headers, camera.auth = config, url, headers, auth
        camera.session = requests.Session()
        try:
            output.put(("frame", camera._snapshot_direct()))
        except SourceError as exc:
            output.put(("error", str(exc)))
        except Exception:
            output.put(("error", "retrieval_failed"))
        finally:
            camera.session.close()


class CameraSource:
    def __init__(self, config):
        self.cfg = config
        self.kind = config["type"]
        if self.kind not in ("snapshot", "stream"):
            raise SourceError("recorded_video_is_not_a_live_camera_use_demo")
        self.url = os.environ.get(config["url_env"], "")
        try:
            parts = urlsplit(self.url)
            allowed = ("http", "https") if self.kind == "snapshot" else ("http", "https", "rtsp", "rtsps")
            if parts.scheme not in allowed or not parts.hostname:
                raise ValueError()
        except ValueError:
            raise SourceError("camera_url_missing_or_invalid") from None
        try:
            self.headers = json.loads(os.environ.get(config["headers_env"], "{}"))
            if not isinstance(self.headers, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.headers.items()):
                raise ValueError()
        except ValueError:
            raise SourceError("invalid_camera_headers_environment") from None
        username = os.environ.get(config["username_env"])
        password = os.environ.get(config["password_env"])
        if bool(username) != bool(password):
            raise SourceError("incomplete_camera_credentials")
        self.auth = (username, password) if username else None
        if self.kind == "stream":
            if self.headers:
                raise SourceError("stream_custom_headers_not_supported_use_snapshot_endpoint")
            if self.auth:
                if parts.username:
                    raise SourceError("duplicate_stream_credentials")
                netloc = quote(username, safe="") + ":" + quote(password, safe="") + "@" + parts.netloc
                self.url = urlunsplit(parts._replace(netloc=netloc))
        self.session = requests.Session()
        self.process = None
        self.output = None

    def close_stream(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=2)
            self.process.close()
            self.process = None
        if self.output is not None:
            self.output.cancel_join_thread()
            self.output.close()
            self.output = None

    def close(self):
        self.close_stream()
        self.session.close()

    def _snapshot_direct(self):
        connect = self.cfg.get("connect_timeout_seconds", 5)
        read = self.cfg.get("read_timeout_seconds", 10)
        deadline = time.monotonic() + connect + read
        limit = self.cfg.get("max_image_bytes", 15 * 1024 * 1024)
        try:
            # Redirects are intentionally rejected to keep credentials at the
            # configured endpoint. Use the provider's final image URL.
            with self.session.get(self.url, headers=self.headers, auth=self.auth,
                                  timeout=(connect, read), stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    raise SourceError(f"http_{response.status_code}")
                body = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    body.extend(chunk)
                    if len(body) > limit:
                        raise SourceError("image_too_large")
                    if time.monotonic() > deadline:
                        raise SourceError("retrieval_deadline_exceeded")
                raw_time = response.headers.get(self.cfg.get("capture_time_header")) if self.cfg.get("capture_time_header") else None
        except requests.Timeout:
            raise SourceError("retrieval_timeout") from None
        except requests.RequestException:
            raise SourceError("retrieval_failed") from None
        try:
            image = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR) if body else None
        except cv2.error:
            raise SourceError("invalid_image") from None
        validate_image(image)
        captured = parse_capture_time(raw_time)
        return Frame(image, utcnow(), captured, capture_time_status=("supplied" if captured else "invalid_or_missing" if self.cfg.get("capture_time_header") else "not_supplied"))

    def _snapshot(self):
        # A killable worker enforces an overall deadline even when a server
        # trickles bytes often enough to evade socket idle timeouts.
        ctx = mp.get_context("spawn")
        self.output = ctx.Queue(maxsize=1)
        self.process = ctx.Process(target=_snapshot_worker, args=(self.cfg, self.url, self.headers, self.auth, self.output), daemon=True)
        self.process.start()
        deadline = time.monotonic() + self.cfg.get("connect_timeout_seconds", 5) + self.cfg.get("read_timeout_seconds", 10) + 3
        try:
            while time.monotonic() < deadline:
                try:
                    packet = self.output.get(timeout=min(.5, max(.01, deadline - time.monotonic())))
                except queue.Empty:
                    if not self.process.is_alive():
                        raise SourceError("retrieval_worker_stopped")
                    continue
                if packet[0] == "error":
                    raise SourceError(packet[1])
                return packet[1]
            raise SourceError("retrieval_deadline_exceeded")
        finally:
            self.close_stream()

    def _stream(self):
        if self.process is None:
            ctx = mp.get_context("spawn")
            self.output = ctx.Queue(maxsize=1)
            self.process = ctx.Process(target=_stream_worker, args=(
                self.url, int(self.cfg.get("connect_timeout_seconds", 5) * 1000),
                int(self.cfg.get("read_timeout_seconds", 10) * 1000), self.output), daemon=True)
            self.process.start()
        deadline = time.monotonic() + self.cfg.get("connect_timeout_seconds", 5) + self.cfg.get("read_timeout_seconds", 10)
        while time.monotonic() < deadline:
            try:
                packet = self.output.get(timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if not self.process.is_alive():
                    raise SourceError("stream_stopped")
                continue
            if packet[0] == "error":
                raise SourceError(packet[1])
            _, image, received = packet
            received_at = parse_capture_time(received)
            if (utcnow() - received_at).total_seconds() > self.cfg.get("read_timeout_seconds", 10):
                continue
            validate_image(image)
            return Frame(image, received_at)
        raise SourceError("stream_timeout")

    def read(self):
        for attempt in range(self.cfg.get("attempts", 3)):
            try:
                return self._snapshot() if self.kind == "snapshot" else self._stream()
            except SourceError:
                self.close_stream()
                if attempt == self.cfg.get("attempts", 3) - 1:
                    raise
                time.sleep(2 ** attempt)
