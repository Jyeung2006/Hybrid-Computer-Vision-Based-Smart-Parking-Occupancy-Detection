"""Inventory support for isolated bay calibration; never edits active presets."""
import json

from parking_probe.catalog import PROJECT_ROOT
from parking_probe.config import atomic_json

report = {'status': 'candidate_inventory_only_no_preset_promotion', 'views': {}}
for view, filename in [('CHAD Camera 1', 'chad-camera-1-expanded.json'),
                       ('Overhead', 'overhead-all-bays.json')]:
    recipe = json.loads((PROJECT_ROOT / 'presets' / filename).read_text(encoding='utf-8'))
    bays = []
    for slot in recipe['slots']:
        def count(state):
            groups = [slot[state]] if isinstance(slot.get(state), dict) else []
            groups += [x for x in slot.get('additional_samples', {}).get(state, []) if isinstance(x, dict)]
            return sum(len(x.get('seconds', [])) for x in groups)
        empty, occupied = count('vacant'), count('occupied')
        eligible = empty > 0 and occupied > 0
        bays.append({'bay_id': slot['bay_id'], 'vacant_examples': empty,
            'occupied_examples': occupied, 'two_state_candidate_supported': eligible,
            'promotion': 'held: no separate candidate and development non-regression replay'
                if eligible else 'held: missing verified state'})
    report['views'][view] = {'mapped_bays': len(bays),
        'two_state_examples': sum(b['two_state_candidate_supported'] for b in bays),
        'fallback_only': sum(not b['two_state_candidate_supported'] for b in bays),
        'bays': bays}
out = PROJECT_ROOT / 'runs/evaluation/calibration-candidates.json'
out.parent.mkdir(parents=True, exist_ok=True)
atomic_json(out, report)
print(json.dumps({'output': str(out), 'views': {k: {f: v for f, v in d.items() if f != 'bays'}
    for k, d in report['views'].items()}}, indent=2))
