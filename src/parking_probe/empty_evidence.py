"""Historical empty-appearance diagnostic; not used for normal Run final decisions."""
import math

from .config import polygon_signature
from .sources import read_image, SourceError
from .vision import difference_score, preprocess, pixel_hash, PREPROCESSING


class EmptyEvidence:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.banks, self.limits = {}, {}
        for slot in analyzer.slot_config:
            key = slot['id']
            meta = slot.get('vehicle_empty_match') or {}
            limit = meta.get('max_difference')
            if (key not in analyzer.references or meta.get('vacant_examples', 0) < 5
                    or meta.get('preprocessing') != PREPROCESSING
                    or meta.get('reference_pixel_hash') != analyzer.reference_hashes.get(key)
                    or meta.get('setup_pixel_hash') != analyzer.setup_hash
                    or meta.get('polygon_signature') != polygon_signature(slot['polygon'])
                    or type(limit) not in (float, int) or not math.isfinite(limit) or not 0 < limit <= .04):
                continue
            bank = [analyzer.references[key]]
            for name in slot.get('vehicle_empty_reference_images', []):
                try:
                    image = read_image(analyzer.config.resolve(name))
                    if image.shape == analyzer.setup.shape and pixel_hash(image) in meta.get('additional_reference_hashes', []):
                        bank.append(preprocess(image))
                except (SourceError, OSError):
                    continue
            self.banks[key], self.limits[key] = bank, limit

    def scores(self, image):
        gray = preprocess(image)
        return {key: min(difference_score(gray, ref, self.analyzer.masks[key]) for ref in bank)
                for key, bank in self.banks.items()}

    def candidates(self, image, reference, mog2, verification):
        """No successful verification means no empty fallback, even on a match."""
        scores = self.scores(image) if (image is not None and not reference.get('stale')
                    and reference.get('analysis_status') == 'estimated'
                    and verification.get('inference_completed') and not verification.get('error')) else {}
        ref = {s['slot_id']: s['state'] for s in reference['slots']}
        mog = {s['slot_id']: s['state'] for s in mog2['slots']}
        yolo = {s['slot_id']: s for s in verification['slots']}
        results = {}
        for slot in self.analyzer.slot_config:
            key = slot['id']; check = yolo[key]
            score, limit = scores.get(key), self.limits.get(key)
            reason = 'empty_reference_unavailable'
            if not check.get('requested'):
                reason = 'not_requested_opencv_agreement'
            elif score is None:
                reason = 'verification_unavailable' if verification.get('error') else reason
            elif 'occupied' in (ref[key], mog[key]):
                reason = 'classic_occupied_evidence_blocks_vacancy'
            elif check['state'] != 'uncertain' or check['reason'] != 'no_qualifying_detection_is_not_vacancy':
                reason = 'vehicle_or_ambiguous_overlap_blocks_vacancy'
            elif slot.get('visibility') == 'occluded':
                reason = 'bay_not_visible'
            elif score > limit:
                reason = 'does_not_match_reviewed_empty'
            else:
                reason = 'reviewed_empty_match_after_yolo'
            results[key] = {'candidate': reason == 'reviewed_empty_match_after_yolo', 'reason': reason,
                            'supports_vacancy': (ref[key] == mog[key] == 'vacant'
                                and not reference.get('stale') and reference.get('analysis_status') == 'estimated'),
                            'difference': score, 'limit': limit}
        return results


class VacancyConfirmation:
    """Per-recording candidate streak; never persists a state through bad evidence."""
    def __init__(self, interval=3, required=3):
        self.interval, self.required = interval, required
        self.last_time = None
        self.last_frame = None
        self.streaks = {}

    def update(self, position, frame_id, candidates):
        contiguous = (self.last_time is not None and frame_id != self.last_frame
                      and math.isfinite(position) and .5*self.interval <= position-self.last_time <= 1.5*self.interval)
        if not contiguous:
            self.streaks.clear()
        result = {}
        for key, candidate in candidates.items():
            supported = candidate['candidate'] or candidate.get('supports_vacancy', False)
            count = min(self.required, self.streaks.get(key, 0)+1) if supported else 0
            self.streaks[key] = count
            result[key] = {**candidate, 'consecutive_samples': count, 'required_samples': self.required,
                           'confirmed': count >= self.required}
        self.last_time, self.last_frame = position, frame_id
        return result
