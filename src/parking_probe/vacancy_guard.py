"""Three clean recorded observations before an unresolved bay can be called vacant.

The usual Reference/MOG2 agreement and YOLO occupied routes remain immediate.
No detector silence is treated as a model-confirmed empty-space prediction.
"""
from __future__ import annotations

import math

import numpy as np

from .empty_evidence import EmptyEvidence
from .yolo import DECISION_POLICY

GUARDED_DECISION_POLICY = DECISION_POLICY + '_guarded_three_observations_v1'
STREAK_SAMPLES = 3
STREAK_INTERVAL_SECONDS = 3.0
VISIBILITY_MAPPING = {'shared_physical_id', 'reviewed_full_visible_inventory',
                      'view_local_correspondence_unverified'}


def near_vehicle_box(polygon, detections):
    """Any detected vehicle box touching a bay or a narrow surrounding band blocks silence.

    Detections are the existing YOLO vehicle boxes at its unchanged 0.15 raw
    floor. The 3-pixel/5%-of-short-side band is a conservative guard, not a
    new classification or confidence threshold.
    """
    points = np.asarray(polygon, np.float32)
    x1, y1 = points.min(axis=0)
    x2, y2 = points.max(axis=0)
    band = max(3.0, .05 * min(x2 - x1, y2 - y1))
    for detection in detections:
        bx1, by1, bx2, by2 = detection['box']
        if bx2 < x1 - band or bx1 > x2 + band or by2 < y1 - band or by1 > y2 + band:
            continue
        # The padded bounding rectangle deliberately errs on the side of
        # withholding vacancy for slanted/tightly packed polygons.
        return True
    return False


