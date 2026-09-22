"""Reviewed view mappings and optional one-sided empty-appearance evidence.

Vacant-only labels never satisfy the original two-state calibration rule.
The supplemental vehicle branch may use them, together with object detection.
"""
import json

import numpy as np

from .catalog import CLIPS, PROJECT_ROOT
from .config import polygon_signature
from .evaluation import load_manifest
from .monitor import prepare_preset
from .sources import read_image
from .vision import Analyzer, preprocess, difference_score, pixel_hash, PREPROCESSING


def recipe_path(camera):
    return PROJECT_ROOT / "presets" / ("chad-camera-1-expanded.json" if camera == "Camera 1" else f"chad-camera-{camera[-1]}.json")


def view_recipe(view):
    return json.loads(recipe_path(view.camera).read_text(encoding="utf-8"))


def prepare_view(view, emit, stop, include_empty_evidence=True):
    from .areas import fetch_view, VIEWS
    clips = CLIPS if view.camera == "Camera 1" else [view.clip]
    config, recipe, paths = prepare_preset(emit, stop, recipe_path(view.camera), clips,
        lambda clip, progress, cancelled: fetch_view(VIEWS[clip.id], progress, cancelled),
        PROJECT_ROOT / "data/chad-mapped" / view.camera.replace(" ", "-"))
    if not include_empty_evidence:
        return config, recipe, paths
    prepare_empty_evidence(config)
    return config, recipe, paths


def prepare_empty_evidence(config):
    """Fit reviewed empty-only tolerances; never replace two-state calibration."""
    analyzer = Analyzer(config)
    banks, bank_hashes = {}, {}
    cached = {}

    def sample(path):
        if path not in cached:
            image = read_image(path)
            cached[path] = (preprocess(image), pixel_hash(image), analyzer.alignment(image)['ok'])
        return cached[path]

    for slot in config.data['slots']:
        key = slot['id']
        banks[key] = [analyzer.references[key]] if key in analyzer.references else []
        bank_hashes[key] = []
        for name in slot.get('vehicle_empty_reference_images', []):
            gray, digest, aligned = sample(config.resolve(name))
            if not aligned:
                continue
            banks[key].append(gray)
            bank_hashes[key].append(digest)
    groups, occupied, hashes = {}, {}, {}
    for row in load_manifest(config.path.parent / "calibration-labels.csv", config):
        key = row['slot_id']
        if not banks[key] or row['label'] not in ('vacant', 'occupied'):
            continue
        gray, digest, aligned = sample(row['path'])
        reference_hashes = set(bank_hashes[key]) | {analyzer.reference_hashes.get(key)}
        if not aligned or digest in reference_hashes or digest in hashes.setdefault(key, set()):
            continue
        hashes[key].add(digest)
        values = groups if row['label'] == 'vacant' else occupied
        values.setdefault(key, []).append(min(difference_score(gray,ref,analyzer.masks[key]) for ref in banks[key]))
    for slot in config.data['slots']:
        slot.pop('vehicle_empty_match', None)
        values = groups.get(slot['id'], [])
        if len(values) >= 5 and slot['id'] in analyzer.references:
            # Conservative experimental empty-match tolerance; not an occupied
            # boundary, probability, or replacement for two-state calibration.
            limit = min(.04, max(.012, float(np.percentile(values,95))*1.5 + .005))
            if occupied.get(slot['id']) and min(occupied[slot['id']]) <= limit:
                continue  # Reviewed occupied evidence conflicts with this tolerance.
            slot['vehicle_empty_match'] = {'max_difference': limit, 'vacant_examples': len(values),
                'basis': 'reviewed_vacant_only_heuristic_not_two_state_calibration',
                'preprocessing': PREPROCESSING,
                'sample_pixel_hashes': sorted(hashes[slot['id']]),
                'additional_reference_hashes': bank_hashes[slot['id']],
                'reference_pixel_hash': analyzer.reference_hashes[slot['id']], 'setup_pixel_hash': analyzer.setup_hash,
                'polygon_signature': polygon_signature(slot['polygon'])}
    config.save()
    return config
