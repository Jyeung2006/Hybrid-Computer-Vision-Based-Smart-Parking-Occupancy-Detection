"""Capture one active replay at desktop width; phone widths use Flutter tests.

Headless Chrome imposes a 512px minimum layout viewport when --window-size is
smaller, so its 390px screenshots are misleading crops rather than phone QA.
"""
from pathlib import Path
import subprocess
import time

import requests

from parking_probe.catalog import PROJECT_ROOT

base = 'http://127.0.0.1:8765'
chrome = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
out = PROJECT_ROOT / 'runs/verification/replay-browser'
out.mkdir(parents=True, exist_ok=True)
headers = {'X-Parking-Client': 'web'}
response = requests.post(base + '/api/replay/start', headers=headers,
    json={'source_id': 'chad-1'}, timeout=8)
response.raise_for_status()
if response.status_code != 202:
    raise RuntimeError('Replay already running')
try:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        state = requests.get(base + '/api/replay', timeout=8).json()
        if state['metrics']['published_frames'] >= 3:
            break
        if state['status'] == 'failed':
            raise RuntimeError(state['message'])
        time.sleep(.25)
    else:
        raise TimeoutError('No confirmed replay frame')
    for name, width, height in [('desktop', 1440, 1000)]:
        image = out / f'replay-active-{name}.png'
        command = [str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--force-device-scale-factor=1',
            f'--user-data-dir={out / ("profile-" + name)}', f'--window-size={width},{height}',
            '--virtual-time-budget=5000', f'--screenshot={image}',
            base + '/#/replay']
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if completed.returncode or not image.is_file():
            raise RuntimeError(f'Chrome screenshot failed: {completed.stderr[:400]}')
        print(f'{name}: {image} ({image.stat().st_size} bytes)')
finally:
    requests.post(base + '/api/replay/stop', headers=headers, timeout=8).raise_for_status()
