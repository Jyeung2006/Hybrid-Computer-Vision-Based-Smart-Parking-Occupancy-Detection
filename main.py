"""Press Run for occupancy charts and video review; --terminal keeps text output."""
from pathlib import Path
import os
import subprocess
import sys

UPDATE_INTERVAL_SECONDS = 3.0
START_VIDEO = "chad-1"  # Initially selected recording in the interface.
RUN_ALL_VIDEOS = True  # Terminal mode only: False selects START_VIDEO.


def main():
    root = Path(__file__).resolve().parent
    environment = root / ".venv"
    interpreter = environment / "Scripts" / "python.exe"
    if interpreter.exists() and Path(sys.prefix).resolve() != environment.resolve():
        return subprocess.call([str(interpreter), str(root / "main.py"), *sys.argv[1:]], cwd=root)
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))
    modes = [flag for flag in ("--check", "--dashboard", "--terminal", "--legacy-dashboard") if flag in sys.argv]
    if len(modes) > 1:
        raise SystemExit("Choose only one display mode: --check, --dashboard, --terminal or --legacy-dashboard.")
    if "--legacy-dashboard" in sys.argv:
        sys.argv.remove("--legacy-dashboard")
        from parking_probe.desktop import launch
        return launch(UPDATE_INTERVAL_SECONDS, START_VIDEO)
    if "--check" in sys.argv:
        sys.argv.remove("--check")
        from parking_probe.opencv_check import run
        return run()
    # Existing automation/headless flags continue to select terminal behavior.
    terminal = "--terminal" in sys.argv or any(a.split("=", 1)[0] in ("--fast", "--frames", "--site", "--headless") for a in sys.argv)
    if "--dashboard" in sys.argv:
        sys.argv.remove("--dashboard")
        if terminal:
            raise SystemExit("Dashboard does not accept terminal-only --fast, --frames, --site or --headless options.")
    if terminal:
        if "--terminal" in sys.argv:
            sys.argv.remove("--terminal")
        from parking_probe.terminal import launch
        return launch(UPDATE_INTERVAL_SECONDS, START_VIDEO, RUN_ALL_VIDEOS)
    from parking_probe.interface import launch
    return launch(UPDATE_INTERVAL_SECONDS, START_VIDEO)


if __name__ == "__main__":
    raise SystemExit(main())
