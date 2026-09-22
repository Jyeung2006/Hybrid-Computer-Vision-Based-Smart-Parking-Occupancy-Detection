# Physical bay identity and ten-second summaries

**Mode distinction:** normal Run opens the chart/video interface for four actual CHAD views with Reference, MOG2, YOLOv8 and Final columns. P009 has a shared manual mapping; asynchronous clips are not fused. Selective verification is detailed in [YOLOV8.md](YOLOV8.md); the overhead site now covers [69 bays](OVERHEAD_MAPPING.md). See [CAMERA_MAPPING.md](CAMERA_MAPPING.md). This page documents the earlier **--site site.local.json** synchronized-camera mode, which remains reference-only.

## What is implemented

A physical bay has one permanent ID in a site registry. Each camera has its own polygon and reference for that bay. For example:

| Camera | Local polygon ID | Physical bay ID |
| --- | --- | --- |
| camera-a | A01 | P001 |
| camera-b | B07 | P001 |
| camera-a | A02 | P002 |
| camera-b | B08 | P003 |

This is **three physical bays**, seen through four polygons. The software counts P001 once. The mapping is entered after visual inspection of bay markings, position and a site plan if available. It does not automatically recognize matching spaces across unfamiliar views or identify individual vehicles. Similar-looking spaces alone are insufficient evidence that they are the same bay.

The built-in recordings use CHAD-P001/CHAD-P002/CHAD-P003 for local B01/B02/B03. These IDs remain the same in all four CHAD clips. They show one physical camera during different periods. The original terminal comparison keeps those recordings separate; it does not validate cross-camera identification or fuse their states.

## How camera results are combined

Each camera first runs the existing OpenCV reference comparison with its own calibration. Only fresh, usable observations for the same relative recording time are considered.

| Observations for one bay | Fused result |
| --- | --- |
| All usable views occupied | Occupied |
| All usable views vacant | Vacant |
| At least one occupied and another vacant | Uncertain: views disagree |
| Any usable view uncertain | Uncertain: view uncertain |
| Only one usable view, others unavailable | Use that view, explicitly flag missing view(s) |
| No usable view | Unknown; never count as vacant |
| Usable frame times differ by more than 0.1 seconds | Uncertain: views not synchronized |

Three cameras do not outvote a conflicting fourth camera. Raw appearance-difference scores are preserved per view, but never averaged into a probability: cameras have different perspectives, references and thresholds. This conservative policy makes conflicts visible. It does not guarantee that agreeing cameras are correct.

VIEWS 1/2 means one of two mapped views is usable, not 50% confidence. Missing/failed views are recorded with their reasons. A remaining usable view is an experimental fallback. Observations older than 1.5 sampling intervals are unusable; a missed scheduled sample immediately supplies unknown for that tick. Source capture date/time remains unknown for these recordings.

## Meaning of the rate and ten-second window

The terminal prints estimates at video times 0, 3, 6, 9, 12... seconds. It closes windows at **10, 20, 30... seconds**, independent of those sample times. Normal replay waits on a monotonic clock; --fast skips waits solely for verification.

A window is [start, end). A sample exactly on a ten-second boundary belongs to the next window. The most recent sampled state is held until the next observation, camera end or failure event. This estimates time between samples; actual changes within a three-second gap are unobserved. The implementation does not add the proposal's confirmation/persistence stages.

For each physical bay:

- **Latest state**: the final fused decision before the window ends. Counts below the table use these states, counting each physical bay once.
- **Occupied time**: occupied seconds / actual window seconds × 100.
- With unresolved time, show a range from occupied seconds / duration to (occupied + uncertain + unknown seconds) / duration.
- **Classified**: (occupied + vacant seconds) / duration × 100. This is decision coverage, not accuracy.

Example: a bay occupied for six sampled seconds, uncertain for three, then vacant for one has latest state **vacant**, occupied time **60–90%**, and classified time **70%**. Majority voting over the window would obscure the most recent departure.

