import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from parking_probe.config import Config, atomic_json
from parking_probe.sources import write_image


@pytest.fixture(autouse=True)
def isolate_camera_credentials(monkeypatch):
    for name in ("PARKING_CAMERA_URL", "PARKING_CAMERA_HEADERS", "PARKING_CAMERA_USERNAME", "PARKING_CAMERA_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def scene():
    random = np.random.default_rng(1234)
    background = random.integers(20, 200, (480, 640, 3), dtype=np.uint8)
    background = cv2.GaussianBlur(background, (3, 3), 0)
    slots = [dict(id="P01", polygon=[[100, 150], [240, 150], [240, 300], [100, 300]]),
             dict(id="P02", polygon=[[350, 150], [490, 150], [490, 300], [350, 300]])]
    for slot in slots:
        cv2.fillPoly(background, [np.int32(slot["polygon"])], (90, 90, 90))

    def make(seed=0, occupied=()):
        image = background.copy()
        rng = np.random.default_rng(seed)
        for slot in slots:
            x, y = slot["polygon"][0]
            patch = image[y + 2:y + 148, x + 2:x + 138]
            patch[:] = np.clip(90 + rng.integers(-4, 5, patch.shape), 0, 255)
            if slot["id"] in occupied:
                cv2.rectangle(image, (x + 12, y + 10), (x + 125, y + 140), (220 + seed % 12,) * 3, -1)
                cv2.rectangle(image, (x + 30, y + 30), (x + 105, y + 60), (150,) * 3, -1)
        return image

    return background, slots, make


@pytest.fixture
def config(tmp_path, scene):
    data = json.loads(Path("config.example.json").read_text())
    background, slots, make = scene
    write_image(tmp_path / "setup.png", background)
    data["setup_image"] = "setup.png"
    data["slots"] = slots
    for slot in slots:
        path = tmp_path / (slot["id"] + "-reference.png")
        write_image(path, background)
        slot["reference_image"] = path.name
    atomic_json(tmp_path / "config.json", data)
    return Config(tmp_path / "config.json")
