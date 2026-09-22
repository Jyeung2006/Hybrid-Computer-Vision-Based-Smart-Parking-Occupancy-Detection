from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

from .config import ConfigError, polygon_signature
from .sources import Frame, read_image, utcnow
from .vision import Analyzer, PREPROCESSING, pixel_hash, thresholds


class ClassificationMetrics:
    """Streaming binary truth/four-state decisions; occupied is positive.

    Accuracy/P/R/F1 condition on a definite decision. Coverage and the full
    2x4 matrix expose abstentions. Unconditional error/success rates use all
    labelled truth, so a selective verifier cannot hide its missing decisions.
    """
    def __init__(self):
        self.matrix = {truth: {state: 0 for state in ('occupied', 'vacant', 'uncertain', 'unknown')}
                       for truth in ('occupied', 'vacant')}
        self.ambiguous = 0

    def add(self, truth, predicted):
        if predicted not in self.matrix['occupied']:
            raise ConfigError('Invalid predicted occupancy state.')
        if truth == 'ambiguous':
            self.ambiguous += 1
        elif truth in self.matrix:
            self.matrix[truth][predicted] += 1
        else:
            raise ConfigError('Invalid ground-truth occupancy state.')

    def result(self):
        m = self.matrix
        tp, fn = m['occupied']['occupied'], m['occupied']['vacant']
        fp, tn = m['vacant']['occupied'], m['vacant']['vacant']
        counts = {truth: sum(row.values()) for truth, row in m.items()}
        total, classified = sum(counts.values()), tp + tn + fp + fn
        def pct(numerator, denominator):
            return 100 * numerator / denominator if denominator else None
        return {'binary_observations': total, 'classified_observations': classified,
            'unresolved_observations': total-classified, 'ambiguous_ground_truth_excluded': self.ambiguous,
            'ground_truth_counts': counts,
            'confusion': {'true_occupied': tp, 'true_vacant': tn, 'false_vacant': fn, 'false_occupied': fp},
            'confusion_matrix': {truth: dict(row) for truth, row in m.items()},
            'positive_class': 'occupied', 'accuracy_on_classified_pct': pct(tp+tn, classified),
            'precision_on_classified_pct': pct(tp, tp+fp), 'recall_on_classified_pct': pct(tp, tp+fn),
            'f1_on_classified_pct': pct(2*tp, 2*tp+fp+fn), 'decision_coverage_pct': pct(classified, total),
            'correct_decisions_all_truth_pct': pct(tp+tn, total),
            'occupied_recall_all_truth_pct': pct(tp, counts['occupied']),
            'false_vacant_rate_on_classified_occupied_pct': pct(fn, tp+fn),
            'false_occupied_rate_on_classified_vacant_pct': pct(fp, tn+fp),
            'false_vacant_rate_all_occupied_pct': pct(fn, counts['occupied']),
            'false_occupied_rate_all_vacant_pct': pct(fp, counts['vacant'])}


def reference_boundaries(analyzer, slot, vacant, occupied, hashes, sessions):
    """Shared threshold fitting/metadata for CSV and chronological adapters."""
    decision = thresholds(vacant, occupied)
    decision.update({'vacant_count': len(vacant), 'occupied_count': len(occupied),
        'reference_pixel_hash': analyzer.reference_hashes.get(slot['id']),
        'setup_pixel_hash': analyzer.setup_hash, 'polygon_signature': polygon_signature(slot['polygon']),
        'preprocessing': PREPROCESSING, 'sample_pixel_hashes': sorted(hashes),
        'session_ids': sorted(sessions), 'created_at': utcnow().isoformat()})
    return decision


def load_manifest(path: Path, config):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"frame_path", "slot_id", "label", "session_id"}.issubset(reader.fieldnames or []):
            raise ConfigError("Labels CSV needs frame_path, slot_id, label, session_id columns.")
        rows = list(reader)
    if not rows:
        raise ConfigError("Labels CSV has no observations.")
    seen = set()
    for row in rows:
        config.slot(row["slot_id"])
        if row["label"] not in ("occupied", "vacant", "ambiguous") or not row["session_id"].strip():
            raise ConfigError("Labels must be occupied, vacant or ambiguous, with a session ID.")
        row["path"] = (path.parent / row["frame_path"]).resolve()
        key = row["path"], row["slot_id"]
        if key in seen:
            raise ConfigError("A frame/slot pair is duplicated in the labels CSV.")
        seen.add(key)
    return rows


