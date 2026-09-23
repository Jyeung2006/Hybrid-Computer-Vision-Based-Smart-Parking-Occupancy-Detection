"""Local Tkinter display. No web server, database, Flutter or model inference."""
import argparse
import base64
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from .catalog import CLIPS, PROJECT_ROOT, SOURCE_PAGE
from .display_model import local_time, occupancy_text, runtime_error, video_clock

BG, CARD, INK, MUTED = "#edf2f7", "#ffffff", "#18283b", "#64748b"
STATE_COLORS = {"vacant": "#047857", "occupied": "#be123c", "uncertain": "#a16207", "unknown": "#64748b"}


class ParkingWindow:
    def __init__(self, root, interval=3, start_video="chad-1", autostart=True):
        self.root, self.interval = root, interval
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.run_number = 0
        self.closed = False
        self.photo = None
        self.output_directory = None
        root.title("Parking occupancy | OpenCV experiment")
        root.geometry("1280x840")
        root.minsize(1060, 750)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, foreground=INK, fieldbackground=CARD,
                        rowheight=30, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", background="#e8eef5", foreground=INK,
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.configure("TCombobox", font=("Segoe UI", 10), padding=5)
        root.option_add("*Font", "{Segoe UI} 10")

        header = tk.Frame(root, bg="#13283e", padx=24, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="PARKING OBSERVATORY", bg="#13283e", fg="white", font=("Segoe UI", 19, "bold")).pack(side="left")
        tk.Label(header, text=f"RECORDED VIDEO   /   UPDATE EVERY {interval:g} SECONDS", bg="#13283e", fg="#9de4da", font=("Segoe UI", 10, "bold")).pack(side="right")
        toolbar = tk.Frame(root, bg=BG, padx=22, pady=14)
        toolbar.pack(fill="x")
        self.selected = tk.StringVar(value=next(c.title for c in CLIPS if c.id == start_video))
        self.selector = ttk.Combobox(toolbar, textvariable=self.selected, state="readonly", values=[c.title for c in CLIPS], width=51)
        self.selector.pack(side="left")
        self.selector.bind("<<ComboboxSelected>>", self.selection_changed)
        self.start_button = self.button(toolbar, "Run selected video", self.start, "#087f8c", "white")
        self.start_button.pack(side="left", padx=(12, 6))
        self.button(toolbar, "Stop", self.stop.set).pack(side="left", padx=6)
        self.button(toolbar, "Video sources", lambda: webbrowser.open(SOURCE_PAGE)).pack(side="right")

        metric_bar = tk.Frame(root, bg=BG, padx=22)
        metric_bar.pack(fill="x")
        self.metrics = {}
        for i, (key, title, color) in enumerate((
                ("occupied", "PARKED IN MONITORED BAYS", "#be123c"),
                ("vacant", "VACANT BAYS", "#047857"),
                ("unresolved", "UNCERTAIN / UNKNOWN", "#a16207"),
                ("occupancy", "MONITORED OCCUPANCY", "#087f8c"))):
            metric_bar.columnconfigure(i, weight=1, uniform="metric")
            card = tk.Frame(metric_bar, bg=CARD, padx=16, pady=12)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            tk.Label(card, text=title, bg=CARD, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            value = tk.StringVar(value="—")
            tk.Label(card, textvariable=value, bg=CARD, fg=color, font=("Segoe UI", 25, "bold")).pack(anchor="w", pady=(4, 0))
            self.metrics[key] = value

        content = tk.Frame(root, bg=BG, padx=22, pady=14)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        left = tk.Frame(content, bg=CARD, padx=12, pady=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(left, text="CAMERA VIEW", bg=CARD, fg=INK, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.image_label = tk.Label(left, bg="#17283b", fg="white", text="Preparing camera preview…")
        self.image_label.pack(fill="both", expand=True, pady=(10, 6))
        self.position = tk.StringVar(value="Video 00:00  |  Original capture time: unknown")
        tk.Label(left, textvariable=self.position, bg=CARD, fg=MUTED).pack(anchor="w")
        self.updated = tk.StringVar(value="No observations yet")
        tk.Label(left, textvariable=self.updated, bg=CARD, fg=MUTED).pack(anchor="w", pady=(3, 0))
        right = tk.Frame(content, bg=CARD, padx=12, pady=12)
        right.grid(row=0, column=1, sticky="nsew")
        self.scope = tk.StringVar(value="BAY STATUS")
        tk.Label(right, textvariable=self.scope, bg=CARD, fg=INK, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        self.table = ttk.Treeview(right, columns=("bay", "state", "score"), show="headings", selectmode="none")
        for key, title, width in (("bay", "Bay", 45), ("state", "State", 100), ("score", "Difference", 78)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor="center", stretch=key == "state")
        for state, color in STATE_COLORS.items():
            self.table.tag_configure(state, foreground=color)
        scroll = ttk.Scrollbar(right, command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        tk.Label(right, text="Difference score: 0–1\nAppearance change, not probability", bg=CARD, fg=MUTED, justify="left", font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))
        self.status = tk.StringVar(value="Ready")
        tk.Label(root, textvariable=self.status, bg="#e2eaf3", fg=INK, anchor="w", justify="left", wraplength=1180, padx=24, pady=10).pack(fill="x")
        tk.Label(root, text="Only configured bays contribute to counts. Unresolved bays produce an occupancy range.  •  OpenCV comparison only",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9), pady=8).pack(fill="x")
        self.show_preview()
        root.after(50, self.poll)
        if autostart:
            root.after(150, self.start)

    @staticmethod
    def button(parent, text, command, bg="#dce5ef", fg=INK):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, relief="flat", padx=14, pady=7, cursor="hand2")

    def clip(self):
        return next(c for c in CLIPS if c.title == self.selected.get())

    def show_preview(self):
        path = PROJECT_ROOT / "assets" / "previews" / f"{self.clip().id}.png"
        if path.exists():
            self.photo = tk.PhotoImage(file=str(path))
            self.image_label.configure(image=self.photo, text="")
        self.position.set("Source preview only  |  Original recording time: unknown")

    def selection_changed(self, event=None):
        if self.worker and self.worker.is_alive():
            self.stop.set()
        self.run_number += 1
        self.clear_observations()
        self.show_preview()
        self.status.set("Selected another recording. Press Run selected video to process it.")

    def clear_observations(self):
        for value in self.metrics.values():
            value.set("—")
        for item in self.table.get_children():
            self.table.delete(item)
        self.updated.set("No observations for this recording yet")
        self.scope.set("BAY STATUS")

    def start(self):
        if self.worker and self.worker.is_alive():
            self.status.set("Stopping the previous run; press Run again once it has stopped.")
            self.stop.set()
            return
        self.stop = threading.Event()
        self.run_number += 1
        generation = self.run_number
        selected = self.clip()
        self.clear_observations()
        self.status.set("Loading OpenCV and preparing the selected recording…")

        def emit(kind, value):
            self.events.put((generation, kind, value))

        def work():
            try:
                from .monitor import run_recording
                run_recording(selected, self.interval, self.stop, emit)
            except Exception as exc:
                emit("error", runtime_error(exc))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def poll(self):
        if self.closed:
            return
        while True:
            try:
                generation, kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.run_number:
                continue
            if kind in ("status", "error", "done"):
                self.status.set(value)
                if kind == "error":
                    self.clear_observations()
            elif kind == "observation":
                self.render(*value)
        self.root.after(50, self.poll)

    def render(self, result, png):
        summary = result["summary"]
        available = result["analysis_status"] != "unavailable"
        for key in ("occupied", "vacant", "unresolved"):
            self.metrics[key].set(str(summary[key]) if available else "—")
        self.metrics["occupancy"].set(occupancy_text(summary))
        self.scope.set(f'BAY STATUS  ·  {summary["total_monitored_bays"]} monitored')
        if png:
            self.photo = tk.PhotoImage(data=base64.b64encode(png))
            self.image_label.configure(image=self.photo, text="")
        else:
            self.photo = None
            self.image_label.configure(image="", text="Frame unavailable. Earlier results remain in saved history.")
        self.position.set(f'Video {video_clock(result["video_position_seconds"])} / {video_clock(result["video_duration_seconds"])}  |  Capture date/time: unknown')
        self.updated.set(f'Processed {local_time(result["processed_at"])}  |  {result.get("processing_duration_ms") or 0:.1f} ms')
        for item in self.table.get_children():
            self.table.delete(item)
        for slot in result["slots"]:
            score = "—" if slot["difference_score"] is None else f'{slot["difference_score"]:.3f}'
            self.table.insert("", "end", values=(slot["slot_id"], slot["state"].capitalize(), score), tags=(slot["state"],))
        self.status.set(result.get("error") or f"Updated. Next observation in {self.interval:g} seconds. Results saved automatically.")

    def close(self):
        self.closed = True
        self.stop.set()
        self.root.destroy()


def launch(interval=3, start_video="chad-1"):
    parser = argparse.ArgumentParser(description="Parking monitor: open main.py in VS Code and press Run.")
    parser.add_argument("--video", choices=[c.id for c in CLIPS], default=start_video)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--fast", action="store_true", help="Headless verification only: skip wall-clock waits")
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--no-autostart", action="store_true", help="Open source previews without starting analysis")
    args = parser.parse_args()
    if args.headless:
        try:
            from .monitor import run_recording
            return run_recording(next(c for c in CLIPS if c.id == args.video), interval, threading.Event(),
                                 lambda kind, value: print(value if kind != "observation" else value[0]["summary"], flush=True),
                                 fast=args.fast, frame_limit=args.frames)
        except Exception as exc:
            print(runtime_error(exc))
            return 2
    root = tk.Tk()
    ParkingWindow(root, interval, args.video, not args.no_autostart)
    root.mainloop()
    return 0
