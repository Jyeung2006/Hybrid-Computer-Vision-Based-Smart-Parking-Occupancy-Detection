# Occupancy chart and video interface

**Current Final policy (23 September):** guarded vacancy can resolve an otherwise uncertain bay after three consecutive clean observations. `VACANT (P)` is provisional no-reference evidence. See [GUARDED_VACANCY.md](GUARDED_VACANCY.md) for the rule and measured replay; older strict-policy descriptions below are historical where they differ.

Run `main.py` in VS Code. The native Tkinter interface uses the existing Python/OpenCV environment. The latest full preparation took **about 2–3 minutes** with cached media/models. It analyzes all eight recordings in a background thread before review starts. No URL, API key, CUDA or extra installation is needed here. The interface was inspected on this computer's 1280×720 screen.

## Navigation

**Optional comparison:** in Occupancy overview, enable **Show alternate: Reference priority (experimental)** to show `EXP: Alternate` beside primary Final. It starts OFF. Scroll right for the alternate confirmation source; select a bay for both sources, and scroll the overview down on smaller windows. This can accept calibrated Reference occupied or vacant even when another method differs. The chart, areas, video labels and summaries retain primary Final. Enabling it saves a separate comparison under `experimental-reference-priority/` in the run folder. See [the short guide and measured risks](REFERENCE_PRIORITY.md).

**Read the external test:** **Reports → View external validation report** opens the Markdown report in a read-only window. PKLot is a discrete-snapshot dataset; it is not added as a playable video.

| Control | Action |
| --- | --- |
| Site / View / Recording | Select the car park, real camera angle and recording. |
| Areas & availability | Counts and source/sample times for up to five area rows: CHAD far/near and overhead west/middle/east. Double-click to watch. |
| Occupancy overview | Circle chart, counts/range and Reference/MOG2/YOLOv8/Final states. Scroll for every bay and select a row for its reason. |
| Watch video | Actual footage with all mapped outlines, short bay IDs and count strip. |
| Play / Pause / Replay / slider | Control playback and the displayed observations together. |
| 10-second summaries | Completed windows, all methods, all bays and occupied-time percentages/ranges. Final short windows are labelled partial. |
| Open saved results | Open the current run's JSON/CSV and annotated-image folder. |
| Analyze again | Save a fresh run without replacing empty references. |
| Live camera | Pause review and open the separate authorized-endpoint viewer. |

## Reading the results

Overhead monitors **69 bays**: west 24, middle 22 and east 23. All are in the chart, scrollable table, video and summaries, even if they never change. Only W01/W02/E01 have full two-state Reference/MOG2 calibration; the remaining 66 use YOLO verification with their missing classic evidence visible. Fifteen overhead bays have reviewed empty images; their guarded matching evidence can now support vacancy after three clean observations. The camera's small drift is registered to the setup view with explicit limits; unusable registration remains an error. See [GUARDED_VACANCY.md](GUARDED_VACANCY.md).

CHAD Cameras 1/2/3/4 monitor 9/5/4/3 bays. P009 is manually shared across the views; Camera 2/3 far-row IDs remain view-local. The four Camera 1 files are different recording periods of the same view. Their counts are not added together. See [CAMERA_MAPPING.md](CAMERA_MAPPING.md).

Matching definite Reference/MOG2 results are kept, with YOLO marked **SKIPPED** for that bay. Any uncertain, unknown or opposing result triggers YOLO. A vehicle score at least 0.80 plus unique polygon association gives occupied. A single no-detection remains uncertain; three consecutive clean no-detections can give guarded vacancy when reviewed empty evidence matches, or a clearly labelled provisional vacancy when no reference exists. Weak/nearby boxes, conflicts, occlusion, stale frames and reference mismatches block the guard. Select a bay to read its evidence. Red/green show final occupied/vacant, amber uncertain and provisional, grey unknown. See [GUARDED_VACANCY.md](GUARDED_VACANCY.md).

Exact occupancy is `occupied / total × 100` only if every bay is resolved. Otherwise the range runs from `occupied / total` to `(occupied + unresolved) / total`, multiplied by 100. Unresolved bays are not free. The latest replay's last overhead frame is 48 occupied, 9 vacant and 12 uncertain / 69. Original source capture times are unknown; the footer labels source position and actual processing time.

## Timing and outputs

Preparation samples each recording chronologically at 0, 3, 6... video seconds. One YOLO worker handles at most one running and one waiting frame. Playback reveals each precomputed result at its video timestamp, holding it until the next sample. Completed summaries appear at 10, 20... seconds. Seeking/replay resets the displayed vacancy streak and requires three newly played clean samples; saved ten-second windows remain labelled historical analysis and MOG2 is not updated backwards. The overhead preview is registered into the same setup coordinate system as analysis.

