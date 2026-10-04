"""End-to-end local HTTP check: paced frame -> SQLite -> API bay counts."""
import json
import time

import requests

from parking_probe.catalog import PROJECT_ROOT
from parking_probe.config import atomic_json

base = 'http://127.0.0.1:8765'
headers = {'X-Parking-Client': 'web'}
started = time.monotonic()
reply = requests.post(base + '/api/replay/start', headers=headers,
    json={'source_id': 'chad-1'}, timeout=8)
reply.raise_for_status()
assert reply.status_code == 202
samples = []
last = 0
try:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        sent = time.monotonic()
        response = requests.get(base + '/api/replay', timeout=8)
        response.raise_for_status()
        value = response.json()
        received = time.monotonic()
        assert value['live_availability'] is False and value['simulation'] is True
        assert value['capacity'] == len(value['bays'])
        assert value['available'] == sum(b['available'] for b in value['bays'])
        assert value['provisional_occupied'] == sum(
            b['state'] == 'occupied' and b['provisional'] for b in value['bays'])
        published = value['metrics']['published_frames']
        if published > last:
            samples.append({'published': published, 'replay_seconds': value['replay_seconds'],
                'elapsed_seconds': received-started, 'api_roundtrip_ms': (received-sent)*1000,
                'available': value['available'], 'counts': value['counts']})
            last = published
        if published >= 3 or value['status'] in ('failed', 'complete', 'complete_with_errors'):
            break
        time.sleep(.25)
finally:
    requests.post(base + '/api/replay/stop', headers=headers, timeout=8).raise_for_status()
report = {'source': 'chad-1', 'mode': 'replay', 'http_poll_interval_seconds': .25,
    'samples': samples, 'first_http_publication_elapsed_seconds': samples[0]['elapsed_seconds'] if samples else None,
    'note': 'Local decode-to-API observation, not camera capture-to-Flutter paint latency.'}
out = PROJECT_ROOT / 'runs/evaluation/replay-http-smoke.json'
atomic_json(out, report)
print(json.dumps(report, indent=2))
if len(samples) < 3:
    raise SystemExit('Did not receive three replay samples')
