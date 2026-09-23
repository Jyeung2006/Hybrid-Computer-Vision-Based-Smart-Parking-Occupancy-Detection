"""Exercise the actual chart/video GUI with saved guarded results, without new inference."""
import json
from pathlib import Path
import sys
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from parking_probe.areas import VIEWS
from parking_probe.interface import ParkingInterface
from parking_probe.config import atomic_json
from check_interface import capture_window

RUN = ROOT/'runs/areas/20260923T114108_587187Z'
OUT = ROOT/'runs/verification/guarded-vacancy-interface'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root=tk.Tk()
    root.geometry('1280x820')
    app=ParkingInterface(root,autostart=False)
    errors=[]
    root.report_callback_exception=lambda kind,value,tb: errors.append(str(value))
    try:
        for path in RUN.glob('*/history.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                batch=json.loads(line)
                if batch.get('recordings'):
                    app.review.add_samples(batch)
        for path in RUN.glob('*/windows.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                app.review.add_windows([json.loads(line)])
        assert len(app.review.samples)==8
        app.out=OUT
        app.ready=True
        app.selection.set('overhead-1')
        app.select_clip(); app.pause()
        app.pages.select(app.overview)
        root.update()
        bay='OVER-EL11'
        def displayed():
            row=next(r for r in app.displayed_rows.values() if r['bay_id']==bay)
            return row['state'],row.get('vacancy_guard_streak'),row.get('final_provisional')
        assert displayed()[:2]==('uncertain',1)
        app.position=3;app.update_recorded();root.update()
        assert displayed()[:2]==('uncertain',2)
        app.position=6;app.update_recorded();root.update()
        assert displayed()[:2]==('vacant',3)
        assert any('VACANT' in str(app.table.item(i)['values'][-1]) for i,r in app.displayed_rows.items() if r['bay_id']==bay)
        assert 'provisional vacant' in app.video_counts.cget('text')
        capture_window(root,OUT/'guarded-overview.png')
        app.pages.select(app.watch);root.update();app.update_recorded()
        assert app.photo is not None
        capture_window(root,OUT/'guarded-video.png')
        app.seek(6);root.update()
        assert displayed()[:2]==('uncertain',1)
        assert app.last_displayed_pair['final']['summary']['vacant'] == app.review.at('overhead-1',6)['final']['summary']['vacant']-6
        app.pages.select(app.overview);root.update()
        capture_window(root,OUT/'after-seek.png')
        assert not errors,errors
        report={'saved_run':str(RUN),'recordings':len(app.review.samples),
                'sample_pairs':sum(len(v) for v in app.review.samples.values()),
                'no_new_inference':True,'guarded_at_0_3_6':['uncertain','uncertain','vacant'],
                'same_time_after_seek':'uncertain','callback_errors':errors}
        atomic_json(OUT/'result.json',report)
        print('PASS: GUI chart/table/video and seek reset using eight saved recordings.',flush=True)
    finally:
        app.close()


if __name__=='__main__':
    main()
