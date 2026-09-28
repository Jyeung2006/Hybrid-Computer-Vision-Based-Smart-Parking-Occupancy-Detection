"""Check the real popup against saved OpenCV-first replay without new inference."""
import json
from pathlib import Path
import sys
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from parking_probe.interface import ParkingInterface
from parking_probe.interface_model import window_text
from parking_probe.areas import area_reports
from parking_probe.config import atomic_json
from check_interface import capture_window

REPORT = ROOT / 'runs/verification/opencv-first/report.json'
OUT = ROOT / 'runs/verification/opencv-first/interface'


def main():
    run = Path(json.loads(REPORT.read_text(encoding='utf-8'))['replay_path'])
    OUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.geometry('1280x820')
    app = ParkingInterface(root, autostart=False)
    errors = []
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    checked = 0
    try:
        for path in run.glob('*/history.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                app.review.add_samples(json.loads(line))
        for path in run.glob('*/windows.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                app.review.add_windows([json.loads(line)])
        assert len(app.review.samples) == 8
        app.out = OUT
        app.ready = True
        assert app.primary_columns == ('bay', 'reference', 'mog2', 'vehicle', 'yolo', 'final')
        for clip in app.review.samples:
            app.selection.set(clip)
            app.select_clip(); app.pause(); root.update()
            pair = app.review.at(clip, 0)
            displayed = {row['bay_id']: row for row in app.displayed_rows.values()}
            assert len(displayed) == len(pair['rows'])
            for saved in pair['rows']:
                shown = displayed[saved['bay_id']]
                assert shown['state'] == saved['final_state']
                assert shown.get('vehicle_state') == saved.get('vehicle_state')
                assert shown.get('yolo_requested') == saved.get('yolo_requested')
                checked += 1
        app.selection.set('chad-4'); app.select_clip(); app.pause()
        app.seek(15); root.update()
        b08 = next(row for row in app.displayed_rows.values() if row['slot_id'] == 'B08')
        assert b08['state'] == 'vacant' and b08['final_confirmed_by'] == 'mobilenet_reviewed_empty'
        iid = next(iid for iid, row in app.displayed_rows.items() if row['slot_id'] == 'B08')
        app.table.selection_set(iid); app.table.see(iid); app.show_bay_details()
        assert 'MobileNet + reviewed empty appearance' in app.row_details.cget('text')
        app.pages.select(app.overview); root.update()
        capture_window(root, OUT / 'chad-b08.png')
        app.selection.set('overhead-1'); app.select_clip(); app.pause(); root.update()
        assert 'MobileNet' in window_text(app.review.windows['overhead-1'][0])
        assert 'YOLOv8' in window_text(app.review.windows['overhead-1'][0])
        assert 'Provisional Final' in window_text(app.review.windows['overhead-1'][0])
        reports = area_reports(app.review, {'chad': ('chad-4', 15), 'overhead': ('overhead-1', 0)})
        assert all('provisional_occupied' in area for area in reports)
        assert 'provisional occupied' in app.video_counts.cget('text')
        app.pages.select(app.watch); root.update(); app.update_recorded()
        assert app.photo is not None
        capture_window(root, OUT / 'overhead-video.png')
        assert not errors, errors
        atomic_json(OUT / 'result.json', {'saved_run': str(run), 'recordings': len(app.review.samples),
            'checked_first_sample_bays': checked, 'mobile_column': True,
            'chad4_b08_15': 'vacant_by_mobilenet_known_pedestrian_obstruction',
            'video_rendered': True, 'area_and_window_provisional_counts': True,
            'callback_errors': errors, 'no_new_inference': True})
        print('PASS: eight saved recordings, popup methods, sources, areas, windows and video.', flush=True)
    finally:
        app.close()


if __name__ == '__main__':
    main()
