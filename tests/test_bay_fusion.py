from copy import deepcopy

import pytest

from parking_probe.bay_fusion import TimeWindow, format_window, fuse_views
from parking_probe.config import ConfigError
from parking_probe.site_replay import validate_site


CAMERAS = [{"camera_id": "a", "slot_map": {"A1": "P001"}},
           {"camera_id": "b", "slot_map": {"B8": "P001"}}]


def view(slot, state, when=0, **changes):
    return {"analysis_status": "estimated", "stale": False, "sample_time_seconds": when,
            "frame_time_seconds": when, "slots": [{"slot_id": slot, "state": state,
                "difference_score": .9 if state == "occupied" else .1}], **changes}


@pytest.mark.parametrize("a,b,expected,reason", [
    ("occupied", "occupied", "occupied", "views_agree"),
    ("vacant", "vacant", "vacant", "views_agree"),
    ("occupied", "vacant", "uncertain", "views_disagree"),
    ("occupied", "uncertain", "uncertain", "view_uncertain"),
    ("uncertain", "vacant", "uncertain", "view_uncertain"),
    ("unknown", "vacant", "vacant", "single_view"),
    ("unknown", "unknown", "unknown", "no_usable_view"),
])
def test_two_views_are_one_bay(a, b, expected, reason):
    result = fuse_views(["P001"], CAMERAS, {"a": view("A1", a), "b": view("B8", b)}, 0)
    assert result["summary"]["total_monitored_bays"] == 1
    bay = result["bays"][0]
    assert (bay["state"], bay["reason"]) == (expected, reason)
    assert bay["degraded"] == ("unknown" in (a, b))
    if expected == "uncertain":
        assert result["summary"]["occupancy_pct"] is None
        assert result["summary"]["occupancy_min_pct"] == 0
        assert result["summary"]["occupancy_max_pct"] == 100


def test_stale_view_cannot_outvote_current_view_and_all_stale_is_unavailable():
    observations = {"a": view("A1", "occupied", when=0), "b": view("B8", "vacant", when=6)}
    result = fuse_views(["P001"], CAMERAS, observations, 6)
    assert result["bays"][0]["state"] == "vacant"
    assert result["bays"][0]["degraded"]
    assert fuse_views(["P001"], CAMERAS, observations, 12)["summary"]["occupancy_min_pct"] is None


@pytest.mark.parametrize("frame_time", [None, 1])
def test_unsynchronized_views_are_not_merged_into_a_definite_state(frame_time):
    result = fuse_views(["P001"], CAMERAS,
        {"a": view("A1", "occupied"), "b": view("B8", "occupied", frame_time_seconds=frame_time)}, 0)
    assert result["bays"][0]["reason"] == "views_not_synchronized"
    assert result["bays"][0]["state"] == "uncertain"


def test_failed_retrieval_and_future_observation_are_unknown():
    for changes in ({"stale": True}, {"analysis_status": "unavailable"}, {"sample_time_seconds": 1}):
        fused = fuse_views(["P001"], CAMERAS[:1], {"a": view("A1", "occupied", **changes)}, 0)
        assert fused["bays"][0]["state"] == "unknown"


def test_rates_use_time_after_fusion_and_do_not_majority_vote_latest_state():
    def fused(time, a, b):
        return fuse_views(["P001"], CAMERAS, {"a": view("A1", a, time), "b": view("B8", b, time)}, time)
    window = TimeWindow(fused(0, "unknown", "unknown"))
    window.update(0, fused(0, "occupied", "occupied"))
    window.update(3, fused(3, "occupied", "occupied"))
    window.update(6, fused(6, "vacant", "occupied"))
    window.update(9, fused(9, "vacant", "vacant"))
    report = window.close(10)
    bay = report["bays"][0]
    assert bay["state"] == "vacant"  # latest state, even though most of the window was occupied
    assert bay["state_seconds"] == {"occupied": 6, "vacant": 1, "uncertain": 3, "unknown": 0}
    assert bay["occupied_time_min_pct"] == 60
    assert bay["occupied_time_max_pct"] == 90
    assert bay["occupied_time_pct"] is None
    assert bay["classified_time_pct"] == 70
    assert report["sample_count"] == 4 and report["summary"]["vacant"] == 1
    assert "60.0-90.0%" in format_window(report)
    partial = window.close(12, partial=True)
    assert partial["partial_window"] and partial["window_duration_seconds"] == 2
    assert partial["bays"][0]["occupied_time_pct"] == 0
    assert window.close(12) is None
    with pytest.raises(ValueError, match="monotonic"):
        window.advance(11)


def test_window_boundary_sample_belongs_to_next_window():
    def fused(when, state):
        return fuse_views(["P001"], CAMERAS[:1], {"a": view("A1", state, when)}, when)
    window = TimeWindow(fused(0, "unknown"))
    window.update(0, fused(0, "occupied"))
    assert window.close(10)["bays"][0]["occupied_time_pct"] == 100
    window.update(10, fused(10, "vacant"))
    assert window.close(20)["bays"][0]["occupied_time_pct"] == 0


def site():
    return {"version": 1, "site_id": "test", "bay_ids": ["P001"], "mapping_verified": True,
            "synchronization": {"verified": True, "note": "Synthetic synchronized fixture"},
            "cameras": [{**c, "source_resolution": [640, 480], "analysis_resolution": [640, 480]}
                        for c in deepcopy(CAMERAS)]}


@pytest.mark.parametrize("fault", ["duplicate_camera", "duplicate_bay", "duplicate_polygon", "unmapped_bay",
                                  "foreign_bay", "unverified_sync", "unverified_mapping", "negative_offset"])
def test_unsafe_or_ambiguous_registry_is_rejected(fault):
    data = site()
    if fault == "duplicate_camera":
        data["cameras"][1]["camera_id"] = "a"
    elif fault == "duplicate_bay":
        data["bay_ids"].append("P001")
    elif fault == "duplicate_polygon":
        data["cameras"][0]["slot_map"]["A2"] = "P001"
    elif fault == "unmapped_bay":
        data["bay_ids"].append("P002")
    elif fault == "foreign_bay":
        data["cameras"][1]["slot_map"]["B8"] = "P999"
    elif fault == "unverified_sync":
        data["synchronization"]["verified"] = False
    elif fault == "unverified_mapping":
        data["mapping_verified"] = False
    else:
        data["cameras"][0]["video_offset_seconds"] = -1
    with pytest.raises(ConfigError):
        validate_site(data)
