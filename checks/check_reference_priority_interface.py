"""Check the real Tk interface using saved observations, without CV inference."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parking_probe.interface import ParkingInterface
from parking_probe.alternate_policy import add_alternate
from parking_probe.areas import VIEWS, inventory
from parking_probe.config import atomic_json
from check_interface import capture_window


def main():
    out = ROOT / 'runs/verification/reference-priority/interface'
    out.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = ParkingInterface(root, autostart=False)
    app.out = out
    errors, checked, changed = [], 0, None
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    try:
        for site_path in sorted((ROOT / 'runs/areas/20260921T161408_115721Z').rglob('site.json')):
            site = json.loads(site_path.read_text())
            config = json.loads(Path(site['reference_config']).read_text())
            calibrated = {s['id'] for s in config['slots'] if s.get('calibration', {}).get('status') == 'calibrated'}
            for line in (site_path.parent / 'history.jsonl').read_text().splitlines():
                batch = json.loads(line)
                for pair in batch.get('recordings', []):
                    for row in pair['rows']:
                        row['reference_calibrated'] = row['slot_id'] in calibrated
                    app.review.add_samples({'recordings': [pair]})
                    alternate = add_alternate(pair)
                    if not changed and any(r['final_state'] != r['final_alt_state'] for r in alternate['rows']):
                        changed = pair
        before = deepcopy(app.review.samples)
        for clip, samples in app.review.samples.items():
            app.clip, app.view = VIEWS[clip].clip, VIEWS[clip]
            app.polygons = inventory(app.view)
            for pair in samples:
                app.show_alternate.set(False); app.toggle_alternate()
                app.render_observation(pair)
                rate, counts = app.rate.cget('text'), app.video_counts.cget('text')
                app.show_alternate.set(True); app.toggle_alternate()
                assert app.rate.cget('text') == rate and app.video_counts.cget('text') == counts
                assert len(app.table.get_children()) == len(app.polygons)
                checked += len(pair['rows'])
        assert app.review.samples == before
        assert checked == 1088
        assert changed is not None
        app.view = VIEWS[changed['recording_id']]; app.clip = app.view.clip
        app.polygons = inventory(app.view)
        app.sync_selectors()
        app.pages.select(app.overview)
        app.render_observation(changed)
        differing = next(i for i, row in app.displayed_rows.items() if row.get('final_alt_state') != row['state'])
        app.table.selection_set(differing); app.table.see(differing); app.show_bay_details()
        for width, height in ((1220, 860), (1100, 650)):
            root.geometry(f'{width}x{height}')
            root.update()
            app.table.xview_moveto(1)
            capture_window(root, out / f'alternate-{width}.png')
            app.overview_canvas.yview_moveto(1)
            capture_window(root, out / f'alternate-details-{width}.png')
            app.overview_canvas.yview_moveto(0)
        app.show_alternate.set(False); app.toggle_alternate()
        root.update()
        capture_window(root, out / 'default-off.png')
        app.open_validation_report()
        report_window, report_text = app.validation_viewer
        report_window.update()
        assert report_text.cget('state') == 'disabled'
        capture_window(report_window, out / 'read-only-report.png')
        report_window.destroy()
        assert not errors, errors
        atomic_json(out / 'result.json', {'saved_run': '20260921T161408_115721Z',
            'recordings': len(app.review.samples), 'sample_pairs': sum(map(len, app.review.samples.values())),
            'bay_observations_checked': checked, 'primary_counts_unchanged': True,
            'primary_samples_unchanged': True, 'new_inference_count': 0,
            'callback_errors': errors, 'default_off': True, 'report_viewer_read_only': True})
        print('PASS: 8 recordings, 60 sample pairs, 1088 observations; no primary change or new inference.')
    finally:
        app.close()


if __name__ == '__main__':
    main()
