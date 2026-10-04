"""Paced, single-recording replay with durable events and conservative availability.

Replay clock time measures when a historical frame was decoded here. It is never
presented as the original camera capture time or as live availability.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .catalog import CLIPS, PROJECT_ROOT

INTERVAL_SECONDS = 3.0
STALE_SECONDS = max(10.0, 3 * INTERVAL_SECONDS)
SOURCES = {c.id: ('chad', c) for c in CLIPS}
SOURCES['overhead-1'] = ('overhead', None)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ReplayStore:
    """One source/session at a time. SQLite is an audit log, not a live feed."""
    def __init__(self, db_path, inventories, clock=time.monotonic):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS replay_events (
              session_id TEXT NOT NULL, source_id TEXT NOT NULL, sequence INTEGER NOT NULL,
              bay_id TEXT NOT NULL, replay_seconds REAL NOT NULL, observed_at TEXT NOT NULL,
              raw_state TEXT NOT NULL, candidate_state TEXT, candidate_streak INTEGER NOT NULL,
              confirmed_state TEXT, source TEXT, reason TEXT, provisional INTEGER NOT NULL,
              valid INTEGER NOT NULL, PRIMARY KEY(session_id, bay_id, sequence));
            CREATE TABLE IF NOT EXISTS replay_sessions (
              session_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, started_at TEXT NOT NULL,
              status TEXT NOT NULL, message TEXT NOT NULL);
        ''')
        self.conn.commit()
        self.inventories = inventories
        self.session_id = None
        self.source_id = None
        self.status = 'idle'
        self.message = 'Choose a recording to start the replay simulation.'
        self.bays = {}
        self.last_sequence = -1
        self.last_seconds = -1.0
        self.sample_at = None
        self.replay_seconds = None
        self.metrics = {'published_frames': 0, 'rejected_frames': 0}

    def begin(self, source_id):
        if source_id not in SOURCES or source_id not in self.inventories:
            raise ValueError('Unsupported replay recording')
        with self.lock:
            self.session_id = uuid.uuid4().hex
            self.source_id = source_id
            self.status = 'preparing'
            self.message = 'Preparing models and calibration. No frames have been published.'
            self.bays = {bay: {'candidate_state': None, 'candidate_streak': 0,
                'confirmed_state': None, 'raw_state': 'unknown', 'source': None,
                'reason': 'no_frame', 'provisional': False, 'last_valid': None}
                for bay in self.inventories[source_id]}
            self.last_sequence = -1
            self.last_seconds = -1.0
            self.sample_at = None
            self.replay_seconds = None
            self.metrics = {'published_frames': 0, 'rejected_frames': 0}
            self.conn.execute('INSERT INTO replay_sessions VALUES (?,?,?,?,?)',
                (self.session_id, source_id, utc_now(), self.status, self.message))
            self.conn.commit()
            return self.session_id

    def set_status(self, status, message):
        with self.lock:
            self.status, self.message = status, message
            if self.session_id:
                self.conn.execute('UPDATE replay_sessions SET status=?, message=? WHERE session_id=?',
                    (status, message, self.session_id))
                self.conn.commit()

    def publish(self, source_id, sequence, replay_seconds, rows, *, frame_valid=True):
        """Reject repeated/late frames. Invalid frames cannot confirm a state."""
        with self.lock:
            if (source_id != self.source_id or type(sequence) is not int or sequence <= self.last_sequence
                    or replay_seconds <= self.last_seconds):
                self.metrics['rejected_frames'] += 1
                return False
            by_bay = {row['bay_id']: row for row in rows}
            if len(by_bay) != len(rows) or set(by_bay) != set(self.bays):
                raise ValueError('Replay frame must cover each mapped bay exactly once')
            if any(row.get('final_state') not in ('occupied', 'vacant', 'uncertain', 'unknown')
                   for row in rows):
                raise ValueError('Invalid bay state')
            next_bays = deepcopy(self.bays)
            sample_at = utc_now()
            instant = self.clock()
            events = []
            for bay_id, state in next_bays.items():
                row = by_bay[bay_id]
                raw = row['final_state']
                valid = bool(frame_valid and raw in ('occupied', 'vacant'))
                state['raw_state'] = raw if frame_valid else 'unknown'
                state['source'] = row.get('final_confirmed_by') if frame_valid else None
                state['reason'] = row.get('final_reason') if frame_valid else 'invalid_frame'
                state['provisional'] = bool(row.get('final_provisional')) if frame_valid else False
                if valid:
                    state['last_valid'] = instant
                    if state['candidate_state'] == raw:
                        state['candidate_streak'] += 1
                    else:
                        state['candidate_state'] = raw
                        state['candidate_streak'] = 1
                    if state['candidate_streak'] >= 3:
                        state['confirmed_state'] = raw
                else:
                    state['candidate_state'] = None
                    state['candidate_streak'] = 0
                events.append((self.session_id, source_id, sequence, bay_id, replay_seconds,
                    sample_at, state['raw_state'], state['candidate_state'],
                    state['candidate_streak'], state['confirmed_state'], state['source'],
                    state['reason'], int(state['provisional']), int(valid)))
            message = f'Replayed {source_id} at {replay_seconds:.0f}s.'
            try:
                self.conn.executemany('INSERT INTO replay_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', events)
                self.conn.execute('UPDATE replay_sessions SET status=?, message=? WHERE session_id=?',
                    ('playing', message, self.session_id))
                self.conn.commit()
            except sqlite3.Error:
                self.conn.rollback()
                raise
            self.bays = next_bays
            self.last_sequence = sequence
            self.last_seconds = replay_seconds
            self.replay_seconds = replay_seconds
            self.sample_at = sample_at
            self.status = 'playing'
            self.message = message
            self.metrics['published_frames'] += 1
            return True

    def snapshot(self):
        with self.lock:
            now = self.clock()
            bays = []
            for bay_id, state in self.bays.items():
                age = None if state['last_valid'] is None else max(0.0, now - state['last_valid'])
                fresh = age is not None and age <= STALE_SECONDS
                # A first occupied candidate blocks a previously vacant bay.
                possible_occupied = state['candidate_state'] == 'occupied'
                available = bool(fresh and state['confirmed_state'] == 'vacant' and not possible_occupied)
                effective = ('stale' if not fresh else
                    'occupied' if possible_occupied else state['confirmed_state'] or 'unknown')
                bays.append({'bay_id': bay_id, 'state': effective,
                    'raw_state': state['raw_state'], 'candidate_state': state['candidate_state'],
                    'candidate_streak': state['candidate_streak'],
                    'confirmed_state': state['confirmed_state'],
                    'provisional': bool(state['provisional'] or (possible_occupied and state['confirmed_state'] != 'occupied')),
                    'source': state['source'], 'reason': state['reason'],
                    'fresh': fresh, 'age_seconds': round(age, 3) if age is not None else None,
                    'available': available})
            counts = Counter(b['state'] for b in bays)
            return {'schema_version': 1, 'mode': 'replay', 'live_availability': False,
                'simulation': True, 'source_id': self.source_id, 'session_id': self.session_id,
                'status': self.status, 'message': self.message, 'served_at': utc_now(),
                'original_capture_time_known': False, 'source_capture_time': None,
                'last_processed_at': self.sample_at, 'replay_seconds': self.replay_seconds,
                'sample_interval_seconds': INTERVAL_SECONDS, 'stale_after_seconds': STALE_SECONDS,
                'capacity': len(bays), 'available': sum(b['available'] for b in bays),
                'counts': {s: counts[s] for s in ('occupied', 'vacant', 'unknown', 'stale')},
                'provisional_occupied': sum(b['state'] == 'occupied' and b['provisional'] for b in bays),
                'metrics': dict(self.metrics), 'bays': bays}


class ReplayJob:
    def __init__(self, root=PROJECT_ROOT, interval=INTERVAL_SECONDS):
        self.root = Path(root)
        self.interval = interval
        inventories = {}
        for source_id in SOURCES:
            site = 'overhead' if source_id == 'overhead-1' else 'chad'
            preset = 'overhead-all-bays.json' if site == 'overhead' else 'chad-camera-1-expanded.json'
            slots = json.loads((self.root / 'presets' / preset).read_text(encoding='utf-8'))['slots']
            inventories[source_id] = [s['bay_id'] for s in slots]
        self.store = ReplayStore(self.root / 'runs/replay/events.sqlite3', inventories)
        self.stop = threading.Event()
        self.worker = None
        self.lock = threading.Lock()

    def start(self, source_id):
        if source_id not in SOURCES:
            raise ValueError('Unsupported replay recording')
        with self.lock:
            if self.worker and self.worker.is_alive():
                return False
            self.stop = threading.Event()
            self.store.begin(source_id)
            self.worker = threading.Thread(target=self._run, args=(source_id,), daemon=True,
                name='parking-replay')
            self.worker.start()
            return True

    def halt(self):
        self.stop.set()
        self.store.set_status('stopping', 'Stopping the replay simulation…')

    def _run(self, source_id):
        service = None
        try:
            from .areas import VIEWS, OVERHEAD, inventory, fetch_overhead
            from .comparison import run_comparison
            from .monitor import prepare_preset
            from .view_presets import prepare_view
            from .vehicle import VehicleDetector, prepare_model
            from .yolo import YOLODetector, VerificationService
            site, clip = SOURCES[source_id]
            def emit(kind, value):
                if kind != 'comparison_samples':
                    return
                for pair in value['recordings']:
                    reference = pair['reference']
                    valid = (reference.get('analysis_status') == 'estimated'
                        and reference.get('stale') is False and not reference.get('error')
                        and (reference.get('alignment') or {}).get('ok') is True)
                    self.store.publish(source_id, reference['video_frame_index'],
                        reference['sample_time_seconds'], pair['rows'], frame_valid=valid)
            mobilenet = VehicleDetector(prepare_model(cancelled=self.stop.is_set))
            service = VerificationService(YOLODetector())
            if site == 'chad':
                view = VIEWS['chad-1']
                prepared = prepare_view(view, emit, self.stop, include_empty_evidence=True)
                mapping = {s['id']: s['bay_id'] for s in inventory(view)}
                clips = [clip]
                profile = 'coco'
            else:
                prepared = prepare_preset(emit, self.stop, self.root / 'presets/overhead-all-bays.json',
                    [OVERHEAD], fetch_overhead, self.root / 'data/overhead-all')
                mapping = {s['id']: s['bay_id'] for s in inventory(VIEWS['overhead-1'])}
                clips = [OVERHEAD]
                profile = 'aerial'
            out = self.root / 'runs/replay' / self.store.session_id
            code = run_comparison(clips, self.interval, self.stop, emit, fast=False, out=out,
                prepared=prepared, bay_map=mapping, verification=True, service=service,
                verification_profile=profile, detector=mobilenet, opencv_first=True)
            self.store.set_status('stopped' if self.stop.is_set() else 'complete_with_errors' if code else 'complete',
                'Replay stopped.' if self.stop.is_set() else 'Historical recording finished. Results expire when stale.')
        except Exception as exc:
            self.store.set_status('failed', f'Replay failed: {type(exc).__name__}. See local run log.')
            out = self.root / 'runs/replay' / (self.store.session_id or 'unknown')
            out.mkdir(parents=True, exist_ok=True)
            import traceback
            (out / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        finally:
            if service:
                service.close()
