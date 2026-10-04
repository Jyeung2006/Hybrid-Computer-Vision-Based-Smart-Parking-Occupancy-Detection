"""Four-policy development pilot on the saved, selected visual-review labels.

This is deliberately NOT an independent CHAD/Overhead accuracy estimate.
Unlike saved selective YOLO rows, YOLO-only is rerun over every labelled frame.
"""
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys
import time

from parking_probe.areas import OVERHEAD, VIEWS
from parking_probe.catalog import CLIPS, PROJECT_ROOT
from parking_probe.config import Config, atomic_json
from parking_probe.monitor import recording_for_recipe
from parking_probe.pklot import sha256
from parking_probe.policy_benchmark import score
from parking_probe.yolo import YOLODetector, associate

run = PROJECT_ROOT / 'runs/areas/20260928T013811_543214Z'
labels_path = PROJECT_ROOT / 'runs/verification/bay-boundary-audit/development-visual-labels.csv'
labels = list(csv.DictReader(labels_path.open(encoding='utf-8', newline='')))
wanted = defaultdict(list)
excluded = []
for label in labels:
    if label['recording'] not in {*(c.id for c in CLIPS), 'overhead-1'}:
        excluded.append(label)
    else:
        wanted[(label['recording'], float(label['seconds']))].append(label)

detector = YOLODetector()
observations, pedestrian_checks, frame_times = [], [], []
for site in ('chad', 'overhead'):
    site_dir = run / site
    config_path = Path(json.loads((site_dir / 'site.json').read_text())['reference_config'])
    slots = Config(config_path).data['slots']
    recipe = json.loads((PROJECT_ROOT / 'presets' /
        ('overhead-all-bays.json' if site == 'overhead' else 'chad-camera-1-expanded.json')).read_text())
    pairs = {}
    for line in (site_dir / 'history.jsonl').read_text(encoding='utf-8').splitlines():
        for pair in json.loads(line).get('recordings', []):
            key = (pair['recording_id'], float(pair['reference']['sample_time_seconds']))
            if key in wanted:
                pairs[key] = pair
    recordings = {}
    try:
        for key, pair in sorted(pairs.items()):
            source_id, seconds = key
            if source_id not in recordings:
                clip = OVERHEAD if source_id == 'overhead-1' else next(c for c in CLIPS if c.id == source_id)
                path = VIEWS['overhead-1'].path if source_id == 'overhead-1' else PROJECT_ROOT / 'data/chad' / clip.member
                recordings[source_id] = recording_for_recipe(path, recipe)
            reference = pair['reference']
            valid = (reference.get('analysis_status') == 'estimated'
                and reference.get('stale') is False and reference.get('error') is None
                and (reference.get('alignment') or {}).get('ok') is True)
            start = time.perf_counter()
            image = recordings[source_id].read(reference['video_frame_index']) if valid else None
            detections = detector.detect(image, 'aerial' if site == 'overhead' else 'coco') if valid else []
            elapsed = (time.perf_counter() - start) * 1000
            full = {r['slot_id']: r for r in associate(slots, detections,
                {s['id'] for s in slots}, .5 if site == 'overhead' else .82)}
            frame_times.append({'recording': source_id, 'seconds': seconds,
                'decode_and_full_yolo_ms': elapsed, 'detection_count': len(detections)})
            rows = {r['slot_id']: r for r in pair['rows']}
            for label in wanted[key]:
                bay = label['slot_id']
                if bay not in rows:
                    raise ValueError(f'Labelled bay not in saved view: {source_id} {bay}')
                existing = rows[bay]
                observations.append({'view': site.upper(), 'recording': source_id,
                    'condition': label['condition'], 'seconds': seconds, 'bay_id': bay,
                    'truth': label['visual_state'], 'reference_state': existing['reference_state'],
                    'mog2_state': existing['mog2_state'], 'vehicle_state': existing['vehicle_state'],
                    'full_yolo_state': full[bay]['state'], 'final_state': existing['final_state'],
                    'final_provisional': existing['final_provisional'], 'valid_frame': valid,
                    'yolo_requested': existing['yolo_requested'],
                    'reference_ms': existing['reference_ms'], 'mog2_ms': existing['mog2_ms'],
                    'vehicle_ms': existing['vehicle_ms'], 'yolo_ms': existing['yolo_ms'],
                    'full_yolo_ms': elapsed})
                if source_id == 'chad-4' and bay == 'B08':
                    pedestrian_checks.append({'seconds': seconds, 'truth': label['visual_state'],
                        'hybrid': existing['final_state'], 'mobile': existing['vehicle_state'],
                        'full_yolo': full[bay]['state'], 'vehicle_detections': detections})
    finally:
        for recording in recordings.values():
            recording.close()

if len(observations) != len(labels) - len(excluded):
    raise ValueError('A selected visual label did not join exactly once')
report = {'status': 'development_pilot_not_independent_accuracy',
    'source_run': str(run), 'labels': str(labels_path), 'labels_sha256': sha256(labels_path),
    'model_manifest_sha256': sha256(PROJECT_ROOT / 'assets/models/yolov8s-manifest.json'),
    'excluded_other_camera_labels': len(excluded), 'observations': observations,
    'frame_timings': frame_times, 'pedestrian_checks': pedestrian_checks,
    'metrics': score(observations)}
output = PROJECT_ROOT / 'runs/evaluation/development-policy-pilot.json'
output.parent.mkdir(parents=True, exist_ok=True)
atomic_json(output, report)
print(json.dumps({'output': str(output), 'observations': len(observations),
    'excluded': len(excluded), 'pedestrian_checks': pedestrian_checks,
    'metric_groups': list(report['metrics'])}, indent=2))