def calibrate(config, manifest_path):
    analyzer = Analyzer(config)
    rows = load_manifest(manifest_path, config)
    groups = defaultdict(lambda: {"vacant": [], "occupied": [], "hashes": set(), "sessions": set()})
    cache = {}
    all_reference_hashes = set(analyzer.reference_hashes.values())
    for row in rows:
        if row["label"] == "ambiguous":
            continue
        path = row["path"]
        if path not in cache:
            image = read_image(path)
            alignment = analyzer.alignment(image)
            if not alignment["ok"]:
                raise ConfigError("A calibration frame fails setup-view alignment: " + alignment["reason"])
            cache[path] = (image, pixel_hash(image))
        image, digest = cache[path]
        if digest in all_reference_hashes:
            raise ConfigError("Reference images must not be reused as calibration samples.")
        group = groups[row["slot_id"]]
        if digest in group["hashes"]:
            raise ConfigError("Duplicate image content for a slot cannot count as independent samples.")
        group["hashes"].add(digest)
        group["sessions"].add(row["session_id"])
        group[row["label"]].append(analyzer.slot_score(row["slot_id"], image))
    report = {}
    for slot in config.data["slots"]:
        group = groups[slot["id"]]
        decision = reference_boundaries(analyzer, slot, group['vacant'], group['occupied'], group['hashes'], group['sessions'])
        slot["calibration"] = decision
        report[slot["id"]] = decision
    config.save()
    return report


def evaluate(config, manifest_path):
    analyzer = Analyzer(config)
    rows = load_manifest(manifest_path, config)
    forbidden_hashes = set(analyzer.reference_hashes.values())
    forbidden_sessions = set()
    for slot in config.data["slots"]:
        calibration = slot.get("calibration") or {}
        forbidden_hashes.update(calibration.get("sample_pixel_hashes", []))
        forbidden_sessions.update(calibration.get("session_ids", []))
    if any(row["session_id"] in forbidden_sessions for row in rows):
        raise ConfigError("Evaluation sessions must be separate from calibration sessions.")
    groups = defaultdict(list)
    for row in rows:
        groups[row["path"]].append(row)
    samples = []
    durations = []
    seen_hashes = set()
    metrics = ClassificationMetrics()
    for path, labels in groups.items():
        image = read_image(path)
        digest = pixel_hash(image)
        if digest in forbidden_hashes:
            raise ConfigError("Evaluation image duplicates reference or calibration data.")
        if digest in seen_hashes:
            raise ConfigError("Duplicate evaluation image content is not a separate test frame.")
        seen_hashes.add(digest)
        # Offline scoring tests the detector. It does not manufacture camera
        # capture timestamps or establish the freshness of a live source.
        result = analyzer.analyze(Frame(image, utcnow()))
        durations.append(result["processing_duration_ms"])
        predicted = {s["slot_id"]: s for s in result["slots"]}
        for row in labels:
            truth = row["label"]
            state = predicted[row["slot_id"]]["state"]
            samples.append({"frame_name": path.name, "session_id": row["session_id"], "slot_id": row["slot_id"],
                            "truth": truth, "predicted": state, "difference_score": predicted[row["slot_id"]]["difference_score"]})
            metrics.add(truth, state)
    measured = metrics.result()
    sessions = sorted({r["session_id"] for r in rows})
    return {"evaluation_type": "labelled_images_detector_only", "live_camera_validation": "not_performed_by_this_command",
            "unique_frames": len(seen_hashes), "session_ids": sessions,
            "minimum_evaluation_requirements_met": len(seen_hashes) >= 30 and len(sessions) >= 2 and all(measured['ground_truth_counts'].values()),
            **measured,
            "processing_latency_ms": {"median": float(np.median(durations)), "p95": float(np.percentile(durations, 95)), "maximum": float(max(durations))},
            "observations": samples}
