"""Real yolo-camera UI check. Captures only this test's own window."""
import ctypes
from ctypes import wintypes as wt
import json
from pathlib import Path
import sys
import time
import tkinter as tk

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from parking_probe.interface import ParkingInterface
from parking_probe.interface_model import chart_data
from parking_probe.catalog import CLIPS, PROJECT_ROOT
from parking_probe.areas import VIEWS, inventory, area_reports


def capture_window(root, path):
    """PrintWindow on our HWND, without reading any other application surface."""
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.GetAncestor.argtypes, user.GetAncestor.restype = [wt.HWND, wt.UINT], wt.HWND
    user.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user.GetWindowDC.argtypes, user.GetWindowDC.restype = [wt.HWND], wt.HDC
    user.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
    user.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    gdi.CreateCompatibleDC.argtypes, gdi.CreateCompatibleDC.restype = [wt.HDC], wt.HDC
    gdi.CreateCompatibleBitmap.argtypes, gdi.CreateCompatibleBitmap.restype = [wt.HDC, ctypes.c_int, ctypes.c_int], wt.HBITMAP
    gdi.SelectObject.argtypes, gdi.SelectObject.restype = [wt.HDC, wt.HANDLE], wt.HANDLE
    gdi.DeleteObject.argtypes = [wt.HANDLE]
    gdi.DeleteDC.argtypes = [wt.HDC]
    gdi.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
    root.update()
    hwnd = user.GetAncestor(root.winfo_id(), 2)
    rect = wt.RECT()
    user.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right-rect.left, rect.bottom-rect.top
    source = user.GetWindowDC(hwnd)
    dc = gdi.CreateCompatibleDC(source)
    bitmap = gdi.CreateCompatibleBitmap(source, width, height)
    old = gdi.SelectObject(dc, bitmap)
    try:
        if not user.PrintWindow(hwnd, dc, 2):
            raise RuntimeError("Own-window screenshot failed")
        gdi.SelectObject(dc, old)
        header = ctypes.create_string_buffer(40)
        import struct
        header.raw = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        pixels = ctypes.create_string_buffer(width*height*4)
        if not gdi.GetDIBits(dc, bitmap, 0, height, pixels, header, 0):
            raise RuntimeError("Own-window bitmap read failed")
        image = np.frombuffer(pixels, np.uint8).reshape(height, width, 4)[:, :, :3]
        if not cv2.imwrite(str(path), image):
            raise RuntimeError("Screenshot save failed")
    finally:
        gdi.SelectObject(dc, old)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(dc)
        user.ReleaseDC(hwnd, source)


