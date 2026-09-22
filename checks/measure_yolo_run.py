"""Summarize saved observations; these are coverage/timing, not accuracy labels."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    ui = json.loads((ROOT / 'runs/verification/interface-yolo-check.json').read_text())
    run = Path(ui['analysis_directory'])
    groups = {'chad': [], 'overhead': []}
    for path in sorted(run.glob('*/history.jsonl')):
        for line in path.read_text().splitlines():
            tick = json.loads(line)
            for item in tick['recordings']:
                if 'yolo' in item:
                    groups['overhead' if item['recording_id'] == 'overhead-1' else 'chad'].append(item)

    def timing(values):
        return {'median_ms': float(np.median(values)), 'p95_ms': float(np.percentile(values, 95)),
                'max_ms': float(max(values))} if values else None

    result = {'run': str(run), 'preparation_seconds': ui['preparation_seconds'],
              'accuracy_measured': False, 'false_vacant_rate': None, 'false_occupied_rate': None,
              'timing_scope': 'Final branch sum excludes decode/registration, writes and rendering.', 'groups': {}}
    for name, items in groups.items():
        states = [slot['state'] for item in items for slot in item['final']['slots']]
        counts = {state: states.count(state) for state in ('occupied', 'vacant', 'uncertain', 'unknown')}
        result['groups'][name] = {
            'sampled_frames': len(items), 'bay_observations': len(states), 'counts': counts,
            'decision_coverage_pct': 100 * (counts['occupied'] + counts['vacant']) / len(states),
            'inference_requested_frames': sum(x['yolo']['inference_requested'] for x in items),
            'inference_completed_frames': sum(x['yolo']['inference_completed'] for x in items),
            'requested_bay_observations': sum(len(x['yolo']['requested_slot_ids']) for x in items),
            'skipped_bay_observations': sum(x['yolo']['skipped_slot_count'] for x in items),
            'final_branch_processing': timing([x['final']['processing_duration_ms'] for x in items]),
            'yolo_inference': timing([x['yolo']['inference_ms'] for x in items if x['yolo']['inference_completed']]),
            'queue_wait': timing([x['yolo']['queue_wait_ms'] for x in items if x['yolo']['inference_completed']]),
        }
    result['overhead_timeline'] = [dict(video_seconds=x['final']['sample_time_seconds'], **x['final']['summary'])
                                   for x in groups['overhead']]
    output = ROOT / 'runs/verification/yolo-measurements.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'overhead_timeline'}, indent=2))


if __name__ == '__main__':
    main()
