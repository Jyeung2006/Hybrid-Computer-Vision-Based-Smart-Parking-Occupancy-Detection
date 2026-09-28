"""Explicit sites, camera views, recordings and physical bay inventories.

Camera overlap never creates extra spaces. Unverified identities stay view-local.
The overhead inventory covers all 69 painted bays visible in the source video.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time

import requests

from .catalog import CLIPS, Clip, PROJECT_ROOT, DownloadError, fetch_clip

SITES = {"chad": "CHAD car park", "overhead": "Overhead demo car park"}
OVERHEAD = Clip("overhead-1", "carPark.mp4", 10607736, 0, 0, 0,
                "f2d804e9b2e8ff7e0ae9776068a9cbc8126b6bce2e09ef6f56d3ad9c8fe84069")
OVERHEAD_URL = "https://raw.githubusercontent.com/harshbafnaa/car-parking-detection/a35ce5055beb2d50eac971254720892944e0f7fb/carPark.mp4"
OVERHEAD_MAP = {"W01": "OVER-W01", "E01": "OVER-E01"}
EXTRA_VIEWS = (
    Clip("chad-camera-2", "2_036_0.mp4", 38367668, 38370136, 37193418952, 1708257018,
         "3f2368e5b34636644c85288a5776597ef5e92a56876f0e3635ba4e085c3636d9"),
    Clip("chad-camera-3", "3_073_0.mp4", 24027785, 24025474, 69136536030, 174652777,
         "789db97f547aec64b1682970a8ecf888d2c8eeaf24528fb8cffa44a9bf9ffb46"),
    Clip("chad-camera-4", "4_075_0.mp4", 5251955, 5244727, 86485498243, 260132983,
         "02104edf050e130da6496604162fd25a80a704ab7b6a36b30f5b0c8cd9e24e07"),
)


@dataclass(frozen=True)
class RecordingView:
    clip: Clip
    site: str
    camera: str
    resolution: tuple
    directory: str
    analyzed: bool = False

    @property
    def path(self):
        return PROJECT_ROOT / "data" / self.directory / self.clip.member

    @property
    def label(self):
        return self.clip.member


VIEWS = {c.id: RecordingView(c, "chad", "Camera 1", (1920, 1080), "chad", True) for c in CLIPS}
VIEWS.update({c.id: RecordingView(c, "chad", f"Camera {c.member[0]}",
             (1280, 720) if c.member[0] == "4" else (1920, 1080), "chad-views", True) for c in EXTRA_VIEWS})
VIEWS[OVERHEAD.id] = RecordingView(OVERHEAD, "overhead", "Overhead camera", (1100, 720), "other-parking", True)


def fetch_overhead(clip=OVERHEAD, progress=lambda m: None, cancelled=lambda: False):
    path = VIEWS[OVERHEAD.id].path
    if path.exists() and path.stat().st_size == clip.size and hashlib.sha256(path.read_bytes()).hexdigest() == clip.sha256:
        progress("Using cached overhead parking video.")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    try:
        start = time.monotonic()
        with requests.get(OVERHEAD_URL, stream=True, timeout=(5, 20)) as response:
            response.raise_for_status()
            total = 0
            digest = hashlib.sha256()
            with partial.open("wb") as handle:
                for chunk in response.iter_content(256*1024):
                    if cancelled() or time.monotonic()-start > 90:
                        raise DownloadError("Overhead video download stopped or timed out.")
                    total += len(chunk)
                    if total > clip.size:
                        raise DownloadError("Overhead video exceeds its pinned size.")
                    digest.update(chunk)
                    handle.write(chunk)
            if total != clip.size or digest.hexdigest() != clip.sha256:
                raise DownloadError("Overhead video checksum failed.")
        partial.replace(path)
        return path
    except requests.RequestException:
        raise DownloadError("Cannot download the overhead recording. Check the connection and retry.") from None
    finally:
        partial.unlink(missing_ok=True)


def fetch_view(view, progress=lambda m: None, cancelled=lambda: False):
    return (fetch_overhead(view.clip, progress, cancelled) if view.site == "overhead" else
            fetch_clip(view.clip, progress, cancelled, view.path.parent))


def inventory(view):
    if not view.analyzed:
        return []  # Camera correspondence has not been verified for other views.
    if view.site == "overhead":
        return json.loads((PROJECT_ROOT / "presets/overhead-all-bays.json").read_text())['slots']
    from .view_presets import view_recipe
    return view_recipe(view)['slots']


AREA_LABELS = {"chad-far": "CHAD / Far row", "chad-near": "CHAD / Near row",
               "chad-c2-row": "CHAD / Camera 2 row", "chad-c3-row": "CHAD / Camera 3 row",
               "overhead-west": "Overhead / West bays", "overhead-middle": "Overhead / Middle bays", "overhead-east": "Overhead / East bays"}


def area_reports(review, selections, display_overrides=None):
    from .interface_model import chart_data
    reports = []
    for site, default in (("chad", "chad-1"), ("overhead", "overhead-1")):
        clip_id, position = selections.get(site, (default, 0.0))
        view = VIEWS[clip_id]
        if view.site != site or not view.analyzed:
            raise ValueError("Area reports require a mapped recording from the correct site.")
        pair = ((display_overrides or {}).get(clip_id) or review.at(clip_id, position))
        bays = inventory(view)
        for area, label in AREA_LABELS.items():
            ids = [b["bay_id"] for b in bays if b["area"] == area]
            if not ids:
                continue
            rows, summary = chart_data(pair, ids)
            reports.append({"area_id": area, "area_name": label, "site_id": site,
                "recording_id": clip_id, "playback_seconds": position,
                "sample_seconds": pair["reference"]["sample_time_seconds"] if pair else None,
                "identity_scope": "view_local_unverified_correspondence" if any(b.get('mapping_status') == 'view_local_correspondence_unverified' for b in bays if b['area'] == area) else "mapped_physical_bays",
                "capacity_scope": "mapped_visible_subset" if site == "chad" else "all_69_visible_marked_bays",
                "available": summary["occupancy_min_pct"] is not None,
                "provisional_vacant": sum(r['state'] == 'vacant' and bool(r.get('final_provisional')) for r in rows),
                "provisional_occupied": sum(r['state'] == 'occupied' and bool(r.get('final_provisional')) for r in rows),
                **summary})
    return reports
