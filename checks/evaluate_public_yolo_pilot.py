"""Predeclared small external-site YOLO-only transfer pilot.

Three fixed test images per held-out day (first, middle, last), one fixed bay
geometry from fitting days, no threshold tuning and no CHAD accuracy claim.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import time

import cv2

from parking_probe.catalog import PROJECT_ROOT
from parking_probe.config import atomic_json
from parking_probe.pklot import sha256
from parking_probe.pklot_additional import annotation
from parking_probe.yolo import YOLODetector, associate

cache = PROJECT_ROOT / 'data/pklot'
summary_path = cache / 'additional-summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
protocol = {'version': 1, 'views': ['UFPR05', 'PUCPR'], 'partition': 'test_only',
    'sampling': 'all_test_days_first_middle_last_xml_in_sorted_path_order',
    'geometry': 'first_full_annotation_on_earliest_fit_day_fixed_for_each_view',
    'yolo_profile': 'aerial', 'confidence': .80, 'bay_overlap': .25,
    'no_detection': 'uncertain_not_vacant', 'policy_selection_after_test': False}
out = PROJECT_ROOT / 'runs/evaluation/public-yolo-pilot'
out.mkdir(parents=True, exist_ok=True)
atomic_json(out / 'protocol.json', protocol)
detector = YOLODetector()
result = {'status': 'external_exploratory_pilot_not_chad_accuracy',
    'dataset': summary['source'], 'archive_sha256': summary['archive_sha256'],
    'protocol': protocol, 'views': {}}
for view in protocol['views']:
    base = cache / view
    fit_days = set(summary['views'][view]['partitions']['fit']['days'])
    test_days = sorted(summary['views'][view]['partitions']['test']['days'])
    fit_candidates = [p for p in sorted(base.glob('*/*/*.xml')) if p.parent.name in fit_days]
    if not fit_candidates:
        raise ValueError('Missing fitting-day geometry')
    best = max(fit_candidates[:30], key=lambda p: len(annotation(p, view)[0]))
    slots, _ = annotation(best, view)
    fixed = {s['id']: s['polygon'] for s in slots}
    rows, times = [], []
    for day in test_days:
        images = [p for p in sorted(base.glob(f'*/{day}/*.xml')) if p.with_suffix('.jpg').exists()]
        if len(images) < 3:
            raise ValueError('Too few labelled test frames in held-out day')
        selected = [images[0], images[len(images)//2], images[-1]]
        for xml in selected:
            image_path = xml.with_suffix('.jpg')
            image = cv2.imread(str(image_path))
            if image is None or image.shape[:2] != (720, 1280):
                raise ValueError('Original full frame unavailable or wrong size')
            current, labels = annotation(xml, view)
            start = time.perf_counter()
            detections = detector.detect(image, 'aerial')
            by_slot = {r['slot_id']: r for r in associate(slots, detections, set(fixed), .5)}
            elapsed = (time.perf_counter()-start)*1000
            times.append(elapsed)
            for bay, truth in labels.items():
                if bay not in by_slot:
                    continue
                rows.append({'day': day, 'weather': xml.parts[-3], 'bay_id': bay,
                    'frame_id': xml.stem, 'truth': truth, 'predicted': by_slot[bay]['state'],
                    'reason': by_slot[bay]['reason']})
            result.setdefault('frames', []).append({'view': view, 'day': day,
                'xml': xml.relative_to(cache).as_posix(), 'xml_sha256': sha256(xml),
                'image_sha256': sha256(image_path), 'detections': len(detections),
                'bay_geometry_differences': sum(fixed.get(s['id']) != s['polygon'] for s in current),
                'inference_and_association_ms': elapsed})
    by_weather = defaultdict(list)
    for row in rows:
        by_weather[row['weather']].append(row)
    def metrics(group):
        counts = Counter((r['truth'], r['predicted']) for r in group)
        occupied = sum(r['truth'] == 'occupied' for r in group)
        vacant = sum(r['truth'] == 'vacant' for r in group)
        definite = sum(r['predicted'] in ('occupied', 'vacant') for r in group)
        return {'observations': len(group), 'truth_occupied': occupied, 'truth_vacant': vacant,
            'true_occupied_pred_occupied': counts['occupied', 'occupied'],
            'true_occupied_pred_vacant': counts['occupied', 'vacant'],
            'true_vacant_pred_occupied': counts['vacant', 'occupied'],
            'true_vacant_pred_vacant': counts['vacant', 'vacant'],
            'abstentions': len(group)-definite, 'definite_coverage': definite/len(group) if group else None,
            'false_vacant_over_true_occupied': counts['occupied', 'vacant']/occupied if occupied else None,
            'false_occupied_over_true_vacant': counts['vacant', 'occupied']/vacant if vacant else None}
    result['views'][view] = {'test_days': test_days,
        'fixed_geometry_source': best.relative_to(cache).as_posix(),
        'fixed_geometry_sha256': sha256(best), 'mapped_bays': len(slots),
        'frames': len(times), 'yolo_calls': len(times),
        'inference_ms_median': statistics.median(times),
        'inference_ms_p95': sorted(times)[min(len(times)-1, int(.95*len(times)))],
        'metrics': metrics(rows), 'by_weather': {w: metrics(r) for w,r in by_weather.items()}}
atomic_json(out / 'results.json', result)
print(json.dumps({'output': str(out / 'results.json'), 'views': result['views']}, indent=2))
