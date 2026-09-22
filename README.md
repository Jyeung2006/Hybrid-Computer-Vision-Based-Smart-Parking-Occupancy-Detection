# Parking occupancy prototype

**Separate external validation:** run `.\.venv\Scripts\python.exe checks/evaluate_pklot.py` for the saved, day-separated PKLot UFPR04 experiment. See [EXTERNAL_VALIDATION.md](EXTERNAL_VALIDATION.md) for measured branch/profile/weather metrics and calibration counts. This checks-only track leaves the application and CHAD/overhead calibration unchanged; outdoor PKLot results are not their accuracy results.

**22 September audit:** the original three calibrated CHAD bays retain all 117 Reference/MOG2 observations unchanged. Additional mapped bays have incomplete reference/calibration coverage. Both active profiles are YOLOv8s (small). See [MAPPING_CALIBRATION_AUDIT.md](MAPPING_CALIBRATION_AUDIT.md) for the per-view table, exact models and score/mapping checks.

**Open `main.py` in VS Code and press Run** for the parking areas, circle chart and video interface. Choose **Site → Overhead demo car park** to monitor **all 69 visible bays**, split into west (24), middle (22) and east (23). CHAD Cameras 1/2/3/4 still monitor 9/5/4/3 bays respectively. See [QUICK_START.md](QUICK_START.md) for the brief guide.

Every three video seconds, the table shows **Reference / MOG2 / YOLOv8 / Final estimate**. Matching definite Reference/MOG2 states are kept. Either uncertain/unknown or disagreement sends the bay to one shared full-frame YOLOv8s pass. A strong uniquely assigned vehicle detection can establish occupied; missing detections alone remain uncertain. Final vacancy requires definite Reference/MOG2 agreement. The undisplayed empty-image override has been removed; repeated unresolved results cannot establish vacancy. See [DECISION_FIX.md](DECISION_FIX.md). Ten-second summaries cover every mapped bay. See [YOLOV8.md](YOLOV8.md) for the exact rule and proposal scope.

The last tested overhead sample has **48 occupied, 2 vacant and 19 uncertain out of 69**, giving a 69.6–97.1% occupancy range. These are experimental recorded estimates, not ground truth or live availability. All bays are mapped, but 66 still lack full two-state classic calibration. Fifteen overhead bays have reviewed empty images, retained for calibration; the separate empty-only heuristic no longer determines Final. See [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md) and [FINAL_RESULTS.md](FINAL_RESULTS.md).

Video URLs are built in, cached media and two ONNX model profiles are already available here, and no API key or extra installation is needed on this computer. Normal inference uses **Python 3.12 / OpenCV DNN CPU**. Standard YOLOv8s COCO weights serve CHAD; aerial-trained YOLOv8s weights serve the overhead clip. Model sizes/hashes, source credits and the optional conversion recipe are documented in [third_party/YOLOV8-SOURCES.md](third_party/YOLOV8-SOURCES.md). Initial preparation took about **2–3 minutes** in recent reference-preparation/replay checks; then playback reveals saved chronological analysis.

The overhead camera's small drift is corrected with guarded registration, keeping all ten sampled frames usable. The chart and video show all 69 polygons. Large changes and unusable images still fail validation. CHAD cross-view IDs are manually mapped; overlapping inventories and unsynchronized periods are never summed as one live total. The optional Live camera tab remains a viewer requiring an authorized endpoint.

**Application validation:** the prior 244 automated tests passed; actual interface checks processed all eight recordings and 1,088 bay observations without source issues or callback errors. Independent CHAD/overhead accuracy and false-vacant/false-occupied rates remain unmeasured. Full application evidence is in [VALIDATION.md](VALIDATION.md); changes and details are recorded in [WORK_LOG.md](WORK_LOG.md). PKLot has its own external evaluation and additional tests linked above.

The current correction makes every definite final decision traceable to the displayed methods. Logistic probability fusion, temporal confirmation, persistence/database, Flutter, API server and deployment remain deferred. The earlier MobileNet-SSD supplement and terminal modes are preserved for historical comparison. The rest of this README describes those earlier commands and the original calibrated baseline where stated.

