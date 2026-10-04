import numpy as np

from parking_probe.opencv_first import before_yolo
from parking_probe.vehicle import VehicleDetector, classify_bays


class FakeNet:
    def __init__(self, label): self.label = label
    def setInput(self, blob): pass
    def forward(self):
        return np.array([[[[0, self.label, .95, .1, .1, .4, .7]]]], dtype=np.float32)


def test_person_class_is_ignored_and_motorbike_is_vehicle():
    detector = VehicleDetector.__new__(VehicleDetector)
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    detector.net = FakeNet(15)  # MobileNet SSD VOC person.
    assert detector.detect(image) == []
    detector.net = FakeNet(14)  # VOC motorbike.
    assert detector.detect(image)[0]['class'] == 'motorbike'


def test_motorcycle_inside_bay_occupied_but_opencv_still_wins():
    slot = {'id': 'B08', 'polygon': [[10, 10], [90, 10], [90, 90], [10, 90]]}
    detected = [{'class': 'motorbike', 'box': [20, 20, 70, 75], 'detector_score': .9}]
    result = classify_bays([slot], detected, {}, {})[0]
    assert result['state'] == 'occupied'
    assert before_yolo('vacant', 'unknown', 'uncertain') == (
        'vacant', 'reference_definite_mog2_unresolved', 'reference', False)
