# Reference + MOG2 comparison for CHAD 1–4

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.

## Current selective-YOLO implementation — 19 September 2026

Normal Run now uses **Reference / MOG2 / YOLOv8 / Final estimate**. Matching definite classic results are retained; uncertain, missing or conflicting evidence triggers YOLOv8s. No qualifying detection remains uncertain. This supersedes the earlier SSD Vehicle/empty-bank decision rule and its vacancy counts below. CHAD mappings remain 9/5/4/3 bays across Cameras 1/2/3/4; overlapping periods are not fused.

The overhead site now maps **all 69 visible painted bays**, divided west 24 / middle 22 / east 23. Guarded registration corrects this clip's small drift; all ten samples remain usable. Only three bays have full classic calibration; YOLO verifies the others. The former three-bay subset and later-drift failure below are historical.

Current details: [YOLOV8.md](YOLOV8.md), [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md), [FINAL_RESULTS.md](FINAL_RESULTS.md), [QUICK_START.md](QUICK_START.md). YOLO verification is now implemented; later probability fusion, temporal confirmation and persistence remain deferred.

## Earlier implementation and source history

The following dated record preserves the prior algorithms, measurements and source research. Its descriptions of no YOLO, Vehicle fallback, three overhead bays and unavailable later overhead frames are superseded above.

**19 September interface update:** all mapped CHAD views now also have a separate Vehicle column. This does not train MOG2 or create missing empty references; its unresolved states remain visible. Final combines method evidence conservatively. See [CAMERA_MAPPING.md](CAMERA_MAPPING.md). The original MOG2 algorithm and terminal comparison described below remain available.

## Scope and proposal alignment

Normal VS Code Run now compares **all four CHAD recordings together** at corresponding relative playback times. Each recording has its own MOG2 model and both methods produce a result for every marked bay at every three-second sample. Ten-second reports retain separate states, rates and counts for each method and recording. The recordings show different periods from camera 1; they are not synchronized camera views and their occupancy counts are never summed or fused together.

The implementation follows the MOG2 evidence portion of proposal sections 3.2–3.3: one stateful full-frame model per camera/recording, chronological updates, shadow exclusion, morphological opening/closing, then foreground proportion within each slot polygon. Both branches receive the same decoded frame. Their camera, frame, position and slot identifiers must match before the output joins them. CPU execution is sequential within a sample; the evidence branches are separate, but this does not claim parallel worker execution.

The proposal also describes logistic probability fusion, YOLO, three-snapshot confirmation, database transactions and app publication. Those are outside this request. Neither branch score nor their agreement is reported as a calibrated probability or confirmed parking state. The existing custom --site workflow remains reference-only; the new dual-branch workflow is the built-in CHAD comparison.

## MOG2 processing