## Run and read the terminal output

This earlier mode retains its **three calibrated CHAD bays** and four Camera 1 recording periods. Its results exclude the six additional mapped bays and the additional source; use the interface for the full mapped inventory and area display.

```powershell
.\.venv\Scripts\python.exe main.py --terminal  # All four recordings, both methods
.\.venv\Scripts\python.exe main.py --terminal --video chad-4
# Stop after five sample ticks across active recordings (0, 3, 6, 9, 12 seconds):
.\.venv\Scripts\python.exe main.py --frames 5
# Verification only: retain the sampled video times but skip wall-clock waits.
.\.venv\Scripts\python.exe main.py --fast
# Original library/decoding/playback diagnostic, without occupancy:
.\.venv\Scripts\python.exe main.py --check
```

Each three-second table shows recording ID, physical bay ID, REFERENCE state and normalized difference, MOG2 state and foreground percentage, and method agreement. Ten-second tables show each method's latest state and estimated occupied-time percentage/range. Counts below the table are separate for each recording and method. Time rates summarize the preceding window; they are not probabilities. Ctrl+C stops playback. A shorter recording finishes while others continue. Exact frame positions and processing timings remain in JSON/CSV.

At the end, a final historical table reports occupied/vacant only when both methods agree, uncertain for mixed/incomplete evidence, and unknown if both are unavailable. It uses each recording's last sampled frame and saves final-summary.json/csv. This is an experimental consensus estimate, not a calibrated probability or temporally confirmed state.

Only **CHAD-P001–CHAD-P003**, mapped from local polygons B01–B03, contribute to each recording's three-bay total. Other visible bays and the foreground SUV are excluded. OCCUPIED and VACANT are feature-threshold decisions. UNCERTAIN includes between-threshold evidence or an uncalibrated/restabilizing MOG2 model. UNKNOWN indicates unusable frame/reference evidence. Unresolved time produces ranges. All four clips show different periods from one camera, so counts are never added into an apparent twelve-space car park. The same bay can correctly have different states in different recordings.

The earlier custom multicamera mode remains available through `python main.py --site site.local.json`, using the reference method. It maps multiple polygons to one physical bay and leaves conflicting views uncertain. Configure [site.example.json](site.example.json) as explained in [MULTICAMERA.md](MULTICAMERA.md). That mode requires synchronized footage; the built-in comparison uses independent recording periods. Automatic cross-view identity recognition and real multicamera accuracy remain unvalidated.

The supplied four public recordings are from the same elevated outdoor parking camera. Their addresses, archive members and checksums are in `src/parking_probe/catalog.py`; no URL or API key input is needed. Already verified local videos are reused offline. `test_video.cmd` opens the new interface; `test_video.cmd --terminal` selects text output.

## Calibration and outputs

The following describes the original CHAD analysis. Interface runs save all views under **`runs/areas/<UTC-time>/`**, with `chad/`, `chad-camera-2/`, `chad-camera-3/`, `chad-camera-4/` and `overhead/` subfolders, alongside inventory, source-status and displayed area-summary JSON. All interface sources now save YOLO and Final branches; the expanded setup is documented in [YOLOV8.md](YOLOV8.md) and [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md). Terminal runs retain `runs/comparison/`. See [PARKING_AREAS.md](PARKING_AREAS.md) for the overhead recipe and inventory history.

The first three selected recordings provide the supplied reference and calibration frames. Recipe version 2 contains **99 labelled bay examples across 39 distinct full frames**, selected after visual inspection to cover more of each recording. There are 10/25 vacant/occupied examples for B01, 21/11 for B02 and 26/6 for B03. Video 4 is excluded from calibration. The minimum remains five examples per state, with the 95th percentile of vacant scores and 5th percentile of occupied scores as boundaries.

