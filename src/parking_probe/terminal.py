"""Parking occupancy reports in the IDE terminal, without a dashboard.

Uses the same calibrated OpenCV analysis and persisted reports as the optional
display. The import/playback-only diagnostic is available via main.py --check.
"""
import argparse
from datetime import datetime
import threading

from .catalog import CLIPS
from .display_model import runtime_error, video_clock, occupancy_text
from .bay_fusion import format_window


def launch(interval=3, start_video="chad-1", run_all=True):
    parser = argparse.ArgumentParser(description="Sample parking bays every three seconds; summarize each ten-second window.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--video", choices=["all", *[c.id for c in CLIPS]], default=None)
    source.add_argument("--site", help="Local JSON mapping synchronized recordings to shared physical bay IDs")
    parser.add_argument("--frames", type=int, default=0, help="Number of observations; 0 means the whole recording")
    parser.add_argument("--headless", action="store_true", help="Accepted for compatibility; this mode already has no window")
    parser.add_argument("--fast", action="store_true", help="Verification only: process samples without three-second waits")
    args = parser.parse_args()
    if args.frames < 0:
        parser.error("--frames must be zero or positive")
    print("PARKING OCCUPANCY | OpenCV reference + MOG2 comparison" if not args.site else
          "PARKING OCCUPANCY | Configured multicamera reference comparison", flush=True)
    print(f"Samples: every {interval:g}s | Summaries: every 10s | Recorded footage", flush=True)
    print(f"Processing date: {datetime.now().astimezone():%Y-%m-%d %Z} | Original capture date/time: unknown", flush=True)
    print("OCCUPIED = above the occupied threshold; VACANT = similar to the empty reference.", flush=True)
    print("UNCERTAIN = between thresholds; UNKNOWN = cannot assess. Scores are not probabilities.", flush=True)
    if args.site:
        print("Multiple views: agreement supplies the state; disagreement is UNCERTAIN. Each bay counts once.", flush=True)
    else:
        print("The two methods are displayed separately; agreement is not a calibrated probability or confirmed state.", flush=True)
    if args.fast:
        print("FAST VERIFICATION: three-second video samples, without wall-clock waits.", flush=True)
    stop = threading.Event()

    def emit(kind, value):
        if kind == "final_summary":
            from .comparison import format_final
            print(format_final(value), flush=True)
        elif kind == "comparison_samples":
            from .comparison import format_samples
            print(format_samples(value), flush=True)
        elif kind == "comparison_windows":
            from .comparison import format_comparison_windows
            print(format_comparison_windows(value), flush=True)
        elif kind == "observation":
            states = " | ".join(f"{b['bay_id']} {b['state'].upper():<9}" for b in value["bays"])
            print(f"{video_clock(value['timeline_seconds'])}  {states} | Site {occupancy_text(value['summary'])}", flush=True)
        elif kind == "window":
            print(format_window(value), flush=True)
        elif kind == "done":
            print("\n" + value, flush=True)
        else:
            print(value, flush=True)

    try:
        if args.site:
            from .site_replay import load_site, run_site
            print("Custom --site mode uses the existing reference branch; built-in CHAD comparison includes MOG2.", flush=True)
            site = load_site(args.site)
            return run_site(site, interval, stop, emit, fast=args.fast, frame_limit=args.frames)
        else:
            from .comparison import run_comparison
            selected = args.video or ("all" if run_all else start_video)
            clips = list(CLIPS) if selected == "all" else [c for c in CLIPS if c.id == selected]
            print("Recordings: " + ", ".join(c.id for c in clips), flush=True)
            print("Different periods from one camera: compare them side by side; never sum them as extra physical bays.", flush=True)
            print("REFERENCE = empty-reference difference. MOG2 = calibrated foreground fraction after shadow/noise removal.", flush=True)
            print("B01 -> CHAD-P001 | B02 -> CHAD-P002 | B03 -> CHAD-P003; other bays excluded.", flush=True)
            return run_comparison(clips, interval, stop, emit, fast=args.fast, frame_limit=args.frames)
    except KeyboardInterrupt:
        stop.set()
        print("\nStopped. Earlier observations remain in the saved run history.", flush=True)
        return 130
    except Exception as exc:
        print("\nCurrent occupancy unavailable: " + runtime_error(exc), flush=True)
        return 2
