"""Local Flutter/API host using the existing OpenCV-first recorded pipeline.

This is recorded evidence, never a claim of live camera availability. One CHAD
Camera-1 recording and one overhead recording contribute to a response.
"""
from collections import Counter
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from pathlib import Path
import threading
import traceback
from urllib.parse import parse_qs, urlsplit, unquote

from .catalog import PROJECT_ROOT, CLIPS
from .opencv_first import DECISION_POLICY
from .replay_service import ReplayJob, SOURCES

STATES = ('occupied', 'vacant', 'uncertain', 'unknown')
CHAD_RECORDINGS = tuple(c.id for c in CLIPS)


def now():
    return datetime.now(timezone.utc).isoformat()


class ResultStore:
    def __init__(self, root=PROJECT_ROOT):
        self.root = Path(root)
        self.cache = {}
        self.lock = threading.Lock()
        self.inventories = {}
        for key, preset in (('chad', 'chad-camera-1-expanded.json'), ('overhead', 'overhead-all-bays.json')):
            slots = json.loads((self.root / 'presets' / preset).read_text(encoding='utf-8'))['slots']
            ids = [s['bay_id'] for s in slots]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate physical bay IDs in inventory')
            self.inventories[key] = ids

    def _latest_pairs(self, path):
        """Ignore an incomplete trailing write; cache only by an observed file revision."""
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self.cache.get(path)
        if cached and cached[0] == signature:
            return cached[1]
        pairs = {}
        with path.open(encoding='utf-8') as handle:
            for line in handle:
                if not line.endswith('\n'):
                    break
                try:
                    batch = json.loads(line)
                    for pair in batch.get('recordings', []):
                        if pair.get('final', {}).get('decision_policy') == DECISION_POLICY:
                            pairs[pair['recording_id']] = pair
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        if len(self.cache) > 12:
            self.cache.clear()
        self.cache[path] = (signature, pairs)
        return pairs

    def _area(self, site, recording):
        ids = self.inventories[site]
        source = None
        rows = {}
        issue = 'No OpenCV-first analysis is available yet.'
        for run in sorted((self.root / 'runs/areas').glob('*'), reverse=True):
            path = run / site / 'history.jsonl'
            if not path.is_file():
                continue
            try:
                pair = self._latest_pairs(path).get(recording)
            except (OSError, UnicodeError):
                continue
            if pair is None:
                continue
            try:
                final = pair['final']
                reference = pair['reference']
                expected_camera = 'chad-camera-1' if site == 'chad' else 'overhead-demo-camera-1'
                # The frame identity ties displayed evidence to its recording.
                if (reference['video_id'] != recording or final['frame_id'] != reference['frame_id']
                        or pair['camera_id'] != expected_camera):
                    raise ValueError('Mismatched frame identity')
                candidates = pair['rows']
                for row in candidates:
                    bay = row['bay_id']
                    if bay in rows or bay not in ids or row['final_state'] not in STATES:
                        raise ValueError('Invalid or duplicate bay evidence')
                    if row.get('recording_id') != recording or row.get('frame_id') != reference['frame_id']:
                        raise ValueError('Mismatched bay evidence')
                    rows[bay] = row
                source = {
                    'run_id': run.name, 'recording_id': recording,
                    'frame_id': reference['frame_id'],
                    'sample_seconds': reference['sample_time_seconds'],
                    'processed_at': final['processed_at'],
                    'decision_policy': DECISION_POLICY,
                }
                issue = None
                if (reference.get('stale') is not False or reference.get('error')
                        or reference.get('analysis_status') != 'estimated'
                        or (reference.get('alignment') or {}).get('ok') is not True):
                    rows = {}
                    issue = 'The latest recorded frame is unusable; all bays are unknown.'
            except (KeyError, TypeError, ValueError):
                rows = {}
                issue = 'The latest recorded sample could not be validated.'
            break  # Never replace a latest failed frame with an older definite one.
        bays = [{
            'bay_id': bay, 'state': rows.get(bay, {}).get('final_state', 'unknown'),
            'provisional': bool(rows.get(bay, {}).get('final_provisional', False)),
            'source': rows.get(bay, {}).get('final_confirmed_by'),
            'reason': rows.get(bay, {}).get('final_reason', 'missing_observation'),
        } for bay in ids]
        counts = Counter(b['state'] for b in bays)
        return {
            'id': site, 'name': 'CHAD' if site == 'chad' else 'Overhead',
            'capacity': len(ids), **{s: counts[s] for s in STATES},
            'provisional_occupied': sum(b['state'] == 'occupied' and b['provisional'] for b in bays),
            'provisional_vacant': sum(b['state'] == 'vacant' and b['provisional'] for b in bays),
            'has_sample': source is not None, 'source': source, 'issue': issue,
            'scope': 'Camera 1 mapped bays' if site == 'chad' else 'All 69 mapped bays',
            'bays': bays,
        }

    def snapshot(self, chad='chad-1'):
        if chad not in CHAD_RECORDINGS:
            raise ValueError('Unsupported CHAD recording')
        with self.lock:
            areas = [self._area('chad', chad), self._area('overhead', 'overhead-1')]
        count_fields = ('capacity', *STATES, 'provisional_occupied', 'provisional_vacant')
        return {
            'schema_version': 1, 'mode': 'recorded', 'live_availability': False,
            'basis': 'latest_sample_per_selected_recording', 'served_at': now(),
            'chad_recording': chad, 'chad_recordings': list(CHAD_RECORDINGS),
            'areas': areas, 'totals': {k: sum(a[k] for a in areas) for k in count_fields},
        }