The existing grayscale/Gaussian masked absolute-difference method, empty references, polygons and alignment guards are unchanged. Missing references and invalid or overlapping calibrations remain unknown. The generated preset is versioned by recipe, source checksums and OpenCV version; old presets remain available. See `presets/chad-camera-1.json` and [VIDEO_SOURCES.md](VIDEO_SOURCES.md) for the exact sample times and visual review.

MOG2 uses one full-frame stateful model per recording, initialized with a mosaic of the same verified empty bay references. It updates once per valid chronological sample, excludes shadow labels, applies 3×3 opening/closing and scores the cleaned foreground fraction in each bay. Its own percentile calibration uses the same reviewed labels with chronological runtime updates and read-only probes at extra labelled times. Settings, provenance, measured thresholds and stationary-object/background-adaptation limitations are documented in [MOG2.md](MOG2.md). A MOG2-only failure preserves usable reference evidence.

Terminal replay targets 0, 3, 6, 9... seconds on a monotonic clock and samples the nearest source frames. Summaries close independently at 10, 20, 30... seconds. Overdue samples produce unknown; the final short window is explicitly partial. Processing/writing can introduce timing jitter, recorded as late_by_seconds. The interface precomputes chronological samples before recorded playback and reveals each result/window only when its video time is reached. This is not a hard real-time service.

Default outputs go to `runs/comparison/<UTC-run-time>/`: paired `observations.csv`/`history.jsonl`, `windows.jsonl`, `summary.csv`, `bay-windows.csv`, calibration and run metadata. Each `chad-N/reference/` and `chad-N/mog2/` folder contains annotated `latest.png` and per-frame JSON/CSV; MOG2 also saves the cleaned `foreground.png`. Each clip has `latest-window.json`. Capture time remains unknown; received_at is local decode time. Top-level latest.json marks current occupancy unavailable after the run ends; timestamped history is retained. Custom --site mode still writes `runs/sites/...`, and the older dashboard writes `runs/chad/...`.

The generated configuration, reference/sample PNGs, label manifest and both calibration reports are under `data/chad/preset-<signature>/`. Demonstration replay is not independent accuracy evaluation. Reference decision coverage across the four clips is 91.45%; MOG2 coverage is 82.05% in the measured run. Neither is accuracy. Independent labels/periods are still required to measure accuracy and false-vacant/false-occupied rates.

## Interface and earlier dashboard

Normal Run and `--dashboard` open the new chart/video interface; see [INTERFACE.md](INTERFACE.md). The earlier reference-only window remains available separately:

```powershell
.\.venv\Scripts\python.exe main.py --legacy-dashboard
.\.venv\Scripts\python.exe main.py --legacy-dashboard --video chad-4
```

It includes a camera preview, count cards and reference-method states/scores. It remains a single-recording, reference-only display and is not launched by normal Run.

## Legacy single-area indoor demo (optional)

The earlier 23-second Pexels example is retained through the CLI below. Its low-angle view measures one test region, not clearly marked parking bays. Its recorded results in the validation document are historical, from 10 September. It uses a different interval and output directory from the new `main.py` display.

```powershell
.\.venv\Scripts\python.exe -m parking_probe demo
.\.venv\Scripts\python.exe -m parking_probe demo --headless
```

`demo` ignores `--config` and camera environment variables. Its reviewed public URL, SHA-256, polygon and label times are in `src/parking_probe/video_demo.py`. Each run recreates its generated preset under `data/video-demo/indoor-v1`, leaving `config.local.json` and camera references alone. Do not edit the generated preset expecting changes to survive another demo run.

The default sample interval is about 0.5 video seconds, rounded to whole frames (0.5005 seconds for this clip). Live sampling remains three seconds by default. Use `--step 1` for fewer recorded samples, `--frames 10` to stop early, or `--out runs/my-new-demo` for an empty output directory. Omitting `--out` creates a separate timestamped run in `runs/demo-indoor`.

Each run saves `annotated.mp4`, `latest.png`, `latest.json`, `history.jsonl`, `summary.csv`, `slots.csv` and `run.json`. The video is sampled, silent, and may play less smoothly than the original. `run.json` records completion versus early stopping and aggregate latency/state counts. Normal end-of-file is completion, not a stale-camera error. Download/decode failures never assert current occupancy.

