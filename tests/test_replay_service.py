import json
import pytest

from parking_probe.replay_service import ReplayStore, STALE_SECONDS


def row(state='vacant', provisional=False, bay='B08'):
    return {'bay_id': bay, 'final_state': state, 'final_provisional': provisional,
            'final_confirmed_by': 'mobilenet_reviewed_empty' if state == 'vacant' else 'yolov8',
            'final_reason': 'test'}


def test_confirmation_occupied_block_stale_and_ordering(tmp_path):
    instant = [0.0]
    store = ReplayStore(tmp_path / 'events.db', {'chad-1': ['B08']}, clock=lambda: instant[0])
    store.begin('chad-1')
    first = store.snapshot()
    assert first['live_availability'] is False and first['capacity'] == 1
    assert first['available'] == 0 and first['bays'][0]['state'] == 'stale'
    for sequence in range(3):
        instant[0] = sequence * 3.0
        assert store.publish('chad-1', sequence, float(sequence * 3), [row()])
    bay = store.snapshot()['bays'][0]
    assert bay['confirmed_state'] == 'vacant' and store.snapshot()['available'] == 1
    instant[0] = 9.0
    assert store.publish('chad-1', 3, 9.0, [row('occupied', True)])
    bay = store.snapshot()['bays'][0]
    assert bay['confirmed_state'] == 'vacant'
    assert bay['state'] == 'occupied' and bay['provisional'] is True
    assert store.snapshot()['available'] == 0
    assert not store.publish('chad-1', 3, 9.0, [row()])
    assert not store.publish('chad-1', 2, 6.0, [row()])
    assert store.snapshot()['metrics']['rejected_frames'] == 2
    instant[0] += STALE_SECONDS + .1
    bay = store.snapshot()['bays'][0]
    assert bay['state'] == 'stale' and bay['available'] is False
    assert store.snapshot()['available'] == 0


def test_invalid_frame_breaks_candidate_without_confirming(tmp_path):
    instant = [0.0]
    store = ReplayStore(tmp_path / 'events.db', {'chad-1': ['B08']}, clock=lambda: instant[0])
    store.begin('chad-1')
    assert store.publish('chad-1', 0, 0.0, [row()])
    assert store.publish('chad-1', 1, 3.0, [row()], frame_valid=False)
    assert store.snapshot()['bays'][0]['candidate_streak'] == 0
    assert store.publish('chad-1', 2, 6.0, [row()])
    assert store.snapshot()['bays'][0]['confirmed_state'] is None
    assert store.snapshot()['available'] == 0
    count = store.conn.execute('SELECT COUNT(*) FROM replay_events').fetchone()[0]
    assert count == 3


def test_invalid_bay_payload_does_not_advance_frame_or_persist(tmp_path):
    store = ReplayStore(tmp_path / 'events.db', {'chad-1': ['B08']})
    store.begin('chad-1')
    with pytest.raises(ValueError):
        store.publish('chad-1', 0, 0.0, [row('broken')])
    assert store.last_sequence == -1
    assert store.conn.execute('SELECT COUNT(*) FROM replay_events').fetchone()[0] == 0
    assert store.publish('chad-1', 0, 0.0, [row()])
    status = store.conn.execute('SELECT status FROM replay_sessions').fetchone()[0]
    assert status == 'playing'
