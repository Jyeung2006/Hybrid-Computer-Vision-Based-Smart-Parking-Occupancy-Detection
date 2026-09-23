"""Deterministic synthetic integration check; never uses a real camera."""
from __future__ import annotations

import csv
import json
import platform
from pathlib import Path

import cv2
import numpy as np

from parking_probe.config import Config, atomic_json
from parking_probe.evaluation import calibrate, evaluate
from parking_probe.output import Reporter
from parking_probe.sources import Frame, utcnow, write_image
from parking_probe.vision import Analyzer


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / "runs" / "self-test"
    destination.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1701)
    background = cv2.GaussianBlur(rng.integers(20, 180, (480, 800, 3), dtype=np.uint8), (3, 3), 0)
    slots = [{"id": "TEST01", "polygon": [[140, 160], [310, 160], [310, 330], [140, 330]]},
             {"id": "TEST02", "polygon": [[480, 160], [650, 160], [650, 330], [480, 330]]}]
    for slot in slots:
        cv2.fillPoly(background, [np.int32(slot["polygon"])], (85, 85, 85))
    cv2.rectangle(background, (0, 0), (800, 65), (20, 20, 20), -1)
    cv2.putText(background, "SYNTHETIC SOFTWARE TEST - NOT PARKING FOOTAGE", (15, 38), cv2.FONT_HERSHEY_SIMPLEX, .72, (255, 255, 255), 2)
    write_image(destination / "setup.png", background)
    data = json.loads((root / "config.example.json").read_text())
    data.update(source_id="synthetic-software-test", setup_image="setup.png", slots=slots)
    for slot in slots:
        reference = slot["id"] + "-empty.png"
        write_image(destination / reference, background)
        slot["reference_image"] = reference
    atomic_json(destination / "config.json", data)

    def generate(name, count, offset, periods):
        rows = []
        for i in range(count):
            sample = background.copy()
            random = np.random.default_rng(offset + i)
            occupied_id = slots[i % 2]["id"]
            for slot in slots:
                x, y = slot["polygon"][0]
                patch = sample[y + 2:y + 168, x + 2:x + 168]
                patch[:] = np.clip(85 + random.integers(-4, 5, patch.shape), 0, 255)
                if slot["id"] == occupied_id:
                    cv2.rectangle(sample, (x + 12, y + 10), (x + 158, y + 158), (220 + (offset + i) % 10,) * 3, -1)
                rows.append({"frame_path": f"{name}/{i:03d}.png", "slot_id": slot["id"],
                    "label": "occupied" if slot["id"] == occupied_id else "vacant", "session_id": periods[i % len(periods)]})
            write_image(destination / name / f"{i:03d}.png", sample)
        manifest = destination / (name + ".csv")
        with manifest.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return manifest, sample

    calibration_path, _ = generate("calibration", 20, 1, ["synthetic-calibration"])
    testing_path, sample = generate("evaluation", 30, 100, ["synthetic-test-a", "synthetic-test-b"])
    config = Config(destination / "config.json")
    fitting = calibrate(config, calibration_path)
    report = evaluate(config, testing_path)
    report.update(data_provenance="synthetic_generated_test_patterns",
                  real_camera_access="not_configured", real_world_validation="pending_authorized_indoor_camera_and_manual_labels",
                  minimum_evaluation_requirements_met=False,
                  dataset_shape_note="30 generated frames and simulated session labels; not actual recording periods or manual ground truth",
                  environment={"python": platform.python_version(), "opencv": cv2.__version__, "numpy": np.__version__, "platform": platform.platform()})
    atomic_json(destination / "synthetic-report.json", report)
    atomic_json(destination / "calibration-report.json", fitting)
    analyzer = Analyzer(config)
    result = analyzer.analyze(Frame(sample, utcnow()))
    result["input_mode"] = "synthetic_software_test"
    Reporter(destination / "preview", config.data["slots"]).write(result, sample)
    failure = analyzer.failure("simulated_retrieval_timeout")
    failure["input_mode"] = "synthetic_software_test"
    Reporter(destination / "failure-preview", config.data["slots"]).write(failure)
    print(json.dumps({k: v for k, v in report.items() if k != "observations"}, indent=2))
    print(f"Synthetic artifacts: {destination}")


if __name__ == "__main__":
    main()

