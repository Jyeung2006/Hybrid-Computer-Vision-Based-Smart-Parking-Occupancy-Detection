"""Local Tkinter occupancy chart, recorded video review and authorized live viewer.

Recordings are analyzed chronologically in a worker before review starts. Seeking
only selects saved observations; it never feeds out-of-order frames into MOG2.
Tk widgets and the local recording decoder belong to the UI thread. Network input
uses the existing bounded CameraSource worker and a latest-frame queue.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

import cv2
import numpy as np

from .catalog import CLIPS, PROJECT_ROOT
from .comparison import run_comparison
from .alternate_policy import add_alternate, export_alternate_review
from .config import Config, atomic_json
from .areas import SITES, VIEWS, EXTRA_VIEWS, OVERHEAD, OVERHEAD_MAP, fetch_view, fetch_overhead, inventory, area_reports
from .monitor import prepare_preset
from .view_presets import prepare_view
from .yolo import YOLODetector, VerificationService
from .vehicle import VehicleDetector, prepare_model as prepare_mobilenet
from .display_model import occupancy_text, video_clock, local_time
from .documentation import MANUAL_NAME, read_document
from .interface_model import Review, PlaybackGuard, STATES, chart_data, ring_segments, window_text
from .sources import CameraSource, SourceError, utcnow

BG = "#eef3f8"
INK = "#192b43"
MUTED = "#607087"
ACCENT = "#2459d3"
COLORS = {"occupied": "#e25467", "vacant": "#22a686", "uncertain": "#e2a12f", "unknown": "#98a6b8"}


def png_photo(image, width, height):
    h, w = image.shape[:2]
    scale = min(max(1, width) / w, max(1, height) / h)
    resized = cv2.resize(image, (max(1, round(w*scale)), max(1, round(h*scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".png", resized)
    if not ok:
        raise SourceError("preview_encode_failed")
    return tk.PhotoImage(data=base64.b64encode(encoded.tobytes()))


class LocalPlayer:
    """A local-file decoder only; arbitrary network URLs never enter this class."""
    def __init__(self, path, resolution=(1920, 1080), stabilization=None):
        self.resolution = resolution
        self.cap = cv2.VideoCapture(str(Path(path)))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.next_index = 0
        if not self.cap.isOpened() or not math.isfinite(self.fps) or self.fps <= 0 or self.count < 1:
            self.close()
            raise SourceError("recorded_video_open_failed")
        self.duration = self.count / self.fps
        self.stabilizer = None
        if stabilization:
            from .registration import FrameRegistration
            self.stabilizer = FrameRegistration(self.image_at(0), stabilization)

    def image_at(self, position):
        index = min(self.count - 1, max(0, int(position * self.fps)))
        if index < self.next_index or index - self.next_index > 12:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        else:
            for _ in range(index - self.next_index):
                if not self.cap.grab():
                    raise SourceError("recorded_video_decode_failed")
        ok, image = self.cap.read()
        if not ok or image is None:
            raise SourceError("recorded_video_decode_failed")
        self.next_index = index + 1
        if (image.shape[1], image.shape[0]) != tuple(self.resolution):
            raise SourceError("recorded_video_resolution_changed")
        if self.stabilizer:
            image, _ = self.stabilizer.apply(image)
        return image

    def close(self):
        self.cap.release()


def put_latest(channel, event):
    try:
        channel.put_nowait(event)
    except queue.Full:
        try:
            channel.get_nowait()
        except queue.Empty:
            pass
        channel.put_nowait(event)


def live_worker(config_path, stop, channel, generation):
    """No URLs, headers, credentials or raw provider errors are emitted."""
    camera = None
    try:
        config = Config(config_path)
        camera = CameraSource(config.data["source"])
        interval = config.data.get("interval_seconds", 3) if camera.kind == "snapshot" else .1
        stale = config.data.get("stale_after_seconds", 15)
        while not stop.is_set():
            frame = camera.read()
            if stop.is_set():
                break
            age = (utcnow() - frame.captured_at).total_seconds() if frame.captured_at else None
            if age is not None and (age > stale or age < -5):
                raise SourceError("source_capture_time_stale_or_invalid")
            # Bound memory/queue size even for high-resolution cameras.
            h, w = frame.image.shape[:2]
            scale = min(960 / w, 540 / h)
            image = cv2.resize(frame.image, (max(1, round(w * scale)), max(1, round(h * scale))))
            put_latest(channel, (generation, "frame", (image, frame.received_at, frame.captured_at, time.monotonic(), stale)))
            if stop.wait(interval):
                break
    except SourceError as exc:
        put_latest(channel, (generation, "error", str(exc)))
    except Exception:
        put_latest(channel, (generation, "error", "camera_configuration_or_connection_failed"))
    finally:
        if camera is not None:
            camera.close()


class ParkingInterface:
    def __init__(self, root, interval=3.0, start_video="chad-1", autostart=True):
        self.root, self.interval = root, interval
        self.review = Review()
        self.playback_guard = PlaybackGuard()
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.live_events = queue.Queue(maxsize=2)
        self.live_stop = threading.Event()
        self.live_thread = None
        self.live_generation = 0
        self.live_deadline = None
        self.live_photo = None
        self.closed = self.ready = self.playing = False
        self.player = None
        self.photo = None
        self.position = 0.0
        self.anchor = 0.0
        self.duration = 0.0
        self.render_key = None
        self.picture_key = None
        self.out = None
        self.last_displayed_pair = None
        self.show_alternate = tk.BooleanVar(master=root, value=False)
        self.clip = VIEWS[start_video].clip
        self.view = VIEWS[start_video]
        self.polygons = inventory(self.view)
        self.area_selections = {}
        self.source_errors = []
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.timer = root.after(60, self.tick)
        if autostart:
            root.after(150, self.prepare)

    def label(self, parent, text="", size=11, color=INK, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def _build(self):
        root = self.root
        root.title("Parking Observatory | OpenCV")
        root.geometry(f"{min(1220, root.winfo_screenwidth()-60)}x{min(860, root.winfo_screenheight()-65)}")
        root.minsize(1100, 650)
        root.configure(bg=BG)
        menu = tk.Menu(root)
        reports = tk.Menu(menu, tearoff=False)
        reports.add_command(label='View external validation report', command=self.open_validation_report)
        menu.add_cascade(label='Reports', menu=reports)
        root.configure(menu=menu)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 5), background="white", foreground=INK)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(18, 6), background="#dfe7f1")
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", ACCENT)])
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=6, background="#edf3fa")

        header = tk.Frame(root, bg="#142840", padx=20, pady=10)
        header.pack(fill="x")
        self.label(header, "PARKING OBSERVATORY", 17, "white", True).pack(anchor="w")
        self.label(header, "OpenCV experiment  /  Reference + MOG2 + MobileNet → selective YOLOv8s  /  Every 3 video seconds",
                   10, "#bacadd").pack(anchor="w", pady=(4, 0))
        self.tabs = ttk.Notebook(root)
        # Reserve the status bar before the expanding notebooks.
        bottom = tk.Frame(root, bg=BG, padx=18, pady=5)
        bottom.pack(side="bottom", fill="x")
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(8, 4))
        self.recorded = tk.Frame(self.tabs, bg=BG)
        self.live = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(self.recorded, text="Recorded parking")
        self.tabs.add(self.live, text="Live camera")
        self.tabs.bind("<<NotebookTabChanged>>", self.tab_changed)

        toolbar = tk.Frame(self.recorded, bg=BG, pady=5)
        toolbar.pack(fill="x")
        self.selection = tk.StringVar(value=self.clip.id)
        self.site_selection = tk.StringVar(value=SITES[self.view.site])
        self.camera_selection = tk.StringVar(value=self.view.camera)
        self.recording_selection = tk.StringVar(value=self.view.label)
        for title, variable, width, callback, attribute in (
            ("SITE", self.site_selection, 24, self.site_changed, "site_combo"),
            ("VIEW", self.camera_selection, 18, self.camera_changed, "camera_combo"),
            ("RECORDING", self.recording_selection, 18, self.recording_changed, "recording_combo")):
            self.label(toolbar, title, 9, MUTED, True).pack(side="left", padx=(5, 6))
            combo = ttk.Combobox(toolbar, textvariable=variable, state="readonly", width=width)
            combo.pack(side="left", padx=(0, 9))
            combo.bind("<<ComboboxSelected>>", callback)
            setattr(self, attribute, combo)
        self.site_combo.configure(values=list(SITES.values()))
        self.sync_selectors()
        self.results_button = ttk.Button(toolbar, text="Open saved results", command=self.open_results, state="disabled")
        self.results_button.pack(side="right")

        playback_footer = tk.Frame(self.recorded, bg=BG)
        playback_footer.pack(side="bottom", fill="x")
        self.pages = ttk.Notebook(self.recorded)
        self.pages.pack(fill="both", expand=True)
        self.overview = tk.Frame(self.pages, bg="white", padx=15, pady=6)
        self.watch = tk.Frame(self.pages, bg="#101d2e")
        self.summaries = tk.Frame(self.pages, bg="white", padx=24, pady=12)
        self.areas_page = tk.Frame(self.pages, bg="white", padx=16, pady=8)
        self.pages.add(self.areas_page, text="Areas & availability")
        self.pages.add(self.overview, text="Occupancy overview")
        self.pages.add(self.watch, text="Watch video")
        self.pages.add(self.summaries, text="10-second summaries")
        self.pages.bind("<<NotebookTabChanged>>", lambda e: self.invalidate_picture())
        tk.Checkbutton(self.overview, text='Show alternate: Reference priority (experimental)',
            variable=self.show_alternate, command=self.toggle_alternate, bg='white', fg='#7039a8',
            activebackground='white', font=('Segoe UI', 10)).pack(anchor='w')
        overview_scroll = ttk.Scrollbar(self.overview, orient='vertical')
        overview_scroll.pack(side='right', fill='y')
        self.overview_canvas = tk.Canvas(self.overview, bg='white', highlightthickness=0,
                                        yscrollcommand=overview_scroll.set)
        self.overview_canvas.pack(fill='both', expand=True)
        overview_scroll.configure(command=self.overview_canvas.yview)
        body = tk.Frame(self.overview_canvas, bg="white")
        body_window = self.overview_canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: self.overview_canvas.configure(scrollregion=self.overview_canvas.bbox('all')))
        self.overview_canvas.bind('<Configure>', lambda e: self.overview_canvas.itemconfigure(body_window, width=e.width))
        left = tk.Frame(body, bg="white", width=345)
        left.pack(side="left", fill="y", padx=(0, 20))
        self.label(left, "MONITORED BAY OCCUPANCY", 11, MUTED, True).pack(anchor="w", pady=(4, 0))
        self.chart = tk.Canvas(left, width=280, height=210, bg="white", highlightthickness=0)
        self.chart.pack()
        self.rate = self.label(left, "Preparing observations…", 15, INK, True)
        self.rate.pack()

        right = tk.Frame(body, bg="white")
        right.pack(side="left", fill="both", expand=True)
        self.label(right, "BAY DECISIONS", 11, MUTED, True).pack(anchor="w", pady=(4, 10))
        table_frame = tk.Frame(right, bg="white")
        table_frame.pack(fill="x")
        table_frame.columnconfigure(0, weight=1)
        self.primary_columns = ('bay', 'reference', 'mog2', 'vehicle', 'yolo', 'final')
        self.table = ttk.Treeview(table_frame, columns=(*self.primary_columns, 'final_alt', 'alt_basis'),
            displaycolumns=self.primary_columns, show="headings", height=3)
        for col, title, width in (("bay", "Bay ID", 115), ("reference", "Reference", 95),
                                  ("mog2", "MOG2", 95), ("vehicle", "MobileNet + empty", 130),
                                  ("yolo", "YOLOv8", 95), ("final", "Final estimate", 110),
                                  ('final_alt', 'EXP: Alternate', 150), ('alt_basis', 'EXP: Confirmed by', 225)):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, minwidth=85, anchor="center", stretch=True)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.configure(xscrollcommand=horizontal.set)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.grid(row=0, column=0, sticky='ew')
        self.alternate_note = self.label(right, '', 9, '#7039a8', justify='left', anchor='w', wraplength=640)
        self.alternate_note.pack(fill='x')
        for state in STATES:
            self.table.tag_configure(state, foreground={"vacant": "#087b61", "occupied": "#b33149", "uncertain": "#956412", "unknown": MUTED}[state])
        self.table.tag_configure('provisional', foreground='#956412')
        self.row_details = self.label(right, "Select a bay to see its method results and Final source.\nYOLOv8 runs only for unresolved bays or Reference/MOG2 conflicts.",
                                     9, MUTED, justify="left", anchor="w", wraplength=650)
        self.row_details.pack(fill="x", pady=4)
        self.table.bind('<<TreeviewSelect>>', self.show_bay_details)
        self.displayed_rows = {}
        self.legend = {}
        legend = tk.Frame(right, bg="white")
        legend.pack(pady=2, fill="x")
        for index, state in enumerate(STATES):
            item = tk.Frame(legend, bg="white")
            item.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 30), pady=0)
            self.label(item, "●", 11, COLORS[state]).pack(side="left", padx=(0, 6))
            value = self.label(item, f"0 {state}", 10)
            value.pack(side="left")
            self.legend[state] = value
        self.scope_label = self.label(right, "", 9, MUTED, justify="left")
        self.scope_label.pack(anchor="w")
        self.label(self.summaries, "COMPLETED VIDEO WINDOW", 11, MUTED, True).pack(anchor="w", pady=(0, 12))
        summary_canvas = tk.Canvas(self.summaries, bg='white', highlightthickness=0)
        summary_scroll = ttk.Scrollbar(self.summaries, orient='vertical', command=summary_canvas.yview)
        summary_scroll.pack(side='right', fill='y')
        summary_canvas.pack(fill='both', expand=True)
        summary_canvas.configure(yscrollcommand=summary_scroll.set)
        self.window_label = self.label(summary_canvas, "The first 10-second summary appears at video 00:10.", 10, INK,
                                      justify="left", anchor="nw")
        summary_canvas.create_window((0,0), window=self.window_label, anchor='nw')
        self.window_label.bind('<Configure>', lambda e: summary_canvas.configure(scrollregion=summary_canvas.bbox('all')))
        self.label(self.areas_page, "VACANCY BY AREA", 12, INK, True).pack(anchor="w")
        self.label(self.areas_page, "Overhead: all 69 visible bays. CHAD: mapped subsets. Unresolved bays are not free. Double-click to view.",
                   10, MUTED).pack(anchor="w", pady=(3, 6))
        columns = ("area", "vacant", "occupied", "unresolved", "total", "basis")
        self.area_table = ttk.Treeview(self.areas_page, columns=columns, show="headings", height=5)
        for col, title, width in zip(columns, ("Area", "Vacant", "Occupied", "Unresolved", "Mapped bays", "Recording / sample time"),
                                     (215, 80, 80, 95, 95, 235), strict=True):
            self.area_table.heading(col, text=title)
            self.area_table.column(col, width=width, anchor="w" if col in ("area", "basis") else "center")
        self.area_table.pack(fill="x", pady=4)
        self.area_table.bind("<Double-1>", self.open_area)
        self.label(self.areas_page, "P = provisional estimate (occupied or vacant); see the Final source. Separate recording times are not fused as live availability.",
                   9, MUTED, justify="left").pack(anchor="w", pady=3)

        self.video_label = tk.Label(self.watch, bg="#101d2e", fg="#d2e0ee", text="Preparing the recordings…",
                                    font=("Segoe UI", 13))
        self.video_label.pack(fill="both", expand=True)
        self.video_counts = tk.Label(self.watch, bg="#142840", fg="white", font=("Segoe UI", 11), pady=9)
        self.video_counts.pack(side="bottom", fill="x", before=self.video_label)

        controls = tk.Frame(playback_footer, bg=BG, pady=5)
        controls.pack(fill="x")
        self.play_button = ttk.Button(controls, text="Play", command=self.toggle_play, state="disabled")
        self.play_button.pack(side="left")
        self.replay_button = ttk.Button(controls, text="Replay", command=self.replay, state="disabled")
        self.replay_button.pack(side="left", padx=7)
        self.seek_var = tk.DoubleVar(value=0)
        self.scrubber = ttk.Scale(controls, from_=0, to=33, variable=self.seek_var, command=self.seek, state="disabled")
        self.scrubber.pack(side="left", fill="x", expand=True, padx=12)
        self.clock_label = self.label(controls, "00:00 / 00:00", 11, INK, True, width=14)
        self.clock_label.pack(side="right")
        self.sample_label = self.label(playback_footer, "No observations yet.", 9, MUTED, anchor="w", justify="left")
        self.sample_label.pack(fill="x")
        self.label(playback_footer, "RECORDED REVIEW · Site, camera view and recording are separate. Overlapping views never create extra bays.",
                   9, MUTED, anchor="w").pack(fill="x", pady=(2, 0))

        self._build_live()
        self.status = self.label(bottom, "Ready to prepare the recordings.", 9, MUTED, anchor="w", wraplength=900)
        self.status.pack(side="left", fill="x", expand=True)
        self.prepare_button = ttk.Button(bottom, text="Prepare recordings", command=self.prepare)
        self.prepare_button.pack(side="right", padx=(12, 0))
        self.render_observation(None)
        self.render_areas()

    def sync_selectors(self):
        self.site_selection.set(SITES[self.view.site])
        cameras = list(dict.fromkeys(v.camera for v in VIEWS.values() if v.site == self.view.site))
        self.camera_combo.configure(values=cameras)
        self.camera_selection.set(self.view.camera)
        options = [v.label for v in VIEWS.values() if v.site == self.view.site and v.camera == self.view.camera]
        self.recording_combo.configure(values=options)
        self.recording_selection.set(self.view.label)

    def site_changed(self, event=None):
        site = next(k for k,v in SITES.items() if v == self.site_selection.get())
        self.selection.set(next(k for k,v in VIEWS.items() if v.site == site))
        self.select_clip()

    def camera_changed(self, event=None):
        self.selection.set(next(k for k,v in VIEWS.items() if v.site == self.view.site and v.camera == self.camera_selection.get()))
        self.select_clip()

    def recording_changed(self, event=None):
        self.selection.set(next(k for k,v in VIEWS.items() if v.site == self.view.site and v.camera == self.view.camera and v.label == self.recording_selection.get()))
        self.select_clip()

    def open_area(self, event=None):
        chosen = self.area_table.selection()
        if chosen:
            site = "chad" if chosen[0].startswith("chad-") else "overhead"
            clip, position = self.area_selections.get(site, ("chad-1" if site == "chad" else "overhead-1", 0))
            self.selection.set(clip)
            self.select_clip()
            self.seek(position)
            self.pages.select(self.watch)

    def render_areas(self):
        overrides = {self.clip.id: self.last_displayed_pair} if self.last_displayed_pair and self.area_selections.get(self.view.site, (None,))[0] == self.clip.id else {}
        reports = area_reports(self.review, self.area_selections, overrides)
        for iid in self.area_table.get_children():
            self.area_table.delete(iid)
        for r in reports:
            sample = "no usable observation" if r['sample_seconds'] is None else f"{r['sample_seconds']:.0f}s"
            counts = (f"{r['vacant']} (P:{r['provisional_vacant']})",
                      f"{r['occupied']} (P:{r['provisional_occupied']})") if r['available'] else ("—", "—")
            self.area_table.insert("", "end", iid=r['area_id'], values=(r['area_name'], *counts, r['unresolved'],
                r['total_monitored_bays'], f"{VIEWS[r['recording_id']].label} / {sample}"))
        if self.ready and self.out:
            value = {"basis": "independent_recorded_periods", "live_availability": False, "areas": reports}
            try:
                atomic_json(self.out / "area-summary.json", value)
            except OSError:
                self.status.configure(text="Area summary could not be saved; displayed results remain experimental recorded observations.")

    def _build_live(self):
        panel = tk.Frame(self.live, bg=BG, padx=12, pady=16)
        panel.pack(fill="x")
        self.label(panel, "Watch an authorized camera", 20, INK, True).pack(anchor="w")
        self.label(panel, "No live camera is configured by this demo. Connect your own authorized image or direct stream endpoint.\n"
                   "This tab is a viewer only. CHAD polygons and occupancy results do not apply to a different camera.",
                   11, MUTED, justify="left").pack(anchor="w", pady=10)
        bar = tk.Frame(panel, bg=BG)
        bar.pack(fill="x")
        self.live_config = tk.StringVar(value=str(PROJECT_ROOT / "config.local.json"))
        ttk.Entry(bar, textvariable=self.live_config).pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="Browse config", command=self.browse_config).pack(side="left", padx=7)
        self.connect_button = ttk.Button(bar, text="Connect", command=self.connect_live)
        self.connect_button.pack(side="left")
        ttk.Button(bar, text="Disconnect", command=self.disconnect_live).pack(side="left", padx=7)
        self.label(panel, "Set PARKING_CAMERA_URL in the launching terminal; source.type is snapshot or stream in config.local.json.\n"
                   "Snapshot refresh uses the configured interval (3s by default). See PROJECT_DOCUMENTATION.md#doc-interface for the short live setup.",
                   10, MUTED, justify="left").pack(anchor="w", pady=(10, 0))
        self.live_status = self.label(self.live, "Live occupancy unavailable until this camera has its own bay setup and calibration.",
                                      10, MUTED, justify="left", anchor="w", wraplength=1050)
        self.live_status.pack(side="bottom", fill="x", padx=12, pady=8)
        self.live_label = tk.Label(self.live, bg="#101d2e", fg="white", text="Live camera disconnected",
                                   font=("Segoe UI", 15))
        self.live_label.pack(fill="both", expand=True, padx=12)

    def prepare(self):
        if self.worker and self.worker.is_alive():
            return
        self.pause()
        self.ready = False
        self.review = Review()
        self.playback_guard.reset()
        self.area_selections = {}
        self.source_errors = []
        self.stop = threading.Event()
        self.render_key = None
        self.render_observation(None)
        self.window_label.configure(text="Preparing the 10-second summaries…")
        self.video_label.configure(image="", text="Analyzing recordings before playback…")
        self.photo = None
        for widget in (self.play_button, self.replay_button, self.scrubber, self.prepare_button, self.results_button):
            widget.configure(state="disabled")
        self.render_areas()
        self.status.configure(text="Preparing all mapped views, MobileNet, selective YOLOv8s and 69 overhead bays…")
        self.out = PROJECT_ROOT / "runs/areas" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")

        def work():
            issues = []
            detector = None
            mobilenet = None
            try:
                self.events.put(("status", "Loading the local MobileNet-SSD model…"))
                mobilenet = VehicleDetector(prepare_mobilenet(
                    lambda k,v: self.events.put((k,v)), self.stop.is_set))
            except Exception:
                issues.append("MobileNet-SSD unavailable; its branch will show unknown.")
            try:
                self.events.put(("status", "Loading the local YOLOv8s models…"))
                detector = YOLODetector()
            except Exception:
                issues.append("YOLOv8s model unavailable; unresolved bays cannot be verified. See PROJECT_DOCUMENTATION.md#doc-yolov8.")
            service = VerificationService(detector)
            self.verification_service = service
            for view in [VIEWS['chad-1'], *(VIEWS[c.id] for c in EXTRA_VIEWS)]:
                if self.stop.is_set():
                    service.close()
                    return
                try:
                    prepared = prepare_view(view, lambda k,v: self.events.put((k,v)), self.stop, include_empty_evidence=True)
                    clips = CLIPS if view.camera == 'Camera 1' else [view.clip]
                    mapping = {s['id']:s['bay_id'] for s in inventory(view)}
                    code = run_comparison(clips, self.interval, self.stop, lambda k,v: self.events.put((k,v)), fast=True,
                        out=self.out / ('chad' if view.camera == 'Camera 1' else view.clip.id),
                        prepared=prepared, bay_map=mapping, verification=True, service=service,
                        detector=mobilenet, opencv_first=True)
                    if code:
                        issues.append(f"{view.camera} processing reported unavailable samples.")
                except Exception:
                    issues.append(f"{view.camera} calibration/analysis unavailable; inspect its saved reports.")
            if self.stop.is_set():
                service.close()
                return
            try:
                prepared = prepare_preset(lambda k,v: self.events.put((k,v)), self.stop,
                    PROJECT_ROOT / "presets/overhead-all-bays.json", [OVERHEAD], fetch_overhead, PROJECT_ROOT / "data/overhead-all")
                code = run_comparison([OVERHEAD], self.interval, self.stop, lambda k,v: self.events.put((k,v)), fast=True,
                    out=self.out / "overhead", prepared=prepared, bay_map={s['id']:s['bay_id'] for s in inventory(VIEWS['overhead-1'])},
                    verification=True, service=service, verification_profile='aerial',
                    detector=mobilenet, opencv_first=True)
                if code:
                    issues.append("Overhead processing reported unavailable samples.")
            except Exception:
                issues.append("Overhead calibration/analysis unavailable; video remains viewable if downloaded.")
            service.close()
            if not self.stop.is_set():
                try:
                    atomic_json(self.out / "source-status.json", {"issues": issues, "external_live_source": False})
                    atomic_json(self.out / "bay-inventory.json", {k: inventory(v) for k,v in VIEWS.items()})
                except OSError:
                    issues.append("Source/inventory report could not be saved.")
                self.events.put(("ready", issues))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def select_clip(self):
        self.pause()
        self.playback_guard.reset()
        self.view = VIEWS[self.selection.get()]
        self.clip = self.view.clip
        self.polygons = inventory(self.view)
        self.sync_selectors()
        self.position = 0.0
        self.duration = 0.0
        self.render_key = self.picture_key = None
        self.photo = None
        self.video_label.configure(image="", text="Preparing recordings…" if not self.ready else "Opening recording…")
        self.render_observation(None)
        if self.player:
            self.player.close()
            self.player = None
        if self.ready:
            try:
                stabilization = json.loads((PROJECT_ROOT / 'presets/overhead-all-bays.json').read_text()).get('stabilization') if self.view.site=='overhead' else None
                self.player = LocalPlayer(self.view.path, self.view.resolution, stabilization)
                self.duration = self.player.duration
                self.scrubber.configure(to=self.duration)
                for widget in (self.play_button, self.replay_button, self.scrubber):
                    widget.configure(state="normal")
                self.seek(0)
                self.toggle_play()
            except (SourceError, cv2.error, OSError):
                self.playback_failed()

    def pause(self):
        if self.playing:
            self.position = min(self.duration, max(0, time.monotonic()-self.anchor))
        self.playing = False
        if hasattr(self, "play_button"):
            self.play_button.configure(text="Play")

    def toggle_play(self):
        if not self.ready or not self.player:
            return
        if self.playing:
            self.pause()
        else:
            if self.position >= self.duration:
                self.seek(0)
            self.anchor = time.monotonic()-self.position
            self.playing = True
            self.play_button.configure(text="Pause")

    def seek(self, value):
        if not self.ready or not self.player:
            return
        self.playback_guard.reset()
        self.render_key = None
        self.position = min(self.duration, max(0, float(value)))
        self.anchor = time.monotonic()-self.position
        self.picture_key = None
        self.update_recorded()

    def replay(self):
        self.seek(0)
        if not self.playing:
            self.toggle_play()

    def invalidate_picture(self):
        self.picture_key = None

    def tab_changed(self, event=None):
        if self.tabs.select() == str(self.live):
            self.pause()

    def show_bay_details(self, event=None):
        selected = self.table.selection()
        row = self.displayed_rows.get(selected[0]) if selected else None
        if row:
            basis = (row.get('final_reason') or 'reference and MOG2 comparison').replace('_',' ')
            confirmed = {'reference_and_mog2':'Reference + MOG2', 'yolov8':'YOLOv8',
                         'reference':'Reference', 'mog2':'MOG2', 'mobilenet_ssd':'MobileNet vehicle detection',
                         'mobilenet_reviewed_empty':'MobileNet + reviewed empty appearance',
                         'reviewed_empty_and_three_clean_no_detections':'reviewed empty reference + three clean observations'}.get(row.get('final_confirmed_by'))
            confirmation = f"Supported by {confirmed}" if confirmed else "No method confirmation"
            if row.get('final_provisional'):
                confirmation = f"PROVISIONAL {row['state'].upper()}: no definite method confirmation"
            detail = (f"{row['bay_id']}: {confirmation}.\nFinal: {basis}.\n"
                      f"Reference: {row['reference_state']} ({row.get('reference_reason') or 'classified'}); "
                      f"MOG2: {row['mog2_state']} ({row.get('mog2_reason') or 'classified'}).\n"
                      f"MobileNet + empty: {row.get('vehicle_state', 'unknown')} "
                      f"({row.get('vehicle_reason') or 'not run'}); "
                      f"YOLOv8: {row.get('yolo_state', 'unknown') if row.get('yolo_requested') else 'skipped'} "
                      f"({row.get('yolo_reason') or 'not run'}).")
            if row.get('vacancy_guard_streak') and row.get('final_state') not in ('occupied', 'vacant'):
                detail += f"\nVacancy guard: {row['vacancy_guard_streak']}/3 consecutive observations."
            if self.show_alternate.get():
                detail += (f"\nEXP alternate: {row.get('final_alt_state', 'unknown').upper()} | "
                           f"Confirmed by: {row.get('final_alt_confirmed_by') or 'none'}.")
            self.row_details.configure(text=detail)

    def save_alternate_comparison(self):
        if self.show_alternate.get() and self.out:
            try:
                export_alternate_review(self.out, self.review.samples)
            except OSError:
                self.status.configure(text='Experimental comparison could not be saved; primary results are unchanged.')

    def toggle_alternate(self):
        enabled = self.show_alternate.get()
        self.table.configure(displaycolumns=(*self.primary_columns, 'final_alt', 'alt_basis') if enabled else self.primary_columns)
        self.alternate_note.configure(text=(
            'EXP = experimental Reference priority (occupied AND vacant). Scroll right for its confirmation.\n'
            'It can override a YOLO occupied result. Chart, areas, video and summaries still show primary Final.' if enabled else ''))
        selected = self.table.selection()
        selected_bay = self.displayed_rows.get(selected[0], {}).get('bay_id') if selected else None
        self.render_observation(self.last_displayed_pair)
        for iid, row in self.displayed_rows.items():
            if row['bay_id'] == selected_bay:
                self.table.selection_set(iid)
                self.show_bay_details()
        self.save_alternate_comparison()

    def render_observation(self, pair):
        self.last_displayed_pair = pair
        if self.show_alternate.get() and pair:
            pair = add_alternate(pair)
        rows, s = chart_data(pair, [b['bay_id'] for b in self.polygons])
        self.chart.delete("all")
        for state, start, extent in ring_segments(s):
            if abs(extent) >= 359.999:
                self.chart.create_oval(45, 5, 235, 195, fill=COLORS[state], outline="")
            else:
                self.chart.create_arc(45, 5, 235, 195, start=start, extent=extent,
                                      fill=COLORS[state], outline="white", width=3)
        self.chart.create_oval(72, 32, 208, 168, fill="white", outline="white")
        available = s["occupancy_min_pct"] is not None
        center = f"{s['occupied']} / {s['total_monitored_bays']}" if available else (f"— / {s['total_monitored_bays']}" if rows else "—")
        self.chart.create_text(140, 90, text=center, font=("Segoe UI", 28, "bold"), fill=INK)
        self.chart.create_text(140, 122, text="occupied bays" if available else "unavailable", font=("Segoe UI", 10), fill=MUTED)
        self.rate.configure(text=occupancy_text(s) + (" occupied" if available else ""))
        for state in STATES:
            self.legend[state].configure(text=f"{s[state]} {state}")
        for iid in self.table.get_children():
            self.table.delete(iid)
        self.displayed_rows = {}
        for row in rows:
            values = (row["bay_id"], row["reference_state"].upper(), row["mog2_state"].upper(),
                      row.get('vehicle_state','unknown').upper(),
                      (row.get('yolo_state','unknown').upper() if row.get('yolo_requested') else 'SKIPPED'),
                      row["state"].upper() + (' (P)' if row.get('final_provisional') else ''))
            if self.show_alternate.get():
                values += ('EXP: ' + row.get('final_alt_state', 'unknown').upper(),
                           row.get('final_alt_confirmed_by') or 'No confirmation')
            iid = self.table.insert("", "end", values=values,
                                    tags=('provisional' if row.get('final_provisional') else row["state"],))
            self.displayed_rows[iid] = row
        self.row_details.configure(text='Select a bay to inspect each method and the Final source. (P) means provisional, without definite method confirmation.')
        provisional_occupied = sum(row['state']=='occupied' and bool(row.get('final_provisional')) for row in rows)
        provisional_vacant = sum(row['state']=='vacant' and bool(row.get('final_provisional')) for row in rows)
        self.video_counts.configure(text="   |   ".join(f"{s[state]} {state}" for state in STATES) +
                                    f"   |   Occupancy: {occupancy_text(s)}   |   {provisional_occupied} provisional occupied, {provisional_vacant} provisional vacant")
        pending = sum(b.get('calibration_pending', False) for b in self.polygons)
        self.scope_label.configure(text=f"{len(rows)} mapped bays; {pending} lack full two-state calibration. (P) = provisional estimate, not method-confirmed." if rows else
                                   "View only: bay correspondence/calibration not verified.")
        if not rows:
            self.video_counts.configure(text="VIEW ONLY · Overlapping CHAD view; no verified bay mapping or occupancy counts.")
        if pair:
            r = pair["reference"]
            self.sample_label.configure(text=f"{SITES[self.view.site]} / {self.view.camera} / {self.view.label} · Sample {r['sample_time_seconds']:.1f}s "
                f"(source frame {r['video_position_seconds']:.3f}s) · Processed {local_time(pair.get('final',pair['mog2'])['processed_at'])}\n"
                "Original capture time: unknown. Chart holds the most recent sampled estimate until the next 3-second sample.")
        else:
            self.sample_label.configure(text=f"{SITES[self.view.site]} / {self.view.camera} / {self.view.label}\n"
                "No usable observation or calibrated bay mapping for this view. Unknown is not vacant.")

    def update_recorded(self):
        if not self.player:
            return
        self.clock_label.configure(text=f"{video_clock(self.position)} / {video_clock(self.duration)}")
        self.seek_var.set(self.position)
        pair = self.playback_guard.observe(self.review.at(self.clip.id, self.position))
        window = self.review.window_at(self.clip.id, self.position)
        key = (self.clip.id, id(pair), id(window))
        if key != self.render_key:
            self.render_observation(pair)
            self.window_label.configure(text=("No occupancy summary: this view has no verified bay mapping." if not self.view.analyzed else
                "Saved 10-second analysis history for this view; after seeking, current display waits for three fresh played samples.\n\n" + window_text(window)))
            if self.view.analyzed:
                self.area_selections[self.view.site] = (self.clip.id, self.position)
            self.render_areas()
            self.render_key = key
        if self.pages.select() != str(self.watch) or self.tabs.select() != str(self.recorded):
            return
        # Render at up to ~16 fps; source time follows a monotonic clock.
        picture_key = (self.clip.id, int(self.position*15), self.video_label.winfo_width(), self.video_label.winfo_height())
        if picture_key == self.picture_key:
            return
        try:
            image = self.player.image_at(self.position)
            if self.view.site == "chad":
                image = cv2.resize(image, (1280, 720), interpolation=cv2.INTER_AREA)
            rows, _ = chart_data(pair, [b['bay_id'] for b in self.polygons])
            by_bay = {r["bay_id"]: r for r in rows}
            for i, slot in enumerate(self.polygons):
                points = np.array(slot["polygon"], dtype=np.int32)
                result = by_bay.get(slot['bay_id'], {})
                state = result.get('state', 'unknown')
                color = '#956412' if result.get('final_provisional') else COLORS[state]
                rgb = tuple(int(color[j:j+2], 16) for j in (1, 3, 5))
                dense = len(self.polygons)>20
                cv2.polylines(image, [points], True, rgb[::-1], 1 if dense else 3)
                x, y = points[0]
                label = slot['id'] if dense else slot['bay_id'].split('-')[-1]
                cv2.putText(image, label + (f" {state[0].upper()}(P)" if result.get('final_provisional') else ''),
                    (int(x)+2, int(y)+13) if dense else (int(x), max(20, int(y)-9)),
                    cv2.FONT_HERSHEY_SIMPLEX, .34 if dense else .58, rgb[::-1], 1 if dense else 2)
            self.photo = png_photo(image, self.video_label.winfo_width(), self.video_label.winfo_height())
            self.video_label.configure(image=self.photo, text="")
            self.picture_key = picture_key
        except (SourceError, cv2.error, OSError):
            self.playback_failed()

    def playback_failed(self):
        self.pause()
        if self.player:
            self.player.close()
            self.player = None
        self.photo = None
        self.render_observation(None)
        if self.view.analyzed:
            # Clear current area evidence after an actual playback failure.
            self.area_selections[self.view.site] = (self.clip.id, -1.0)
            self.render_areas()
        self.window_label.configure(text="Playback unavailable. Previous results remain saved as history.")
        self.video_label.configure(image="", text="Cannot decode this recording. Select another clip or prepare again.")
        self.status.configure(text="Video playback failed; displayed occupancy cleared.")
        for widget in (self.play_button, self.replay_button, self.scrubber):
            widget.configure(state="disabled")

    def browse_config(self):
        value = filedialog.askopenfilename(parent=self.root, title="Choose camera configuration", filetypes=[("JSON configuration", "*.json")])
        if value:
            self.live_config.set(value)

    def connect_live(self):
        if self.live_thread and self.live_thread.is_alive():
            self.live_status.configure(text="Camera connection is active or stopping. Disconnect, then wait for the bounded read to finish before reconnecting.")
            return
        self.live_generation += 1
        self.live_stop = threading.Event()
        self.live_deadline = None
        self.clear_live("Connecting…", "Opening configured camera. No camera occupancy is calculated in this viewer.")
        self.live_thread = threading.Thread(target=live_worker,
            args=(self.live_config.get(), self.live_stop, self.live_events, self.live_generation), daemon=True)
        self.live_thread.start()

    def clear_live(self, title, message):
        self.live_photo = None
        self.live_label.configure(image="", text=title)
        self.live_status.configure(text=message)

    def disconnect_live(self):
        self.live_stop.set()
        self.live_generation += 1
        self.live_deadline = None
        self.clear_live("Live camera disconnected", "Live occupancy unavailable. No previous camera frame is being displayed.")

    def handle_live_event(self, generation, kind, value):
        if generation != self.live_generation:
            return
        if kind == "error":
            self.live_deadline = None
            hint = " Set PARKING_CAMERA_URL before launching, then retry." if value == "camera_url_missing_or_invalid" else " Check the camera configuration and connection."
            self.clear_live("Live frame unavailable", f"{value}.{hint} Occupancy unavailable.")
        elif kind == "frame":
            image, received, captured, received_mono, stale_after = value
            if time.monotonic() - received_mono > stale_after:
                self.clear_live("Stale camera frame", "No recent frame is available. Occupancy unavailable.")
                return
            self.live_deadline = received_mono + stale_after
            self.live_photo = png_photo(image, max(640, self.live_label.winfo_width()), max(360, self.live_label.winfo_height()))
            self.live_label.configure(image=self.live_photo, text="")
            self.live_status.configure(text=f"Received: {local_time(received.isoformat())}  |  Capture time: "
                f"{local_time(captured.isoformat()) if captured else 'unknown'}  |  Viewer only; live occupancy unavailable.")

    def open_results(self):
        if self.out and self.out.exists():
            os.startfile(str(self.out))

    def open_validation_report(self):
        """A read-only document viewer, with no dataset playback or inference."""
        path = PROJECT_ROOT / MANUAL_NAME
        try:
            contents = read_document(PROJECT_ROOT, 'EXTERNAL_VALIDATION.md')
        except (OSError, ValueError):
            self.status.configure(text='External validation report is unavailable: ' + str(path))
            return
        window = tk.Toplevel(self.root)
        window.title('External validation report (read-only)')
        window.geometry('960x650')
        scroll = ttk.Scrollbar(window, orient='vertical')
        scroll.pack(side='right', fill='y')
        text = tk.Text(window, wrap='word', font=('Consolas', 10), padx=14, pady=14,
                       yscrollcommand=scroll.set)
        text.pack(fill='both', expand=True)
        scroll.configure(command=text.yview)
        text.insert('1.0', contents)
        text.configure(state='disabled')
        self.validation_viewer = window, text

    def tick(self):
        if self.closed:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "comparison_samples":
                    self.review.add_samples(value)
                    self.save_alternate_comparison()
                    self.status.configure(text=f"Analyzing recorded sites… video sample {value['timeline_seconds']:.0f}s. Playback will start after preparation.")
                elif kind == "comparison_windows":
                    self.review.add_windows(value)
                elif kind == "status":
                    self.status.configure(text=str(value))
                elif kind == "ready":
                    self.ready = True
                    self.prepare_button.configure(text="Analyze again", state="normal")
                    self.results_button.configure(state="normal")
                    self.source_errors = value
                    self.status.configure(text=("; ".join(value) if value else
                        "Ready: OpenCV-first decisions; YOLOv8 only checks unresolved or conflicting bays. (P) marks provisional results."))
                    self.select_clip()
                    if self.tabs.select() == str(self.live):
                        self.pause()
                elif kind == "prepare_error":
                    self.status.configure(text=value)
                    self.video_label.configure(text=value, image="")
                    self.prepare_button.configure(text="Retry preparation", state="normal")
        except queue.Empty:
            pass
        try:
            while True:
                self.handle_live_event(*self.live_events.get_nowait())
        except queue.Empty:
            pass
        if self.live_deadline is not None and time.monotonic() > self.live_deadline:
            self.live_deadline = None
            self.clear_live("Stale camera frame", "The latest frame expired. Waiting for a new frame; occupancy unavailable.")
        if self.ready and self.player:
            if self.playing:
                self.position = min(self.duration, time.monotonic()-self.anchor)
                if self.position >= self.duration:
                    self.pause()
                    self.status.configure(text="Recording finished. The chart shows its last sampled historical estimate. Select another recording or press Replay.")
            self.update_recorded()
        self.timer = self.root.after(60, self.tick)

    def close(self):
        self.closed = True
        self.stop.set()
        self.live_stop.set()
        if self.player:
            self.player.close()
        self.root.after_cancel(self.timer)
        self.root.destroy()


def launch(interval=3.0, start_video="chad-1"):
    parser = argparse.ArgumentParser(description="Parking occupancy chart and video viewer")
    parser.add_argument("--video", choices=["all", *VIEWS], default=start_video,
                        help="Initial recording/view; both sites are prepared")
    parser.add_argument("--no-autostart", action="store_true", help="Wait for Prepare recordings")
    args = parser.parse_args()
    root = tk.Tk()
    ParkingInterface(root, interval, "chad-1" if args.video == "all" else args.video, not args.no_autostart)
    root.mainloop()
    return 0
