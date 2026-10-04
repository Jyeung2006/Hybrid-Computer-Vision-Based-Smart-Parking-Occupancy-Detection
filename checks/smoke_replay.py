"""Run three paced CHAD frames and record publication/availability timings."""
import json
import time

from parking_probe.catalog import PROJECT_ROOT
from parking_probe.config import atomic_json
from parking_probe.replay_service import ReplayJob

job = ReplayJob()
started = time.monotonic()
assert job.start('chad-1')
first_at = None
seen = []
deadline = started + 240
try:
    while time.monotonic() < deadline:
        value = job.store.snapshot()
        published = value['metrics']['published_frames']
        if published > len(seen):
            seen.append({'published': published, 'elapsed_seconds': time.monotonic() - started,
                'replay_seconds': value['replay_seconds'], 'counts': value['counts'],
                'available': value['available'], 'provisional_occupied': value['provisional_occupied']})
            if first_at is None:
                first_at = seen[0]['elapsed_seconds']
        if published >= 3 or value['status'] in ('failed', 'complete', 'complete_with_errors'):
            break
        time.sleep(.2)
finally:
    job.halt()
    if job.worker:
        job.worker.join(30)
result = {'source': 'chad-1', 'mode': 'replay', 'live_availability': False,
    'first_publication_elapsed_seconds': first_at, 'samples': seen,
    'final_status': job.store.snapshot()['status'],
    'stale_after_seconds': job.store.snapshot()['stale_after_seconds']}
output = PROJECT_ROOT / 'runs/evaluation/replay-smoke.json'
atomic_json(output, result)
print(json.dumps(result, indent=2))
if not seen or job.store.snapshot()['status'] == 'failed':
    raise SystemExit(1)
