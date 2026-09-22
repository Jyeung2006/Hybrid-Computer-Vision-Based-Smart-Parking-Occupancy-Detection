# Parking sites, camera views and areas

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.

## Current selective-YOLO implementation — 19 September 2026

Normal Run now uses **Reference / MOG2 / YOLOv8 / Final estimate**. Matching definite classic results are retained; uncertain, missing or conflicting evidence triggers YOLOv8s. No qualifying detection remains uncertain. This supersedes the earlier SSD Vehicle/empty-bank decision rule and its vacancy counts below. CHAD mappings remain 9/5/4/3 bays across Cameras 1/2/3/4; overlapping periods are not fused.

The overhead site now maps **all 69 visible painted bays**, divided west 24 / middle 22 / east 23. Guarded registration corrects this clip's small drift; all ten samples remain usable. Only three bays have full classic calibration; YOLO verifies the others. The former three-bay subset and later-drift failure below are historical.

Current details: [YOLOV8.md](YOLOV8.md), [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md), [FINAL_RESULTS.md](FINAL_RESULTS.md), [QUICK_START.md](QUICK_START.md). YOLO verification is now implemented; later probability fusion, temporal confirmation and persistence remain deferred.

## Earlier implementation and source history

The following dated record preserves the prior algorithms, measurements and source research. Its descriptions of no YOLO, Vehicle fallback, three overhead bays and unavailable later overhead frames are superseded above.

## Current behavior — 19 September 2026

All four CHAD views now have analyzed polygons: Camera 1 has 9 bays; Cameras 2/3/4 have 5/4/3. Reference and MOG2 remain visible, supplemented by the approved OpenCV Vehicle branch and a Final estimate. P009 is manually shared across all views; Camera 2/3 far-row identities remain view-local. Recordings are not synchronized and counts are never summed across overlapping views. See [CAMERA_MAPPING.md](CAMERA_MAPPING.md), [FINAL_RESULTS.md](FINAL_RESULTS.md) and [QUICK_START.md](QUICK_START.md) for current mappings, measured results and use.

The overhead site's subset/drift limitations below still apply. Current runs include separate subfolders for Cameras 2–4. Areas follow the selected CHAD view/recording and retain its sample time.

## Historical source and implementation record — 18 September

The following describes the earlier state before the approved Vehicle supplement. Statements about view-only cameras, six pending final states and two-method consensus have been superseded above.

Updated **18 September 2026**. Normal Run now supports two car parks, actual CHAD camera-angle selection, and an area availability table. See [QUICK_START.md](QUICK_START.md) for the short usage guide.

## Correcting the four-video labels

