"""Real-image regression: B08 passing person and CC BY-SA parked motorcycles."""
import json
from pathlib import Path

import cv2

from parking_probe.catalog import PROJECT_ROOT
from parking_probe.monitor import recording_for_recipe
from parking_probe.pklot import sha256
from parking_probe.vehicle import VehicleDetector
from parking_probe.yolo import YOLODetector, OCCUPIED_THRESHOLD

motorcycle_path = PROJECT_ROOT / 'tests/fixtures/parked_motorcycles_sheffield.jpg'
assert sha256(motorcycle_path) == '1dbd270cf7fd4eb1ba493460f21a277c9d30f474e912f38c2fa08bf3ec5b4875'
image = cv2.imread(str(motorcycle_path))
assert image is not None
mobile = VehicleDetector()
yolo = YOLODetector()
motor_mobile = mobile.detect(image)
motor_yolo = yolo.detect(image, 'coco')
assert any(d['class'] == 'motorbike' and d['detector_score'] >= .65 for d in motor_mobile)
assert any(d['class'] == 'motorcycle' for d in motor_yolo)

recipe = json.loads((PROJECT_ROOT / 'presets/chad-camera-1-expanded.json').read_text())
recording = recording_for_recipe(PROJECT_ROOT / 'data/chad/1_054_0.mp4', recipe)
try:
    person = recording.read(round(15 * recording.fps))
finally:
    recording.close()
person_mobile = mobile.detect(person)
person_yolo = yolo.detect(person, 'coco')
assert not any(d['class'] == 'motorbike' for d in person_mobile)
assert not any(d['class'] == 'motorcycle' for d in person_yolo)
report = {'motorcycle_image': str(motorcycle_path), 'motorcycle_sha256': sha256(motorcycle_path),
    'motorcycle_source': 'https://commons.wikimedia.org/wiki/File:Motorcycle_parking_on_a_pedestrianised_street_in_Sheffield.jpg',
    'motorcycle_mobilenet_scores': [d['detector_score'] for d in motor_mobile if d['class'] == 'motorbike'],
    'motorcycle_yolo_scores': [d['detector_score'] for d in motor_yolo if d['class'] == 'motorcycle'],
    'yolo_occupied_threshold': OCCUPIED_THRESHOLD,
    'pedestrian_sample': 'chad-4 frame 15 seconds, B08 visual obstruction',
    'pedestrian_mobile_motorbike_detections': 0,
    'pedestrian_yolo_motorcycle_detections': 0,
    'limitation': 'One motorcycle photo and one pedestrian frame; no statistical recall or precision claim.'}
out = PROJECT_ROOT / 'runs/evaluation/pedestrian-motorcycle-regression.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