class GuardedVacancy:
    """Camera/recording/bay scoped history, independent of UI playback speed."""

    def __init__(self, analyzer, interval=3.0, review_slots=None):
        self.analyzer = analyzer
        self.interval = interval
        self.empty = EmptyEvidence(analyzer)
        reviewed = {s['id']: s for s in review_slots or []}
        self.slots = {s['id']: {**s, **{k: v for k, v in reviewed.get(s['id'], {}).items()
                                       if k in ('mapping_status', 'visibility')}} for s in analyzer.slot_config}
        self.streaks = {}
        self.last = {}

    def reset(self, camera_id=None, recording_id=None):
        if camera_id is None and recording_id is None:
            self.streaks.clear(); self.last.clear()
            return
        matching = lambda key: ((camera_id is None or key[0] == camera_id)
                                and (recording_id is None or key[1] == recording_id))
        for key in list(self.streaks):
            if matching(key):
                del self.streaks[key]
        for key in list(self.last):
            if matching(key):
                del self.last[key]

    def _frame_ok(self, reference, yolo, image):
        return (self.interval == STREAK_INTERVAL_SECONDS and image is not None
            and image.shape == self.analyzer.setup.shape
            and reference.get('frame_id') is not None
            and reference.get('retrieval_status') == 'success'
            and reference.get('analysis_status') == 'estimated'
            and reference.get('stale') is False and reference.get('error') is None
            and (reference.get('alignment') or {}).get('ok') is True
            and yolo.get('analysis_status') == 'estimated' and not yolo.get('error')
            and yolo.get('inference_completed') is True
            and yolo.get('frame_id') == reference.get('frame_id')
            and yolo.get('source_id') == reference.get('source_id'))

    def apply(self, recording_id, position, reference, mog2, yolo, image, rows):
        camera_id = reference['source_id']
        stream = (camera_id, recording_id)
        frame_id = reference.get('frame_id')
        previous = self.last.get(stream)
        contiguous = (previous is not None and frame_id is not None and frame_id != previous[1]
                      and type(position) in (int, float) and math.isfinite(position)
                      and abs(position - previous[0] - STREAK_INTERVAL_SECONDS) <= 1e-6)
        if not contiguous:
            self.reset(camera_id, recording_id)
        self.last[stream] = (position, frame_id)
        frame_ok = self._frame_ok(reference, yolo, image)
        scores = self.empty.scores(image) if frame_ok and self.empty.banks else {}
        yolo_slots = {s['slot_id']: s for s in yolo['slots']}
        reference_slots = {s['slot_id']: s for s in reference['slots']}
        mog2_slots = {s['slot_id']: s for s in mog2['slots']}
        for row in rows:
            slot_id = row['slot_id']
            slot = self.slots[slot_id]
            evidence = yolo_slots[slot_id]
            key = (camera_id, recording_id, slot_id)
            row.update(base_final_state=row['final_state'], base_final_reason=row['final_reason'],
                       base_final_confirmed_by=row['final_confirmed_by'],
                       vacancy_guard_streak=0, vacancy_guard_required=STREAK_SAMPLES,
                       vacancy_guard_reason=None, vacancy_reference_difference=None,
                       vacancy_reference_limit=None, vacancy_evidence=None,
                       final_provisional=False, decision_policy=GUARDED_DECISION_POLICY)
            # The initial Final's definite routes keep their precedence.
            if row['base_final_state'] in ('occupied', 'vacant'):
                row['vacancy_guard_reason'] = 'existing_definite_route'
                self.streaks[key] = 0
                continue
            reason = None
            ref, mog = row['reference_state'], row['mog2_state']
            if not frame_ok or mog2.get('analysis_status') != 'estimated' or mog2.get('error'):
                reason = 'frame_or_model_unusable'
            elif slot.get('visibility') not in (None, 'visible', 'clear') or slot.get('mapping_status') not in VISIBILITY_MAPPING:
                reason = 'bay_visibility_not_reviewed_or_occluded'
            elif reference_slots[slot_id].get('reason') in ('bay_not_visible_in_this_view', 'registered_bay_outside_visible_frame'):
                reason = 'bay_not_visible'
            elif mog2_slots[slot_id].get('reason') in ('bay_not_visible_in_this_view', 'registered_bay_outside_visible_frame'):
                reason = 'bay_not_visible'
            elif 'occupied' in (ref, mog) or {ref, mog} == {'occupied', 'vacant'}:
                reason = 'classic_occupied_or_conflicting_evidence'
            elif (not evidence.get('requested') or evidence.get('state') != 'uncertain'
                  or evidence.get('reason') != 'no_qualifying_detection_is_not_vacancy'):
                reason = 'vehicle_overlap_or_verification_unavailable'
            elif near_vehicle_box(slot['polygon'], yolo.get('detections', [])):
                reason = 'weak_or_nearby_vehicle_box'
            elif slot.get('reference_image'):
                score, limit = scores.get(slot_id), self.empty.limits.get(slot_id)
                if score is None and self.analyzer._calibration_valid(slot):
                    score = row.get('reference_difference')
                    limit = slot['calibration']['vacant_max']
                if score is None or limit is None:
                    reason = 'reviewed_empty_match_unavailable'
                else:
                    row['vacancy_reference_difference'] = score
                    row['vacancy_reference_limit'] = limit
                    if score > limit:
                        reason = 'reviewed_empty_mismatch'
                    else:
                        row['vacancy_evidence'] = 'reviewed_empty_and_three_clean_no_detections'
            else:
                row['vacancy_evidence'] = 'provisional_repeated_no_detection'
            if reason:
                self.streaks[key] = 0
                row['vacancy_guard_reason'] = reason
                continue
            count = min(STREAK_SAMPLES, self.streaks.get(key, 0) + 1)
            self.streaks[key] = count
            row['vacancy_guard_streak'] = count
            if count < STREAK_SAMPLES:
                row['vacancy_guard_reason'] = 'streak_incomplete'
                continue
            if row['vacancy_evidence'] == 'provisional_repeated_no_detection':
                row.update(final_state='vacant', final_reason='provisional_vacant_three_no_detections',
                           final_confirmed_by=None, final_provisional=True,
                           vacancy_guard_reason='provisional_repeated_no_detection')
            else:
                row.update(final_state='vacant', final_reason='guarded_vacant_reviewed_empty_three_no_detections',
                           final_confirmed_by='reviewed_empty_and_three_clean_no_detections',
                           vacancy_guard_reason='reviewed_empty_and_three_clean_no_detections')
        return rows
