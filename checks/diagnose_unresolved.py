"""Read-only policy/detector audit; writes reports, never changes decisions."""
from collections import Counter
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parking_probe.monitor import recording_for_recipe
from parking_probe.yolo import YOLODetector, associate, needs_verification, final_decision


def observations(run):
    return [item for path in sorted(run.glob('*/history.jsonl'))
            for line in path.read_text().splitlines()
            for item in json.loads(line)['recordings']]


def indexed_rows(items):
    return {(item['recording_id'], item['reference']['frame_id'], row['bay_id']): row
            for item in items for row in item['rows']}


def bay_candidates(slots, detections, anchor_fraction):
    results = {s['id']: [] for s in slots}
    for detection in detections:
        x1, y1, x2, y2 = detection['box']
        rectangle = np.float32([[x1,y1],[x2,y1],[x2,y2],[x1,y2]])
        anchor = ((x1+x2)/2, y1+anchor_fraction*(y2-y1))
        candidates = []
        for slot in slots:
            polygon = np.float32(slot['polygon'])
            overlap, _ = cv2.intersectConvexConvex(polygon, rectangle)
            if overlap/abs(cv2.contourArea(polygon)) >= .25 and cv2.pointPolygonTest(polygon, anchor, True) >= 0:
                candidates.append(slot['id'])
        for key in candidates:
            results[key].append({'score': detection['detector_score'], 'class': detection['class'],
                                 'unique_bay': len(candidates) == 1})
    return results


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'runs/areas/20260919T161628_245646Z'
    previous = ROOT/'runs/areas/20260918T185845_684414Z'
    items = observations(run)
    old, new = indexed_rows(observations(previous)), indexed_rows(items)
    common = [k for k in old.keys() & new.keys() if k[0].startswith('chad')]
    transitions = Counter((old[k]['final_state'], new[k]['final_state']) for k in common)
    classic_changes = sum((old[k]['reference_state'], old[k]['mog2_state']) !=
                          (new[k]['reference_state'], new[k]['mog2_state']) for k in common)
    result = {'run': str(run), 'previous_run': str(previous), 'opencv_version': cv2.__version__,
              'production_decisions_changed': False, 'frames': len(items),
              'inference_completed': sum(x['yolo']['inference_completed'] for x in items),
              'inference_errors': dict(Counter(x['yolo']['error'] for x in items if x['yolo']['error'])),
              'matched_chad_bay_observations': len(common), 'classic_state_changes': classic_changes,
              'final_transitions': {f'{a}->{b}': n for (a,b), n in sorted(transitions.items())},
              'agreement_overwritten': sum(not needs_verification(r['reference_state'], r['mog2_state']) and
                  r['final_state'] != r['reference_state'] for x in items for r in x['rows']),
              'fresh_inference': []}
    detector = YOLODetector()
    out = ROOT/'runs/verification/unresolved-audit'
    out.mkdir(parents=True, exist_ok=True)
    for key, recipe_file, media, profile in [
        ('overhead-1', 'overhead-all-bays.json', 'data/other-parking/carPark.mp4', 'aerial'),
        ('chad-1', 'chad-camera-1-expanded.json', 'data/chad/1_029_0.mp4', 'coco'),
    ]:
        item = [x for x in items if x['recording_id'] == key][-1]
        recipe = json.loads((ROOT/'presets'/recipe_file).read_text())
        recording = recording_for_recipe(ROOT/media, recipe)
        try:
            image = recording.read(item['reference']['video_frame_index'])
        finally:
            recording.close()
        detections = detector.detect(image, profile)
        requested = set(item['yolo']['requested_slot_ids'])
        slots = recipe['slots']
        rows = associate(slots, detections, requested, .5 if profile == 'aerial' else .82)
        saved = {s['slot_id']:s for s in item['yolo']['slots']}
        assert all(saved[r['slot_id']]['state'] == r['state'] for r in rows)
        candidates = bay_candidates(slots, detections, .5 if profile == 'aerial' else .82)
        ref = {s['slot_id']:s for s in item['reference']['slots']}
        mog = {s['slot_id']:s for s in item['mog2']['slots']}
        evidence = []
        for row in rows:
            sid = row['slot_id']
            final, _ = final_decision(ref[sid]['state'], mog[sid]['state'], row['state'])
            if final not in ('uncertain', 'unknown'):
                continue
            hits = [h for h in candidates[sid] if h['unique_bay']]
            best = max((h['score'] for h in hits), default=None)
            evidence.append({'slot_id': sid, 'reference': ref[sid], 'mog2': mog[sid],
                             'yolo': row, 'best_unique_candidate_score': best,
                             'candidate_count': len(candidates[sid]),
                             'failure_category': 'below_0.80' if best is not None and best < .8
                                  else 'no_uniquely_assigned_candidate'})
        for slot in slots:
            if slot['id'] in {s['slot_id'] for s in evidence}:
                points = np.array(slot['polygon'], np.int32)
                cv2.polylines(image, [points], True, (0,190,255), 2)
                pos = tuple(points[0] + [2,12])
                cv2.putText(image, slot['id'], pos, cv2.FONT_HERSHEY_SIMPLEX, .4, (0,0,0), 2)
                cv2.putText(image, slot['id'], pos, cv2.FONT_HERSHEY_SIMPLEX, .4, (0,255,255), 1)
        assert cv2.imwrite(str(out/f'{key}-unresolved.png'), image)
        result['fresh_inference'].append({'recording_id': key, 'frame_id': item['reference']['frame_id'],
            'video_seconds': item['reference']['sample_time_seconds'], 'model_profile': profile,
            'states_match_saved_results': True, 'detections_at_least_0_15': len(detections),
            'unresolved_categories': dict(Counter(s['failure_category'] for s in evidence)),
            'unresolved': evidence})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='fresh_inference'}, indent=2))
    for item in result['fresh_inference']:
        print(item['recording_id'], item['unresolved_categories'])
        for row in item['unresolved']:
            print(row['slot_id'], row['reference']['state'], row['mog2']['state'],
                  row['failure_category'], row['best_unique_candidate_score'])


if __name__ == '__main__':
    main()
