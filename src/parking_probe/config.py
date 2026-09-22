from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np


class ConfigError(ValueError):
    pass


def atomic_json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def polygon_signature(points: list) -> str:
    return hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()


def validate_polygon(points: list, width: int, height: int) -> np.ndarray:
    if not isinstance(points, list) or len(points) < 3:
        raise ConfigError("A parking polygon needs at least three corners.")
    if any(not isinstance(p, list) or len(p) != 2 or
           any(type(v) is not int for v in p) for p in points):
        raise ConfigError("Polygon corners must be integer [x, y] pairs.")
    if len({tuple(p) for p in points}) != len(points):
        raise ConfigError("Polygon corners must be distinct.")
    if any(x < 0 or y < 0 or x >= width or y >= height for x, y in points):
        raise ConfigError("A polygon extends outside the setup image.")

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, c):
        return cross(a, b, c) == 0 and min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    def intersects(a, b, c, d):
        v = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
        return (v[0] * v[1] < 0 and v[2] * v[3] < 0) or any((on_segment(a, b, c), on_segment(a, b, d), on_segment(c, d, a), on_segment(c, d, b)))

    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if intersects(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n]):
                raise ConfigError("Polygon edges must not cross or touch.")
    polygon = np.array(points, dtype=np.int32)
    if abs(cv2.contourArea(polygon)) < 25:
        raise ConfigError("The parking polygon is too small (minimum 25 square pixels).")
    return polygon


class Config:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ConfigError("Cannot read configuration JSON.") from None
        d = self.data
        if not isinstance(d, dict) or d.get("version") != 1:
            raise ConfigError("Configuration version must be 1.")
        self.validate_id(d.get("source_id"))
        source = d.get("source", {})
        if not isinstance(source, dict) or source.get("type") not in ("snapshot", "stream", "recorded_video"):
            raise ConfigError("Source type must be snapshot, stream or recorded_video.")
        if "url" in source or "headers" in source or "password" in source:
            raise ConfigError("Put camera addresses and credentials in environment variables, not configuration.")
        required_env = () if source["type"] == "recorded_video" else ("url_env", "headers_env", "username_env", "password_env")
        for key in required_env:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source.get(key, "")):
                raise ConfigError("Source environment variable names are required.")
        for key, value in [("interval_seconds", d.get("interval_seconds", 3)),
                           ("stale_after_seconds", d.get("stale_after_seconds", 15)),
                           ("connect_timeout_seconds", source.get("connect_timeout_seconds", 5)),
                           ("read_timeout_seconds", source.get("read_timeout_seconds", 10))]:
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ConfigError(f"{key} must be a positive finite number.")
        attempts = source.get("attempts", 3)
        if type(attempts) is not int or not 1 <= attempts <= 5:
            raise ConfigError("Source attempts must be between 1 and 5.")
        limit = source.get("max_image_bytes", 15 * 1024 * 1024)
        if type(limit) is not int or not 1024 <= limit <= 100 * 1024 * 1024:
            raise ConfigError("max_image_bytes must be between 1 KiB and 100 MiB.")
        alignment = d.get("alignment", {})
        if type(alignment.get("min_inliers", 12)) is not int or alignment.get("min_inliers", 12) < 6:
            raise ConfigError("Alignment needs at least six inliers.")
        displacement = alignment.get("max_displacement_pixels", 8)
        if type(displacement) not in (int, float) or not math.isfinite(displacement) or displacement <= 0:
            raise ConfigError("Alignment displacement must be positive.")
        if not isinstance(d.get("slots"), list):
            raise ConfigError("slots must be a list.")
        ids = []
        for slot in d["slots"]:
            if not isinstance(slot, dict):
                raise ConfigError("Each slot must be an object.")
            self.validate_id(slot.get("id"))
            ids.append(slot["id"])
        if len(ids) != len(set(ids)):
            raise ConfigError("Parking-space IDs must be unique.")

    @staticmethod
    def validate_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
            raise ConfigError("IDs must use 1–64 letters, digits, underscores or hyphens.")

    def resolve(self, value: str | None) -> Path | None:
        return (self.path.parent / value).resolve() if value else None

    def relative(self, path: Path) -> str:
        import os
        return Path(os.path.relpath(path.resolve(), self.path.parent)).as_posix()

    def save(self):
        atomic_json(self.path, self.data)

    def slot(self, slot_id):
        for slot in self.data["slots"]:
            if slot["id"] == slot_id:
                return slot
        raise ConfigError("Parking-space ID is not configured.")