The [CHAD authors](https://github.com/TeCSAR-UNCC/CHAD) provide four camera views. The four previously selected videos were all from **camera 1**, recorded at different times. Their old CHAD 1–4 labels were recording numbers, not camera numbers. The new interface separates **Site**, **View** and **Recording**, displaying the actual filename.

| Site / camera | Included recordings | Occupancy support |
| --- | --- | --- |
| CHAD / Camera 1 | `1_029_0.mp4`, `1_038_0.mp4`, `1_049_0.mp4`, `1_054_0.mp4` | Three calibrated bays; nine-bay visible inventory |
| CHAD / Camera 2 | `2_036_0.mp4`, 15.00 s, 1920×1080 | View only |
| CHAD / Camera 3 | `3_073_0.mp4`, 9.64 s, 1920×1080 | View only |
| CHAD / Camera 4 | `4_075_0.mp4`, 4.97 s, 1280×720 | View only |
| Overhead demo / Overhead camera | `carPark.mp4`, 28.29 s, 1100×720 | Two calibrated bays; three-bay demonstration inventory |

All eight recordings were downloaded/cached and successfully decoded in the interface check. The three additional CHAD clips total about 67.65 MB. The existing downloader fetched only their ZIP byte ranges; it did not download the roughly 87.97 GB archive. Pinned sizes, offsets, CRCs and SHA-256 hashes are in `src/parking_probe/areas.py`; the original four remain in `catalog.py`.

Although CHAD was recorded with multiple cameras, these selected clip numbers have **not** been matched to the same capture period. Do not fuse them as simultaneous views. The new angles require their own polygons, verified shared bay correspondence, empty references and calibration. Merely selecting another camera does not infer physical bay identity.

## Nine visible CHAD bays

Camera 1 has seven identifiable far-row bays and two near-row bays. IDs P001–P003 retain their existing meanings and calibration. The near bays are partially clipped at the bottom; unidentified edge slivers are excluded. Nine is the mapped visible inventory, not the entire site's capacity.

| Area | Physical bay IDs | Calibration |
| --- | --- | --- |
| CHAD / Far row | CHAD-P001–CHAD-P007 | P001–P003 calibrated; P004–P007 pending |
| CHAD / Near row | CHAD-P008–CHAD-P009 | Both pending |

Pending bays have polygons and stable IDs, but both methods and the final estimate stay **unknown**. They contribute to the chart denominator and unresolved range, never to known-vacant counts. At Camera 1 recording `1_029_0.mp4`, sample 27 s, the display gives **1 occupied, 2 vacant, 6 unknown out of 9**, or **11.1–77.8% occupied**. The three calibrated bays retain their previous results.

These short videos do not supply verified empty and occupied examples for all nine bays. To enable another bay, obtain a verified empty reference plus at least five distinct empty and five occupied calibration examples, separately from its reference. Keep the same view and valid alignment. Do not label a bay vacant merely because it has no calibration.

## A different car park

The integrated overhead recording comes from [Harsh Bafna's parking detection repository](https://github.com/harshbafnaa/car-parking-detection). The README credits inspiration to Murtaza's Computer Vision Zone. The code contains this [pinned direct MP4 link](https://raw.githubusercontent.com/harshbafnaa/car-parking-detection/a35ce5055beb2d50eac971254720892944e0f7fb/carPark.mp4); no API key or manual URL entry is required.

- Local file: `data/other-parking/carPark.mp4`, 10,607,736 bytes, 679 frames at 24 fps.
- SHA-256: `f2d804e9b2e8ff7e0ae9776068a9cbc8126b6bce2e09ef6f56d3ad9c8fe84069`.
- Download verification: bounded requests/deadline, exact byte cap and SHA-256 before atomic cache replacement.
- Only the video is used. No external detector, model or pickle is loaded. See `third_party/OVERHEAD-SOURCE.md` for provenance limits.

The view is overhead and shows many bays. **Only three demonstration bays are mapped**, not the entire car park:

| Area | Bay IDs | Calibration |
| --- | --- | --- |
| Overhead / West sample | OVER-W01, OVER-W02 | W01 calibrated; W02 pending |
| Overhead / East sample | OVER-E01 | E01 calibrated |

Recipe: `presets/overhead-demo.json`, version 2. W01 and E01 each use five vacant and five occupied examples, separate from the 12-second empty reference. Their 20 labels come from this one short recording and are highly correlated. They demonstrate the pipeline; they are not an independent accuracy evaluation.

### Camera movement matters

The overhead video drifts relative to its setup frame. The existing 8-pixel alignment limit remains enforced. Samples at 15, 18, 21, 24 and 27 seconds fail `camera_view_changed`, making both methods unknown. No automatic reference replacement or relaxed alignment threshold was introduced.

At 12 seconds, both calibrated bays report vacant and W02 remains unknown: **0 occupied / 2 vacant / 1 unknown**, range **0–33.3%**. That sample is the reference instant, so it is a functional check, not independent validation. At the last sampled instant, all three displayed bays are unknown and occupancy is unavailable. Earlier usable results remain timestamped history.

An initial three-bay calibration attempt used later frames and failed alignment. It was replaced with two bays having valid examples near the setup view. W02 was deliberately left pending. Unlabelled invalid MOG2 update frames are skipped through the existing runtime guard; labelled invalid calibration frames still cause an error.

## How area availability works

The **Areas & availability** tab shows each area's known-vacant, known-occupied, unresolved and mapped-bay counts. Unresolved includes uncertain plus unknown. Areas with no usable evidence display unavailable, not zero occupancy. Double-click a row to watch that area's selected recording.

The table remembers a selected recording and playback position for each site. Sample time is displayed per area, so results from independent recordings are not represented as one live instant. There is no summed cross-site live total. Camera overlap never creates more physical bays. The circle chart covers the selected mapped camera inventory; uncalibrated additional views are explicitly view only.

Reference and MOG2 must both say occupied or both say vacant for a definite final state. Mixed evidence is uncertain; both unavailable is unknown. An exact percentage requires every mapped bay to be resolved. Otherwise bounds are `occupied / total` through `(occupied + unresolved) / total`; wholly unavailable evidence has no rate.

Three-second samples and ten-second summaries still run chronologically before review playback, preserving MOG2's state order. Ten-second method tables cover the calibrated subset and say so; pending inventory is shown as unknown in the main chart/area table. The previous terminal mode still covers its original three calibrated CHAD bays.

## Saved outputs and verification

Interface runs now write `runs/areas/<UTC-time>/`:

- `chad/` and `overhead/`: method results, annotated images, paired history/CSV, ten-second windows and final historical summaries for the calibrated subsets.
- `bay-inventory.json`: mapped IDs, polygons and pending calibration status.
- `area-summary.json`: the most recently displayed area observations, with recording/sample positions and `live_availability: false`.
- `source-status.json`: per-source preparation issues. One unavailable additional source does not prevent other usable sources from preparing.

Full suite: **125 tests passed in 56.17 s**. The actual interface check decoded eight recordings and analyzed **49 sampled frames / 137 paired bay observations** across the five analyzed recordings. Two checks took 17.66 s and 15.16 s with cached media/calibrations. The latest is `runs/areas/20260918T135145_877105Z`; `runs/verification/interface-check.json` records zero source issues and zero Tk callback errors. Navigation, seeking, unknown-state handling, area arithmetic and later overhead drift were checked. Own-window screenshots were inspected on the 1280×720 screen and the video count strip layout was corrected.

Research also checked the [Computer Vision Engineer tutorial](https://github.com/computervisioneng/parking-space-counter): its linked Drive listing did not provide a verified accessible video during this attempt. The [DLP dataset](https://sites.google.com/berkeley.edu/dlp-dataset) has overhead parking footage, but full raw access requires a request and its sample could not be retrieved here. Neither was added, and no access request/message was sent.

Remaining work for validated full-area availability: suitable stable footage, calibration for all intended bays, manually verified cross-view mapping and synchronized capture if fusing views, and held-out labels from separate capture periods. External live parking input and independent accuracy/error rates remain unverified. The current update does not require a Windows setting change or a manual download.