def main():
    out = PROJECT_ROOT / "runs/verification"
    out.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = ParkingInterface(root, autostart=False)
    errors = []
    root.report_callback_exception = lambda kind, value, tb: errors.append(kind.__name__)
    started = time.monotonic()
    try:
        app.prepare()
        while not app.ready and time.monotonic()-started < 600:
            root.update()
            time.sleep(.02)
            if app.worker and not app.worker.is_alive() and app.events.empty() and not app.ready:
                raise AssertionError(app.status.cget("text"))
        assert app.ready, "Preparation did not finish"
        preparation_seconds = time.monotonic()-started
        results = {}
        for clip in CLIPS:
            app.selection.set(clip.id)
            app.select_clip()
            app.pause()
            app.seek(app.duration)
            rows, s = chart_data(app.review.at(clip.id, app.position), [b['bay_id'] for b in inventory(VIEWS[clip.id])])
            assert s["occupied"] >= 2 and s["total_monitored_bays"] == 9
            near = next(r for r in rows if r['bay_id'] == 'CHAD-P009')
            assert near['yolo_state'] == near['state'] == 'occupied'
            assert near['reference_state'] == near['mog2_state'] == 'unknown'
            assert "summary" in app.window_label.cget("text").lower() or "window" in app.window_label.cget("text").lower()
            app.pages.select(app.watch)
            root.update()
            app.update_recorded()
            assert app.photo is not None
            results[clip.id] = s
            # Seeking backwards must reset both observations and completed windows.
            app.seek(0)
            assert app.review.at(clip.id, app.position)["reference"]["sample_time_seconds"] == 0
            assert "appears" in app.window_label.cget("text")
        for key in ('chad-camera-2','chad-camera-3','chad-camera-4','overhead-1'):
            app.selection.set(key)
            app.select_clip()
            app.pause()
            app.pages.select(app.watch)
            root.update()
            app.update_recorded()
            assert app.photo is not None
            if key != 'overhead-1':
                rows,s = chart_data(app.review.at(key,app.position),[b['bay_id'] for b in app.polygons])
                assert len(rows) == {'chad-camera-2':5,'chad-camera-3':4,'chad-camera-4':3}[key]
                assert next(r for r in rows if r['bay_id']=='CHAD-P009')['state'] == 'occupied'
                assert app.rate.cget('text') != 'Unavailable'
                assert 'YOLOv8' in app.table.heading('yolo')['text']
                results[key] = s
                capture_window(root, out / f'yolo-{key}.png')
        app.seek(12)
        _, overhead = chart_data(app.review.at('overhead-1',12), [b['bay_id'] for b in app.polygons])
        assert overhead['total_monitored_bays']==69 and overhead['occupied']>=40
        assert len(app.table.get_children())==69
        capture_window(root, out / 'yolo-overhead.png')
        app.seek(18)
        assert app.rate.cget('text') != 'Unavailable'
        app.seek(app.duration)
        _, results['overhead-1'] = chart_data(app.review.at('overhead-1',app.position),[b['bay_id'] for b in app.polygons])
        app.pages.select(app.overview)
        root.update()
        capture_window(root,out/'yolo-overhead-overview.png')
        app.table.yview_moveto(1)
        capture_window(root,out/'yolo-overhead-last-bays.png')
        app.pages.select(app.summaries)
        root.update()
        capture_window(root,out/'yolo-overhead-summary.png')
        app.pages.select(app.areas_page)
        root.update()
        capture_window(root,out/'yolo-overhead-areas.png')
        app.selection.set("chad-1")
        app.select_clip()
        app.pause()
        app.seek(27)
        app.pages.select(app.overview)
        root.update()
        capture_window(root, out / "yolo-overview.png")
        app.table.yview_moveto(1)
        root.update()
        app.table.selection_set(app.table.get_children()[-1])
        app.show_bay_details()
        capture_window(root, out / 'yolo-near-row.png')
        app.pages.select(app.watch)
        root.update()
        app.update_recorded()
        capture_window(root, out / "yolo-watch.png")
        app.pages.select(app.summaries)
        root.update()
        capture_window(root, out / 'yolo-summary.png')
        app.pages.select(app.areas_page)
        root.update()
        capture_window(root, out / 'yolo-areas.png')
        assert len(app.area_table.get_children()) == 5
        app.toggle_play()
        old = app.position
        deadline = time.monotonic()+.5
        while time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert app.position > old
        app.pause()
        app.tabs.select(app.live)
        root.update()
        assert not app.playing
        capture_window(root, out / "yolo-live.png")
        from parking_probe.yolo import needs_verification
        for samples in app.review.samples.values():
            for observation in samples:
                for row in observation['rows']:
                    expected=needs_verification(row['reference_state'],row['mog2_state'])
                    assert row['yolo_requested']==expected
                    if not expected:
                        assert row['final_state']==row['reference_state']
        assert not errors, errors
        report = {"analysis_directory": str(app.out), "preparation_seconds": preparation_seconds,
                  "samples_by_recording": {k: len(v) for k,v in app.review.samples.items()},
                  "final_summaries": results, "callback_errors": errors,
                  "overhead_at_12_seconds": overhead, "source_issues": app.source_errors,
                  "areas": area_reports(app.review, app.area_selections),
                  "verified": ["two sites", "four mapped CHAD camera views", "nine-bay CHAD inventory", "selective YOLOv8 and final states", "all eight video decoders",
                               "forward and backward seek", "window reset", "pause and resume", "live tab pauses review", "69 overhead bays and guarded drift correction"],
                  "live_external_camera_tested": False}
        (out / "interface-yolo-check.json").write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps(report, indent=2))
    finally:
        app.close()


if __name__ == "__main__":
    main()