1. Check the same frame resolution, stable-view alignment and freshness used by the reference branch. Unusable frames produce unknown and do not update MOG2.
2. Apply a 5×5 Gaussian blur to BGR pixels.
3. Apply one OpenCV BackgroundSubtractorMOG2 update to the full frame, in increasing video-time order. Never update once per bay or reuse one model across unrelated clips.
4. Keep only mask value 255 as foreground; remove the shadow label 127. OpenCV documents these labels and the learning-rate behavior in its [MOG2 API reference](https://docs.opencv.org/4.x/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html).
5. Apply a 3×3 elliptical morphological opening followed by closing.
6. For each bay, compute foreground_ratio = cleaned foreground pixels inside polygon / polygon pixels. Also record the raw shadow proportion separately.
7. Apply that bay's MOG2-specific calibrated boundaries: at/below the vacant boundary is vacant, at/above the occupied boundary is occupied, and the middle is uncertain. Missing/overlapping calibration is uncertain; missing empty reference or unusable frame is unknown.

The MOG2 mask is evidence about background/foreground, not semantic vehicle recognition. People, shadows that escape removal, reflections and lighting changes can affect it. See OpenCV's [background-subtraction tutorial](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html).

## Initialization, learning and recovery

Simply learning the first frame could treat an already parked vehicle as background. Instead, this experiment builds a full-frame **empty-bay mosaic**: stable setup pixels outside the bays, with each bay's polygon filled from its existing manually verified vacant reference. References may come from different moments. This mosaic is an initialization artifact, not a claimed capture of the entire lot empty at once.

The model receives 30 bootstrap applications of that mosaic (first learning rate 1, then 0.1). These are repeated initialization operations, not 30 independent training frames. After initialization, each valid three-second snapshot updates the model once with an explicit learning rate of 0.001. Settings are versioned in src/parking_probe/mog2.py:

| Setting | Value |
| --- | --- |
| History | 500 observations |
| Variance threshold | 16 |
| Detect shadows | true |
| Runtime learning rate | 0.001 per accepted sampled frame |
| Gaussian filter | 5×5, BGR |
| Opening / closing | 3×3 ellipse, one operation each |
| Gap requiring model reset | more than 15 video seconds |
| Uncertain observations after reset | two accepted updates |

Duplicate or backwards updates are rejected. After a long interruption or a MOG2 processing failure, the model is reinitialized and returns uncertain during restabilization. If only MOG2 fails, the valid reference result is retained. Decode/resolution failures affect both branches, while other recordings continue.

This is adaptive MOG2 with a verified-empty starting point, not a frozen background. An object that remains stationary can eventually be absorbed into an adaptive background model, as described in the OpenCV API reference. The supplied 20–33-second recordings do not validate long-duration occupied-car retention. The slow learning rate reduces adaptation during this short experiment; it does not establish long-term reliability. Initialization, kernel and learning settings are experimental choices, not independently optimized hyperparameters.

## Calibration and data separation

MOG2 has its own percentile boundaries; reference-distance thresholds are never applied to foreground proportions. The existing 99 visually reviewed bay labels across 39 images from CHAD 1–3 are reused as fitting data. No prediction becomes a label. CHAD 4 remains excluded. Reference images and duplicate bay-image content are rejected as calibration samples.

Each calibration recording starts a fresh seeded model. Normal model updates use exactly the same nearest-frame three-second schedule as replay. Labelled times between those updates are read-only probes with learningRate=0; they do not teach the model another background. A test compares subsequent masks with and without those probes. The original labelled PNG is checked against the decoded source frame. This preserves the chronological model state while allowing the already-reviewed labels at additional times to be used.

Each bay needs at least five vacant and five occupied examples. The vacant boundary is their 95th-percentile foreground proportion; the occupied boundary is the occupied examples' 5th percentile. Overlap keeps the bay uncertain. Measured boundaries with OpenCV 4.14.0 and a three-second interval:

| Bay | Vacant examples | Occupied examples | Vacant maximum | Occupied minimum |
| --- | --- | --- | --- | --- |
| CHAD-P001 | 10 | 25 | 0.3147566521 | 0.8357864601 |
| CHAD-P002 | 21 | 11 | 0.0004180602 | 0.7727006689 |
| CHAD-P003 | 26 | 6 | 0.2386392010 | 0.8988764045 |

All three distributions separated under these fitting conditions. That does not imply every replay frame will be classified. For example, CHAD 4's red-SUV bay is often uncertain under MOG2 even when the reference method says occupied; the output preserves that distinction.

The calibration cache includes model parameters, OpenCV version, sampling interval, setup/mosaic/reference hashes, polygon signatures and labelled image content. Files are saved under data/chad/preset-&lt;signature&gt;/mog2-calibration-&lt;signature&gt;.json and copied into each comparison run. The original reference calibration is unchanged. Real held-out accuracy, false-vacant/false-occupied rates and the planned independent 30-frame/two-period evaluation remain pending.

## Running and reading results

```powershell
# Timed terminal comparison: all four recordings, samples every three seconds.
.\.venv\Scripts\python.exe main.py --terminal
# Only CHAD 2, with both methods:
.\.venv\Scripts\python.exe main.py --terminal --video chad-2
# Verification without playback waits:
.\.venv\Scripts\python.exe main.py --video all --fast
# Stop after five sample ticks across all active recordings:
.\.venv\Scripts\python.exe main.py --frames 5
```

At a sample, **REFERENCE** and **MOG2** are separate occupied/vacant/uncertain/unknown states. **DIFF** is normalized mean absolute difference; **FG %** is foreground_ratio × 100. **AGREEMENT** says agree/disagree only when both methods make binary decisions; otherwise it says unresolved. Neither agreeing methods nor a high FG percentage establish confidence.

Each ten-second report shows latest state and occupied-time bounds for both methods. Rates use the earlier sampled-state-duration definition: the last observation holds until the next sample or explicit failure/end, with uncertainty expanding the upper bound. Actual changes between samples are unobserved. Counts below the table are the latest states per recording/method, not an average across unrelated recording periods. Final short windows are labelled partial. Shorter recordings finish without looping or retaining misleading current estimates.

The end-of-run **FINAL HISTORICAL ESTIMATE** joins the last paired observation in each recording. Both methods occupied means occupied; both vacant means vacant. A disagreement, uncertain method or one unavailable method means uncertain; both unavailable means unknown. This conservative summary is not the proposal's logistic probability fusion or three-snapshot confirmation. It preserves both original method states and each source-frame time alongside the final estimate. It is also produced for a stopped/limited run with historical samples, with the run status recorded.

## Output files

Each run creates runs/comparison/&lt;UTC-time&gt;/:

| File | Contents |
| --- | --- |
| observations.csv | Both methods' states, scores, reasons, processing durations, common IDs and times, one row per recording/bay/sample |
| final-summary.json / final-summary.csv | Last paired observation per recording, conservative final estimate and per-recording counts; explicitly historical |
| history.jsonl | Complete paired results at each sample tick |
| windows.jsonl | Ten-second/partial summaries for each recording, including both methods |
| summary.csv | Counts and occupancy bounds per recording/method/window |
| bay-windows.csv | Per-bay duration/rate/coverage summaries for both methods |
| mog2-calibration.json | Exact parameters, fitted boundaries, fitting samples and provenance |
| chad-N/reference/ | Reference annotated latest.png, latest.json and per-frame JSON/CSV history |
| chad-N/mog2/ | MOG2 annotated image, JSON/CSV history and cleaned foreground.png |
| chad-N/latest-window.json | Last historical summary for that recording, both methods |
| run.json | Selected recordings, sample counts, skipped ticks/errors and run timing |

Original recording capture dates remain unknown. Processing/decode times are recorded separately. Top-level latest.json explicitly marks current occupancy unavailable when the run ends; per-recording files remain timestamped history. Invalid masks are cleared on failures. No new packages, URLs, API keys or Windows setting changes are required on this machine.