Site occupancy at window end is occupied bays / total monitored bays if all are resolved; otherwise it is a range including uncertain/unknown bays. If every bay is unknown, current site occupancy is unavailable. Historical occupied-time bounds can still show 0–100% when a whole window was unknown; this means no resolved evidence, not a measured 50%.

A final incomplete window is labelled with its actual duration. CHAD Video 1 lasts 29.996633 seconds, so its last window is 9.996633 seconds. Displayed clocks round to whole seconds; exact times remain in JSON. Decode/reporting work and OS scheduling can delay a report; each summary records late_by_seconds. Late replay ticks produce unknown instead of reusing earlier decisions.

## What to do for actual multiple-camera testing

The existing demo requires no setup. For additional views:

1. Obtain two or more authorized **fixed-camera recordings from the same car park and same period**, with shared visible bays. Different periods cannot be fused.
2. Prepare a separate normal parking configuration for each camera using the README's polygon, empty-reference and calibration commands. Set source_id to the matching camera ID, and source type to recorded_video. Use the correct setup image resolution. Each view needs its own polygon/reference and at least five vacant and five occupied calibration examples per bay; do not copy another camera's thresholds. Existing CLI commands also accept saved video frames as PNG files. Example: `python -m parking_probe --config data/camera-a/config.json configure --frame data/camera-a/setup.png --slot A01`.
3. Copy **site.example.json** to **site.local.json**. Set each local video path, calibration-config path and [width, height] sizes. Paths are relative to the site JSON. source_resolution is the original decoded size; analysis_resolution must match that camera's calibrated setup image. Original frames are checked before resizing.
4. Assign slot_map values after verifying the physical bays. In the example, A01 and B07 both map to P001. Include every configured polygon exactly once. Give different physical cameras different IDs; do not duplicate a recording as another camera. Mark mapping_verified true only after inspection.
5. Choose a common start instant. video_offset_seconds is the position in that file corresponding to site time zero. For example, offsets 5 and 2 align camera-a's second 5 with camera-b's second 2. Both videos must cover that real instant. Record how this was established in the synchronization note, then set synchronization.verified true. Filenames and file creation times do not establish synchronization. The program checks numerical offsets but cannot verify an operator's assertion; drifting/variable-rate footage needs additional timestamp validation.
6. Run:

```powershell
.\.venv\Scripts\python.exe main.py --site site.local.json
```

The example starts unverified and has placeholder paths. It is not a ready-to-run two-camera dataset. The four built-in clips should not be entered as separate cameras. There is no automatic discovery, live multistream connector, tracking, machine-learning detector or new dashboard in this extension. The existing single-camera live CLI remains available separately.

## Saved results

Each Run creates runs/sites/&lt;site-id&gt;/&lt;UTC-run-time&gt;/:

| File | Meaning |
| --- | --- |
| site.json | Physical IDs, view mapping, local file paths and synchronization assertion used |
| history.jsonl / latest.json | Fused snapshots, per-view decisions/scores, timestamps and view health |
| windows.jsonl / latest-window.json | Historical windows, per-bay state seconds, rates and counts |
| summary.csv | Window boundaries, unique-bay counts and site occupancy bounds |
| bays.csv | Per-bay durations, rates, coverage, state and view support |
| cameras/&lt;camera-id&gt;/ | Per-camera JSON, CSV and annotated PNG with physical bay IDs |
| run.json | Camera/sample/window counts, skipped ticks/errors, status and elapsed time |

At EOF/stop/failure the fused latest result becomes unavailable and run_active=false; previous estimates remain timestamped history. latest-window.json is the last **historical** summary. A shorter camera becomes unavailable when its recording ends, while remaining recordings continue. A failed camera does not prevent a usable camera from supplying a flagged fallback. Decode failures do not replace references or silently reuse old occupancy.

Real cross-camera correspondence, agreement accuracy, false-vacant/false-occupied rates and the planned independent 30-frame evaluation remain unmeasured. Automated two-video fixtures test software behavior, not real-world accuracy. See [VALIDATION.md](VALIDATION.md) and [WORK_LOG.md](WORK_LOG.md).
