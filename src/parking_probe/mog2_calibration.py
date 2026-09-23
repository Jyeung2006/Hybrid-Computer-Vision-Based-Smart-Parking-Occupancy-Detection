"""Fit foreground-ratio bounds from a camera's reviewed calibration labels.

Each clip starts a fresh seeded model. State updates use the same three-second
schedule as replay. Extra labelled times are read-only model probes (rate=0),
so adding a calibration observation cannot teach an occupied vehicle away.
"""
from collections import defaultdict
import hashlib
import json

from .config import ConfigError, atomic_json
from .display_model import sample_indices
from .evaluation import load_manifest
from .mog2 import MOG2Branch, PARAMETERS
from .monitor import recording_for_recipe
from .sources import Frame, read_image, utcnow
from .vision import Analyzer, pixel_hash, thresholds


def prepare_mog2(config, recipe, paths, interval, emit, stop):
    analyzer = Analyzer(config)
    branch = MOG2Branch(analyzer, interval=interval)
    model_signature = branch.signature
    manifest = config.path.parent / "calibration-labels.csv"
    rows = load_manifest(manifest, config)
    # Only explicitly reviewed samples are labels. No predicted states are labels.
    grouped = defaultdict(lambda: defaultdict(list))
    sample_hashes = {}
    seen = defaultdict(set)
    forbidden = set(analyzer.reference_hashes.values())
    for row in rows:
        if row["label"] == "ambiguous":
            continue
        digest = pixel_hash(read_image(row["path"]))
        if digest in forbidden or digest in seen[row["slot_id"]]:
            raise ConfigError("MOG2 calibration cannot reuse reference or duplicate bay images.")
        seen[row["slot_id"]].add(digest)
        sample_hashes[str(row["path"])] = digest
        clip_id = row["session_id"]
        if clip_id not in paths:
            raise ConfigError("MOG2 calibration requires the labelled source recordings.")
        index = int(row["path"].stem.rsplit("-", 1)[1])
        grouped[clip_id][index].append(row)
    digest = hashlib.sha256((manifest.read_text() + model_signature + json.dumps(sample_hashes, sort_keys=True)).encode()).hexdigest()[:16]
    output = config.path.parent / f"mog2-calibration-{digest}.json"
    if output.exists():
        report = json.loads(output.read_text())
        if report.get("model_signature") == model_signature:
            emit("status", "Using cached MOG2 foreground calibration.")
            return report
    emit("status", "Fitting MOG2 boundaries from the selected camera's reviewed calibration examples...")
    scores = defaultdict(lambda: {"vacant": [], "occupied": []})
    records = []
    for clip_id, labelled in sorted(grouped.items()):
        branch = MOG2Branch(analyzer, interval=interval)
        recording = recording_for_recipe(paths[clip_id], recipe)
        try:
            updates = {index for _, index in sample_indices(recording.count, recording.fps, interval)}
            for index in sorted(updates | set(labelled)):
                if stop.is_set():
                    raise InterruptedError("Stopped during MOG2 calibration.")
                image = recording.read(index)
                frame = Frame(image, utcnow(), frame_id=f"{clip_id}-{index:06d}")
                checked = analyzer.analyze(frame)
                if checked["analysis_status"] != "estimated" and index in labelled:
                    raise ConfigError("MOG2 calibration frame failed alignment/validation.")
                # Unlabelled chronological updates follow the runtime guard:
                # invalid frames return failure and do not teach the model.
                result = branch.analyze(frame, index / recording.fps, checked, update=index in updates)
                by_slot = {s["slot_id"]: s for s in result["slots"]}
                for row in labelled.get(index, []):
                    if pixel_hash(image) != sample_hashes[str(row["path"])]:
                        raise ConfigError("Labelled MOG2 frame does not match its decoded source.")
                    score = by_slot[row["slot_id"]]["foreground_ratio"]
                    if score is None:
                        raise ConfigError("A usable empty reference is required for MOG2 calibration.")
                    scores[row["slot_id"]][row["label"]].append(score)
                    records.append({"clip_id": clip_id, "frame_index": index, "position_seconds": index / recording.fps,
                                    "slot_id": row["slot_id"], "label": row["label"], "foreground_ratio": score})
        finally:
            recording.close()
    boundaries = {}
    for slot in config.data["slots"]:
        group = scores[slot["id"]]
        boundaries[slot["id"]] = {**thresholds(group["vacant"], group["occupied"]),
            "vacant_count": len(group["vacant"]), "occupied_count": len(group["occupied"])}
    report = {"model_signature": model_signature, "parameters": PARAMETERS, "sample_interval_seconds": interval,
              "source_sessions": sorted(grouped), "slots": boundaries, "samples": records,
              "sample_pixel_hashes": sample_hashes, "created_at": utcnow().isoformat(),
              "evaluation_status": "demonstration_calibration_not_independent_accuracy",
              "model_update_schedule": "same source frames as runtime; extra labels use learningRate=0"}
    atomic_json(output, report)
    emit("status", "MOG2 calibration saved: " + str(output))
    return report
