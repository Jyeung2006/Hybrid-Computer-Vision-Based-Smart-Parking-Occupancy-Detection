import copy
import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from parking_probe.opencv_first import DECISION_POLICY
from parking_probe.web_server import ResultStore, AnalysisJob, make_server


@pytest.fixture
def root(tmp_path):
    presets = tmp_path / "presets"
    presets.mkdir()
    for name, ids in (("chad-camera-1-expanded", ["B01", "B02", "B03"]),
                      ("overhead-all-bays", ["O1", "O2"])):
        (presets / (name + ".json")).write_text(json.dumps({"slots": [{"bay_id": b} for b in ids]}))
    return tmp_path


def pair(recording="chad-1", states=("occupied", "vacant", "unknown")):
    return {"recording_id": recording, "camera_id": "chad-camera-1",
        "reference": {"video_id": recording, "frame_id": recording + "-1", "sample_time_seconds": 3,
                      "stale": False, "error": None, "analysis_status": "estimated", "alignment": {"ok": True}},
        "final": {"decision_policy": DECISION_POLICY, "frame_id": recording + "-1", "processed_at": "2026-09-27T00:00:00+00:00"},
        "rows": [{"bay_id": f"B{i + 1:02}", "recording_id": recording, "frame_id": recording + "-1",
                  "final_state": state, "final_provisional": i == 0,
                  "final_confirmed_by": "provisional_occupied", "final_reason": "test"} for i, state in enumerate(states)]}


def write(root, pairs, run="20260927", tail=""):
    path = root / "runs/areas" / run / "chad/history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"recordings": pairs}) + "\n" + tail)
    return path


def test_recomputes_final_counts_and_keeps_provisional(root):
    write(root, [pair()])
    data = ResultStore(root).snapshot()
    assert data["mode"] == "recorded" and data["live_availability"] is False
    assert data["totals"] == dict(capacity=5, occupied=1, vacant=1, uncertain=0, unknown=3, provisional_occupied=1, provisional_vacant=0)
    assert data["areas"][0]["source"]["sample_seconds"] == 3
    assert data["areas"][0]["bays"][0]["source"] == "provisional_occupied"
    assert data["areas"][1]["has_sample"] is False


def test_selection_never_sums_recordings_or_overlapping_views(root):
    write(root, [pair(), pair("chad-2", ("occupied",) * 3), pair("chad-camera-2", ("occupied",) * 3)])
    store = ResultStore(root)
    assert store.snapshot()["totals"]["occupied"] == 1
    assert store.snapshot("chad-2")["totals"]["occupied"] == 3
    assert store.snapshot("chad-3")["totals"]["unknown"] == 5
    with pytest.raises(ValueError):
        store.snapshot("chad-camera-2")


def test_partial_append_and_cache_invalidation(root):
    path = write(root, [pair()], tail='{"recordings":')
    store = ResultStore(root)
    assert store.snapshot()["totals"]["vacant"] == 1
    path.write_text(json.dumps({"recordings": [pair(states=("vacant",) * 3)]}) + "\n")
    assert store.snapshot()["totals"]["vacant"] == 3


@pytest.mark.parametrize("damage", ["duplicate", "wrong-frame", "wrong-camera", "invalid-state", "stale", "failure", "alignment"])
def test_latest_invalid_frame_is_unknown_not_previous_vacancy(root, damage):
    write(root, [pair(states=("vacant",) * 3)], run="20260926")
    latest = pair()
    if damage == "duplicate": latest["rows"].append(copy.deepcopy(latest["rows"][0]))
    if damage == "wrong-frame": latest["rows"][0]["frame_id"] = "different"
    if damage == "wrong-camera": latest["camera_id"] = "chad-camera-2"
    if damage == "invalid-state": latest["rows"][0]["final_state"] = "broken"
    if damage == "stale": latest["reference"]["stale"] = True
    if damage == "failure": latest["reference"]["error"] = "frame_failed"
    if damage == "alignment": latest["reference"]["alignment"]["ok"] = False
    write(root, [latest])
    data = ResultStore(root).snapshot()
    assert data["totals"]["unknown"] == 5
    assert data["totals"]["vacant"] == 0
    assert data["areas"][0]["issue"]


def test_missing_bay_is_unknown_and_legacy_policy_is_not_used(root):
    write(root, [pair(states=("vacant",))])
    data = ResultStore(root).snapshot()
    assert data["totals"]["vacant"] == 1 and data["totals"]["unknown"] == 4
    legacy = pair(states=("vacant",) * 3)
    legacy["final"]["decision_policy"] = "legacy"
    write(root, [legacy], run="20260928")
    assert ResultStore(root).snapshot()["totals"]["vacant"] == 1


def test_job_only_runs_one_worker(root, monkeypatch):
    job = AnalysisJob(root)
    waiting = threading.Event()
    done = threading.Event()
    def run(run_id):
        waiting.wait(2)
        job.update(status="complete")
        done.set()
    monkeypatch.setattr(job, "_run", run)
    try:
        assert job.start()
        assert not job.start()
        assert job.status()["status"] == "running"
    finally:
        waiting.set()
        assert done.wait(3)


def test_http_contract_and_local_analysis_action(root, monkeypatch):
    write(root, [pair()])
    web = root / "web"
    web.mkdir()
    (web / "index.html").write_text("parking home")
    server = make_server(0, root, web)
    monkeypatch.setattr(server.analysis_job, "start", lambda: True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/occupancy") as response:
            assert response.headers["Cache-Control"] == "no-store"
            assert json.load(response)["totals"]["vacant"] == 1
        assert urlopen(base).read() == b"parking home"
        for path, code in (("/api/occupancy?chad=bad", 400), ("/api/missing", 404), ("/../presets/chad-camera-1-expanded.json", 404)):
            with pytest.raises(HTTPError) as exc:
                urlopen(base + path)
            assert exc.value.code == code
        for headers in ({}, {"X-Parking-Client": "web", "Origin": "https://unrelated.example"}):
            with pytest.raises(HTTPError) as exc:
                urlopen(Request(base + "/api/analysis", method="POST", headers=headers))
            assert exc.value.code == 403
        assert urlopen(Request(base + "/api/analysis", method="POST", headers={"X-Parking-Client": "web"})).status == 202
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