Area rows remember the last selected recording/position for each site and show their own sample times. They represent independent historical observations, not simultaneous live availability. At EOF the last estimate remains historical. Decoder/source failure clears current occupancy; previous results remain timestamped history. This is recorded review, not a hard real-time live throughput claim.

Runs save to `runs/areas/<UTC-run-time>/`, with `chad/`, `chad-camera-2/`, `chad-camera-3/`, `chad-camera-4/` and `overhead/` subfolders. Each includes observations/history, windows, final summaries and per-recording `reference/`, `mog2/`, `yolo/`, `final/` reports/images. `bay-inventory.json` stores all polygons/IDs and calibration status; `area-summary.json` has `live_availability: false`; `source-status.json` records issues. Terminal results remain under `runs/comparison/` and retain their older three-bay scope.

## Optional live camera

1. Obtain an operator-authorized direct camera endpoint. A webpage containing a player is not a direct endpoint. In `config.local.json`, use `source.type: "snapshot"` for HTTP JPEG/PNG, or `"stream"` for a direct HTTP/MJPEG/HLS/RTSP stream. Keep addresses and credentials in environment variables, not this JSON file.
2. In the VS Code PowerShell terminal, set your endpoint and launch from **that same terminal**:

   ```powershell
   $env:PARKING_CAMERA_URL = 'https://your-authorized-camera.example/current.jpg'
   .\.venv\Scripts\python.exe main.py
   ```

   The example URL is a placeholder. Run/F5 may not inherit variables set only inside an existing terminal, so use the command above for this setup.
3. Select **Live camera**, choose the configuration if necessary, and click **Connect**. Use **Disconnect** when finished.

Snapshots refresh at the configured `interval_seconds` (default three seconds); direct stream previews can refresh faster. Existing bounded timeouts/retries apply. Optional existing credential variables are `PARKING_CAMERA_USERNAME`, `PARKING_CAMERA_PASSWORD`, and snapshot-only `PARKING_CAMERA_HEADERS`. Addresses and credentials are not echoed or saved by the viewer.

The viewer displays retrieval and capture times, with unknown capture time explicitly labelled. Failed, expired or stale frames clear the preview. Disconnect invalidates late packets. If an earlier connection is still stopping, wait for its bounded read to finish before reconnecting.

**This tab provides live viewing only; live occupancy is unavailable.** A new camera needs its own polygons, empty references and calibration; CHAD settings cannot be transferred automatically. Existing camera setup/analysis commands remain in README. No authorized external parking camera is configured, so external live parking validation remains outstanding. Synthetic local HTTP snapshot and MJPEG tests verify the viewer without claiming real parking-camera access.

## Launch modes and implementation

`main.py` and `--dashboard` open the interface. `--video chad-4`, `--video chad-camera-2` or `--video overhead-1` chooses the initial video; preparation still includes both sites. `--no-autostart` waits for Prepare recordings. `START_VIDEO` selects the initial recording, while `RUN_ALL_VIDEOS` applies only to terminal mode.

`--terminal` restores the earlier timed console comparison; append `--video chad-2` for one clip. Existing `--fast`, `--frames`, `--site` and `--headless` also select terminal behavior for compatibility. `--terminal --help` lists terminal options. `--check` remains the basic diagnostic. `--legacy-dashboard` opens the earlier reference-only window.

`src/parking_probe/interface.py` implements the window, local decoder and live worker. `interface_model.py` implements time/recording selection and chart data. `areas.py` defines sites, recordings, inventories, area reports and the additional sources. `view_presets.py` prepares per-view recipes; `yolo.py` provides selective YOLO inference, bounded job handling and the final decision rule; `registration.py` aligns the overhead view. `vehicle.py` remains legacy SSD code. `main.py` and `.vscode/launch.json` select the default. The previous `desktop.py` remains available unchanged.

`tests/test_interface.py` and `tests/test_areas.py` test arithmetic, inventory IDs, missing/unknown evidence states, site separation, past-only selection, stale/error states, disconnection, bounded queues and local snapshot/MJPEG decoding. `checks/check_interface.py` runs actual analysis and verifies all eight video decoders, final counts, seeking, pause/resume, tab switching all 69 overhead bays, guarded registration, selective routing and preserved definite agreement. It captures only its own application window for visual inspection. Reports/screenshots are in `runs/verification/`. See [WORK_LOG.md](WORK_LOG.md) and [VALIDATION.md](VALIDATION.md) for measured results.