class AnalysisJob:
    def __init__(self, root=PROJECT_ROOT):
        self.root = Path(root)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.state = {'status': 'idle', 'message': 'Showing saved recorded results.', 'run_id': None}

    def status(self):
        with self.lock:
            return dict(self.state)

    def update(self, **fields):
        with self.lock:
            self.state.update(fields)

    def start(self):
        with self.lock:
            if self.state['status'] == 'running':
                return False
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
            self.state = {'status': 'running', 'message': 'Preparing the recorded analysis…', 'run_id': run_id}
        threading.Thread(target=self._run, args=(run_id,), daemon=True, name='web-parking-analysis').start()
        return True

    def _run(self, run_id):

        out = self.root / 'runs/areas' / run_id
        service = None
        issues = []

        def emit(kind, value):
            if kind == 'comparison_samples':
                clips = ', '.join(p['recording_id'] for p in value['recordings'])
                self.update(message=f'Analyzing {clips}: {value["timeline_seconds"]:.0f}s. Results update as samples finish.')

        try:
            out.mkdir(parents=True, exist_ok=True)
            from .areas import VIEWS, OVERHEAD, inventory, fetch_overhead
            from .comparison import run_comparison
            from .monitor import prepare_preset
            from .view_presets import prepare_view
            from .vehicle import VehicleDetector, prepare_model
            from .yolo import YOLODetector, VerificationService
            self.update(message='Loading MobileNet and YOLOv8…')
            mobilenet = VehicleDetector(prepare_model(cancelled=self.stop.is_set))
            service = VerificationService(YOLODetector())
            self.update(message='Preparing CHAD references and calibration…')
            view = VIEWS['chad-1']
            prepared = prepare_view(view, emit, self.stop, include_empty_evidence=True)
            code = run_comparison(CLIPS, 3.0, self.stop, emit, fast=True,
                out=out / 'chad', prepared=prepared,
                bay_map={s['id']: s['bay_id'] for s in inventory(view)},
                verification=True, service=service, detector=mobilenet, opencv_first=True)
            if code:
                issues.append('Some CHAD samples were unavailable.')
            self.update(message='Preparing Overhead references and calibration…')
            prepared = prepare_preset(emit, self.stop, self.root / 'presets/overhead-all-bays.json',
                [OVERHEAD], fetch_overhead, self.root / 'data/overhead-all')
            code = run_comparison([OVERHEAD], 3.0, self.stop, emit, fast=True,
                out=out / 'overhead', prepared=prepared,
                bay_map={s['id']: s['bay_id'] for s in inventory(VIEWS['overhead-1'])},
                verification=True, service=service, verification_profile='aerial',
                detector=mobilenet, opencv_first=True)
            if code:
                issues.append('Some Overhead samples were unavailable.')
            self.update(status='complete', message=' '.join(issues) or 'Analysis complete. Showing the latest recorded samples.')
        except Exception:
            try:
                (out / 'web-analysis-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            except OSError:
                pass
            self.update(status='failed', message='Analysis failed. Previous recorded results remain labelled with their original times. See the run log.')
        finally:
            if service:
                service.close()
            try:
                (out / 'web-analysis-status.json').write_text(json.dumps(self.status(), indent=2), encoding='utf-8')
            except OSError:
                pass


class ParkingHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, store, job, replay, web_root, **kwargs):
        self.store, self.job, self.replay = store, job, replay
        self.web_root = Path(web_root).resolve()
        super().__init__(*args, directory=str(self.web_root), **kwargs)

    def _local_request(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def _same_origin_request(self):
        return self.headers.get('Origin') in (None, f'http://{self.headers.get("Host")}')

    def send_json(self, value, code=200):
        body = json.dumps(value, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._local_request():
            return self.send_json({'error': 'Local requests only'}, 403)
        url = urlsplit(self.path)
        if url.path == '/api/occupancy':
            try:
                selected = parse_qs(url.query).get('chad', ['chad-1'])[0]
                data = self.store.snapshot(selected)
                data['analysis'] = self.job.status()
                return self.send_json(data)
            except ValueError as exc:
                return self.send_json({'error': str(exc)}, 400)
            except Exception:
                return self.send_json({'error': 'Recorded results are temporarily unavailable'}, 503)
        if url.path == '/api/replay':
            return self.send_json(self.replay.store.snapshot())
        if url.path.startswith('/api/'):
            return self.send_json({'error': 'Not found'}, 404)
        # Only built web assets can be served, including when a symlink exists.
        path = (self.web_root / unquote(url.path).lstrip('/')).resolve()
        if not path.is_relative_to(self.web_root):
            return self.send_json({'error': 'Not found'}, 404)
        if path.is_dir() and not (path / 'index.html').is_file():
            return self.send_json({'error': 'Not found'}, 404)
        super().do_GET()

    def do_POST(self):
        if (not self._local_request() or self.headers.get('X-Parking-Client') != 'web'
                or not self._same_origin_request()):
            return self.send_json({'error': 'Same-origin client required'}, 403)
        if self.path == '/api/analysis':
            started = self.job.start()
            return self.send_json(self.job.status(), 202 if started else 409)
        if self.path == '/api/replay/start':
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return self.send_json({'error': 'Invalid request size'}, 400)
            if size < 1 or size > 1024:
                return self.send_json({'error': 'Invalid request size'}, 400)
            try:
                body = json.loads(self.rfile.read(size))
                source_id = body['source_id']
                if source_id not in SOURCES:
                    raise ValueError('Unsupported replay recording')
                started = self.replay.start(source_id)
                return self.send_json(self.replay.store.snapshot(), 202 if started else 409)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                return self.send_json({'error': 'Unsupported replay recording'}, 400)
        if self.path == '/api/replay/stop':
            self.replay.halt()
            return self.send_json(self.replay.store.snapshot(), 202)
        return self.send_json({'error': 'Not found'}, 404)


def make_server(port=8765, root=PROJECT_ROOT, web_root=None):
    root = Path(root)
    web_root = web_root or root / 'apps/parking_web/build/web'
    store, job, replay = ResultStore(root), AnalysisJob(root), ReplayJob(root)
    server = ThreadingHTTPServer(('127.0.0.1', port), partial(ParkingHandler,
        store=store, job=job, replay=replay, web_root=web_root))
    server.analysis_job = job
    server.replay_job = replay
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f'Parking website and recorded-results API: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.analysis_job.stop.set()
        server.replay_job.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