Recorded results include `input_mode=recorded_video`, `monitoring_scope=test_regions`, `video_frame_index`, `video_position_seconds` and `video_duration_seconds`. `received_at` means local frame decode time. `source_captured_at` and `frame_age_seconds` remain null because the original recording time is unknown. Download time is stored separately in `data/video-demo/indoor-v1/download.json`. In this demo, `total_monitored_regions=1` and `total_monitored_bays=0`; counts and rate bounds refer to that one region.

The reference is frame 0. Five empty examples at 0.5, 1, 1.5, 2 and 2.5 seconds and five occupied examples at 14, 15, 16, 17 and 18 seconds supply the agreed percentile calibration. See the generated `review-labels.png`. All examples come from the same clip, so playback is a demonstration, not held-out evaluation. The existing evaluation command continues to reject reuse of reference/calibration images or sessions.

Source: [Ricky Esquivel / Pexels](https://www.pexels.com/video/a-car-stopping-in-a-parking-lot-4707190/), under the [Pexels license](https://www.pexels.com/license/). This legacy indoor demo uses only the recorded media. The separate CHAD interface now also uses the approved MobileNet-SSD model.

## Getting started on Windows

Use PowerShell from this project folder. A Python 3.12 environment is already installed here. To recreate it on another computer, install Python 3.12 from [python.org](https://www.python.org/downloads/windows/), then run:

```powershell
.\setup.ps1
.\run.ps1 --help
```

The setup script creates `.venv`, installs the tested dependency versions, and copies `config.example.json` to `config.local.json` only if the local configuration does not already exist. It does not change your PowerShell execution policy. If your machine blocks scripts, use `.\.venv\Scripts\python.exe -m parking_probe` instead of `.\run.ps1`.

The dependency versions used for verification are recorded in `requirements-tested.txt`. Reproduce them with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

## 1. Connect an authorized existing camera

Obtain an operator-authorized direct image or live-stream URL for a fixed indoor parking view. A normal webpage containing a video player is not a camera endpoint. No hardware installation or ONVIF discovery is performed.

In `config.local.json`, set `source.type` to `snapshot` for an HTTP JPEG/PNG endpoint, or `stream` for an operator-confirmed HTTP MJPEG/HLS or RTSP stream. OpenCV's installed FFmpeg backend handles streams; actual codec/provider compatibility needs testing with the selected camera. Snapshot endpoints support custom headers and HTTP Basic authentication. Streams support URL credentials or the username/password environment variables, but not custom HTTP headers.

Set the address in your current PowerShell session. In PowerShell 7, masked input avoids printing a signed URL or token:

```powershell
$env:PARKING_CAMERA_URL = Read-Host 'Authorized camera URL' -MaskInput
```

If required, set credentials or an HTTP header JSON object using the same approach:

```powershell
$env:PARKING_CAMERA_USERNAME = Read-Host 'Camera username' -MaskInput
$env:PARKING_CAMERA_PASSWORD = Read-Host 'Camera password' -MaskInput
$env:PARKING_CAMERA_HEADERS = Read-Host 'Header JSON, for example an Authorization or X-API-Key header' -MaskInput
```

Leave unnecessary environment variables unset. They are read from the current process environment; `.env` files are **not** loaded automatically. Do not put secrets in the configuration or command arguments. Error logs omit URLs, credentials, response bodies, and raw network exceptions. HTTP redirects are rejected; configure the provider's final endpoint. TLS verification stays enabled.

If the provider explicitly supplies a frame-capture timestamp header, set `source.capture_time_header` to its name. Supported formats are timezone-aware ISO 8601 and HTTP date format. Do **not** use the ordinary HTTP `Date` header as a camera capture timestamp unless the provider documents that meaning.

```powershell
.\run.ps1 check --count 3
```

Read `runs/connection-check.json`. Successful decoding does not prove that the image is current, that the camera is indoors, or that its bay visibility is adequate. Inspect the source and capture images before continuing. An unchanged image might be a quiet scene or a frozen feed; without source timestamps the prototype cannot distinguish those reliably.

## 2. Capture and mark the view

```powershell
.\run.ps1 capture --session setup --count 1
```

The command prints a saved PNG path under `data/captures/setup`. Its adjacent JSON contains source and retrieval metadata. Use that actual PNG path below:

```powershell
.\run.ps1 configure --frame 'data/captures/setup/YOUR_FRAME.png' --slot P01
.\run.ps1 configure --frame 'data/captures/setup/YOUR_FRAME.png' --slot P02
```

Click each bay's corners in order. Right-click removes the last point, Enter saves, and Escape cancels. Mark only clearly visible bays; the occupancy denominator is the number you configure, not the whole garage's capacity. Leave stable background detail outside the bay polygons so alignment can be checked.

For a headless setup, import a JSON list using `configure --frame ... --polygons-file polygons.json`:

```json
[{"id": "P01", "polygon": [[100,150], [240,150], [240,300], [100,300]]}]
```

These example coordinates are illustrative and must be replaced with coordinates from your camera. Editing a polygon clears that bay's reference and calibration. A different setup view requires a new configuration file.

## 3. Save each bay's empty reference

Capture a frame when a particular bay is visibly empty. Different bays can use references captured at different times. After inspecting the relevant bay:

```powershell
.\run.ps1 capture --session references --count 1
.\run.ps1 reference --slot P01 --frame 'data/captures/references/YOUR_FRAME.png' --confirm-empty
```

Repeat for each bay. The assertion is manual; the software does not decide that its own reference is empty. References are never updated automatically. A changed reference invalidates its calibration.

## 4. Label samples and calibrate

Collect a recording period containing both vacant and occupied examples:

```powershell
.\run.ps1 capture --session calibration-morning --count 30
```

Inspect and label the captured PNGs. One command can label multiple bays in a frame:

```powershell
.\run.ps1 label --frame 'data/captures/calibration-morning/YOUR_FRAME.png' --session calibration-morning --labels P01=vacant P02=occupied --manifest data/calibration.csv
.\run.ps1 calibrate --manifest data/calibration.csv
```

Continue until each bay has at least five unique vacant and five unique occupied samples. More varied examples are preferable to adjacent near-identical images. Use `ambiguous` for ground truth you cannot determine; those observations are excluded from fitting and binary accuracy metrics. CSV columns are `frame_path,slot_id,label,session_id`; image paths are relative to the CSV. You can edit this CSV directly to correct labels.

The pipeline converts the image to grayscale, applies a 5×5 Gaussian filter, and computes the mean absolute difference inside the bay divided by 255. The vacant boundary is the 95th percentile of vacant sample scores; the occupied boundary is the 5th percentile of occupied scores. Scores at the lower boundary are vacant; scores at the upper boundary are occupied; scores between them are uncertain. If boundaries overlap or samples are insufficient, the bay remains uncalibrated/unknown. No arbitrary default occupancy threshold is used.

Camera resolution, stable background features, polygon definition, reference image, and preprocessing version must match. ORB feature matching and a RANSAC transform check alignment outside the bays; by default at least 12 inliers, 50% inlier ratio, background coverage in both dimensions, and no more than 8 pixels of corner displacement are required. Alignment failure pauses interpretation; the program does not move polygons or replace references to hide a change. Feature-poor or obstructed backgrounds may remain unavailable.

## 5. Run the experiment

```powershell
.\run.ps1 run --frames 20 --preview
```

`--frames 0` runs until Ctrl+C or Q in the preview. Omit `--preview` for a terminal-only run. The default interval is three seconds; increase it to match the provider's permitted frequency. No requests overlap. Slow retrieval stretches the effective interval.

Saved under `runs/live`:

| File | Contents |
| --- | --- |
| `latest.png` | Annotated frame, bay IDs/states, timestamps and occupancy summary |
| `latest.json` | Latest structured per-frame result, including failure states |
| `history.jsonl` | Timestamped history of full results |
| `summary.csv` | Counts, occupancy bounds, timing and source health per attempt |
| `slots.csv` | Per-bay state, appearance difference score and reason |

Only the latest annotated image is retained during a run. Each history file rotates at approximately 10 MiB with three backups. Explicitly captured setup/evaluation frames remain in `data` until you remove them. Treat these as local research files.

Occupancy is `occupied / total monitored bays × 100` only when all bays are classified. Otherwise the lower bound is `occupied / total` and the upper bound is `(occupied + unresolved) / total`; uncertain and unknown bays count as unresolved. The software never silently counts unknown bays as vacant.

`source_captured_at` and `frame_age_seconds` are null when unavailable. `received_at`, processing start/end time, retrieval age, and processing duration are recorded separately. Timestamps use UTC with an explicit offset. `freshness_basis: retrieval_only` means source freshness is unverified. Frames older than the default 15 seconds are stale when their age can be established; timestamps over five seconds in the future are rejected.

Retrieval errors make current occupancy unavailable and write a fresh error panel instead of retaining a misleading current percentage. Historical successful results remain timestamped in the logs. Three attempts are allowed by default, with 1- and 2-second backoffs. Snapshot workers enforce a total attempt deadline of connect timeout + read timeout + 3 seconds of startup allowance; stream workers have a connect + read deadline. Stalled workers are terminated and stream buffers are bounded to one pending frame. These are experimental estimates, without temporal confirmation or persistence services.

## 6. Evaluate real performance when access is available

Collect and manually label at least 30 distinct frames from at least two new recording periods, with both occupied and vacant ground truth. Use new session IDs and place their labels in `data/evaluation.csv`:

```powershell
.\run.ps1 evaluate --manifest data/evaluation.csv --out runs/real-evaluation.json
```

Reference and calibration image content cannot be reused for evaluation. Calibration/evaluation session IDs must not overlap; keeping adjacent frames from the same real event in one partition is your responsibility. Evaluation reports accuracy **on classified observations**, decision coverage, false-vacant/false-occupied counts and rates, ambiguous exclusions, and median/p95/max processing latency. Error-rate denominators are explicitly named in the JSON. A structurally sufficient CSV does not independently prove its labels or recording-period provenance.

For a single saved image diagnostic, use `analyze-image --frame ...`. Its output is explicitly marked offline. That command and the synthetic verification below are not substitutes for the required live indoor test.

## Tests and limitations

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_prototype.py
```

The second command generates controlled test patterns under `runs/self-test`; it never contacts a real camera. Its report is explicitly synthetic.

Appearance differences can be caused by cars, people, objects, shadows, glare, wet surfaces, or lighting changes. This baseline cannot reliably distinguish those causes. The empty reference and calibrated boundaries are view-specific. Small controlled samples establish software behavior, not real-world parking accuracy. No real camera performance or public API availability is claimed.

Exit codes: `0` completed; `2` invalid input, source/analysis failure, incomplete calibration, or insufficient evaluation dataset; `130` stopped with Ctrl+C. An uncertain/unknown bay alone does not fail a run when acquisition and view validation work.

## Source research and backend choice

The user's requirements are live indoor footage from an authorized existing camera, without installing camera hardware. The [Toronto underground webcam listing](https://camguide.net/canada/ontario/toronto/parking/) was inspected during planning; its embedded player reported that the camera was no longer available publicly. It is not configured as an input.

[Pexels](https://www.pexels.com/api/) offers recorded stock media and [personal API keys](https://help.pexels.com/hc/en-us/articles/900004904026-How-do-I-get-an-API-key); [PKLot](https://web.inf.ufpr.br/vri/databases/parking-lot-database/) provides labelled outdoor research images. They do not satisfy the selected live indoor requirement and are not used here. An API key from a media catalogue would not by itself grant access to a suitable camera.

Python keeps image acquisition, numerical work and [OpenCV operations](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html) in one small program. It remains a suitable language for a later FastAPI backend, but no app/backend service implementation is included in this stage. The proposal supplied context; its broader architecture and document instructions did not expand this implementation's scope.
