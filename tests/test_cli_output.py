import json

import pytest

from parking_probe.cli import main
from parking_probe.config import Config, ConfigError, atomic_json
from parking_probe.output import Reporter
from parking_probe.sources import Frame, read_image, utcnow, write_image
from parking_probe.vision import Analyzer


def test_report_success_then_failure(config, tmp_path, scene):
    analyzer = Analyzer(config)
    reporter = Reporter(tmp_path / "output", config.data["slots"])
    image = scene[2](1)
    reporter.write(analyzer.analyze(Frame(image, utcnow())), image)
    reporter.write(analyzer.failure("retrieval_timeout"))
    latest = json.loads((tmp_path / "output/latest.json").read_text())
    assert latest["stale"] and latest["summary"]["occupancy_pct"] is None
    assert len((tmp_path / "output/history.jsonl").read_text().splitlines()) == 2
    assert read_image(tmp_path / "output/latest.png").shape[0] > 480
    assert (tmp_path / "output/slots.csv").exists()


def test_no_camera_reports_missing_access(config, monkeypatch, tmp_path):
    monkeypatch.delenv("PARKING_CAMERA_URL", raising=False)
    result = main(["--config", str(config.path), "check", "--count", "1", "--out", str(tmp_path / "connection.json")])
    assert result == 2
    report = json.loads((tmp_path / "connection.json").read_text())
    assert report["successful_frames"] == 0
    assert report["observations"][0]["error"] == "camera_url_missing_or_invalid"


def test_invalid_config_rejected(config):
    config.data["interval_seconds"] = 0
    config.save()
    with pytest.raises(ConfigError):
        Config(config.path)


def test_import_polygons_and_reference_requires_confirmation(config, tmp_path, scene):
    config.data["setup_image"] = None
    config.data["slots"] = []
    config.save()
    atomic_json(tmp_path / "polygons.json", scene[1])
    args = ["--config", str(config.path)]
    assert main(args + ["configure", "--frame", str(tmp_path / "setup.png"), "--polygons-file", str(tmp_path / "polygons.json")]) == 0
    assert main(args + ["reference", "--slot", "P01", "--frame", str(tmp_path / "setup.png")]) == 2
    assert main(args + ["reference", "--slot", "P01", "--frame", str(tmp_path / "setup.png"), "--confirm-empty"]) == 0
    assert Config(config.path).slot("P01")["reference_image"]


def test_offline_analysis_is_explicit(config, tmp_path, scene):
    write_image(tmp_path / "diagnostic.png", scene[2](1))
    assert main(["--config", str(config.path), "analyze-image", "--frame", str(tmp_path / "diagnostic.png"), "--out", str(tmp_path / "offline")]) == 0
    result = json.loads((tmp_path / "offline/latest.json").read_text())
    assert result["input_mode"] == "offline_diagnostic"

