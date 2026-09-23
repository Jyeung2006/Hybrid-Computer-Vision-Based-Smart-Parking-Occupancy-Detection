# Prototype validation results

## Current guarded-vacancy check — 23 September 2026

All **278 tests passed in 90.59 seconds**, including new targeted guards for invalid/stale/model-failure frames, weak/nearby boxes, classic conflicts, reviewed empty mismatch, provisional labelling, camera/recording/time-gap/reset isolation and GUI playback seeking. The all-view YOLOv8s replay completed eight recordings, 60 sample pairs and 1,088 bay observations. The saved comparison with the strict baseline found **151 uncertain-to-vacant** changes (all reviewed-empty matches), zero occupied changes, unchanged Reference/MOG2/YOLO state/reason inputs and 20 consistent ten-second/partial windows. The final overhead frame is **48 occupied, 9 vacant, 12 uncertain / 69**. The replay and full per-bay report are linked in [GUARDED_VACANCY.md](GUARDED_VACANCY.md). No independent labels for these exact observations were available: **false-vacant errors and accuracy have not been established**.

## 22 September separate PKLot UFPR04 external validation

Completed the day-disjoint 60/20/20 experiment in [EXTERNAL_VALIDATION.md](EXTERNAL_VALIDATION.md), using the actual production branches. It is independent of the application footage and does not establish CHAD/overhead or indoor accuracy. The runnable entry point is `checks/evaluate_pklot.py`; the complete measured report is [pklot-evaluation.json](runs/verification/pklot-evaluation.json).

All 28 bays have fitting-only references and hundreds of vacant/occupied examples. Reference thresholds calibrated for 19 bays, MOG2 for zero: the latter distributions overlap despite ample examples. Fitting-image inspection also found three camera positions; the existing fixed-view guard was retained. No test-based retuning.

The held-out set has 741 frames and 20,673 labelled observations. Calibration selected aerial YOLOv8s before test. Final aerial made **5,222 correct occupied decisions, zero vacant decisions and 15,451 unresolved decisions**: 100% classified accuracy/precision, **25.2600% coverage**. Recall counting unresolved occupied observations as missed positives is **34.5416%**, and corresponding F1 **51.3471%**. Conditional recall/F1 are 100%, explicitly distinguished in the report. False-vacant/false-occupied counts are 0/0 because the branch only confirmed cars; this is not evidence of successful vacancy recognition. Reference alone achieved 97.2881% classified accuracy at 19.9777% coverage, with 106 false-vacant and six false-occupied errors. All weather matrices, exact counts, denominators and latency are documented.

Final suite: **254 passed in 64.16 seconds**, [test XML](runs/verification/pklot-tests-final.xml). The [saved-result audit](runs/verification/pklot-delivery-check.json) passed 80,980 decision-policy checks, day/content leakage checks, matrix/ratio checks and frozen configuration checks; all **636 protected existing files were unchanged**. Existing MOG2 signatures remain compatible. Rerunning the default check returned saved measurements without new test inference. This addition did not change or relaunch the normal UI.

## 22 September diagnostic audit of mapping and model consistency

[The audit](MAPPING_CALIBRATION_AUDIT.md) checked all 90 bay/view polygons and generated reference/calibration status, matched 117 original observations with zero classic state changes, and matched 398 SSD-era CHAD observations with zero classic changes. Repeated actual inference on each of five views' last frame three times; detections were identical and saved states reproduced. All 60 current sample frames have zero alignment/inference errors. Both ONNX hashes/class mappings verified. One one-pixel mapping overlap was investigated with an in-memory trim; zero YOLO state changes across ten overhead samples. This was a read-only diagnostic: production remains unchanged and the preceding 244-test suite was not rerun unnecessarily.

Evidence: [report.json](runs/verification/mapping-calibration-audit/report.json), [per-bay.csv](runs/verification/mapping-calibration-audit/per-bay.csv). Recognition accuracy remains unmeasured independently; deterministic repeated inference and policy checks are not accuracy.

## Current verification - 22 September 2026

- **244 tests passed in 97.35 seconds**: [tests-decision-full.xml](runs/verification/tests-decision-full.xml). Added 64 combinations of Reference/MOG2/verifier states plus an end-to-end three-sample regression proving that a valid empty bank and successful no-detection YOLO cannot override unresolved displayed methods. Existing failure, calibration, threshold, association, chronology and occupancy checks also pass.
- Replayed all four CHAD angles (four Camera 1 periods, one each for Cameras 2-4) and the overhead video: **60 sampled frames / 1,088 observations**. Verified the selective trigger, every final confirmation source, classic agreement retention, per-bay final JSON, chart arithmetic and ten-second/final-partial window states. **Zero unsupported definite decisions** under the corrected policy.
- Current actual UI run: [runs/areas/20260921T161408_115721Z](runs/areas/20260921T161408_115721Z); all five source groups completed with no source issues. Independently checked its saved data using `checks/check_decisions.py --existing-run ...`. Native Computer Use inspection verified the 48/69 chart, 2 vacant/19 uncertain, all-area totals, formerly overridden WL07 now uncertain with "No method confirmation", completed-window totals and video count strip. The test's own window was closed afterward.
- The separate headless replay `runs/areas/20260921T161321_173938Z` also passed; it took **112.23 seconds** for preparation/analysis/reporting. The actual UI run's preparation duration was not instrumented. These runs overlapped tests/each other on the CPU, so timings are descriptive, not a controlled performance comparison.
- Audited the previous run: **245 vacant observations lacked classic agreement**, including **237 with all three displayed methods unresolved**. Affected: Camera 1's four periods, Cameras 2/3 and overhead. Camera 4 had zero observed occurrences because the old three-sample rule could not complete in its short clip; the shared code is corrected for it too. No new state is presented as ground truth.

| Group | Frames | Bay observations | Decision coverage | Branch median / p95 |
| --- | ---: | ---: | ---: | --- |
| CHAD | 50 | 398 | 40.70% | 432.80 / 533.98 ms |
| OVERHEAD | 10 | 690 | 71.01% | 514.78 / 577.85 ms |

Branch timing is Reference + MOG2 + YOLO only, excluding decoding/registration, report writing and rendering. Full-sequence decision coverage is not accuracy or final-frame coverage. Source capture time remains unknown and no external live parking source was tested. Independent labelled accuracy and false-vacant/false-occupied rates remain unmeasured. Existing empty examples are retained; no YOLO class, model threshold, polygon or reference label was changed in this correction.

Evidence: [decision-check.json](runs/verification/decision-check.json), [DECISION_FIX.md](DECISION_FIX.md), [FINAL_RESULTS.md](FINAL_RESULTS.md).

## Earlier validation (historical)

## 19 September selective-YOLO and 69-bay verification

Measured 19 September 2026; documentation completed 20 September. Final actual run: [runs/areas/20260919T085852_114918Z](runs/areas/20260919T085852_114918Z).

- **161 automated tests passed in 102.61 seconds**: [tests-yolo-full.xml](runs/verification/tests-yolo-full.xml). They cover source/image/reference/polygon validation, resolution/alignment guards, classic thresholds, occupancy arithmetic, MOG2 chronology and calibration, missing/stale evidence, site/time separation and the new YOLO routing/association/queue paths.
- YOLO-specific checks include definite agreement bypass, either/both uncertain, conflicting occupied/vacant, unknown evidence, exactly 0.80 accepted versus below rejected, ambiguous polygons, no-hit uncertainty, one full-frame inference for all requested bays, stale/wrong identity rejection, bounded queue, timeout, supersession, worker failure and close.
- The first full regression attempt had **159 passes and two failures** because a calibration test still patched the former `Recording` constructor after production moved to `recording_for_recipe`. The fixture now patches the new factory; its assertions that invalid labelled frames fail and invalid unlabelled frames do not update MOG2 were preserved. The final suite above passed. The first focused check passed 56 tests; a reserved pytest parameter name was corrected during initial collection.
- The reproducible export script successfully rebuilt both pinned YOLOv8s ONNX profiles. The full interface was then rechecked using those rebuilt models, including file-integrity checks. There is no manual model-download prerequisite for normal Run here.
- **All eight recordings** decoded and analyzed: 50 CHAD samples and 10 overhead samples, totalling **1,088 bay observations**. No source issues or Tk callback errors occurred. Every actual row was checked against the selective trigger, including preservation of matching definite classic results.
- **227 overhead registration samples** at stride three had zero failures; maximum median reprojection error was **1.086 pixels**. Synthetic tests also reject changed resolution, large motion and featureless frames. Registration does not bypass the post-registration alignment guard or allow black warp padding inside bays.
- Actual UI checks covered site/view/recording selection, all 69 polygons, table scrolling, chart counts, area totals, video playback, forward/backward seek, window reset, pause/resume and live-tab pause. Own-window screenshots were inspected, and a clipped area footer was shortened and rechecked. The test closes its own window.

## Measured timing and decision coverage

Cached preparation took **73.19 seconds** in the final run; an earlier equivalent run took 68.28 seconds. Preparation includes calibration/cache checks, decoding, registration, analysis, report writing and UI handling. The final run overlapped automated tests on this CPU, so these are descriptive observations, not a controlled speed benchmark.

| Group | Frames | Bay observations | Decision coverage | Branch sum median / p95 | YOLO inference median / p95 |
| --- | ---: | ---: | ---: | --- | --- |
| CHAD | 50 | 398 | 40.70% | 424.50 / 492.16 ms | 342.02 / 391.68 ms |
| OVERHEAD | 10 | 690 | 71.01% | 447.72 / 503.72 ms | 339.79 / 402.33 ms |

Branch-sum latency is Reference + MOG2 + YOLO processing and excludes frame decoding/registration, file writes and UI rendering. Each sampled frame had at least one unresolved bay: **60 full-frame inferences completed**, serving **987 requested bay observations**, with **101 bay observations skipped** because the two classic branches agreed. Inference was shared per frame, not repeated per bay. Queue waiting was below 0.7 ms in this sequential recorded run; this does not establish concurrent-camera throughput.

Final overhead estimate at 27 seconds: **48 occupied, 2 vacant, 19 uncertain / 69**. Full-sequence coverage counts classified observations divided by all bay observations. It is not the final-frame percentage and is not accuracy. Detailed metrics: [yolo-measurements.json](runs/verification/yolo-measurements.json), produced by [checks/measure_yolo_run.py](checks/measure_yolo_run.py). UI evidence: [interface-yolo-check.json](runs/verification/interface-yolo-check.json). Registration evidence: [registration-overhead-check.json](runs/verification/registration-overhead-check.json).

**Not measured:** independent labelled accuracy, false-vacant errors and false-occupied errors for the new model/policy. At least 30 manually labelled frames from separate capture periods, covering both bay states and excluding reference/calibration material, are still needed. No live external parking camera was tested. The earlier local HTTP tests exercise retrieval mechanics, not an authorized live parking source. No new YOLO training or automatic ground-truth generation was performed.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe checks/check_interface.py
.\.venv\Scripts\python.exe checks/measure_yolo_run.py
```

Final delivery checks on 20 September also passed: 50 Python files parsed, 69 unique convex bay polygons validated, both ONNX file sizes/digests verified, and all root/third-party Markdown local links resolved. Evidence: [yolo-delivery-check.json](runs/verification/yolo-delivery-check.json).

## Historical validation before selective YOLO — retained for audit

The following dated results concern earlier stages and do not replace the current measurements above.

## Current mapped-camera verification — 19 September 2026

- **142 tests passed in 108.31s**: `runs/verification/tests-mapped-full.xml`. Coverage includes model/frame failure, no-detection vacancy safeguards, weak/ambiguous overlaps, duplicate boxes, evidence conflicts, provenance, four-method output/windows, per-view inventory and source separation, plus the existing frame/calibration/MOG2/timing checks.
- A subsequent failure-guard check passed **25 focused tests in 29.51s**, including unavailable/stale frames whose error text is missing (`tests-mapped-final.xml`). Processing timestamps were then made consistent with the Vehicle branch completion; **42 focused tests then passed in 34.32s** (`tests-mapped-timestamps.xml`), including joined completion timestamps. Python syntax, convex preset polygons and local documentation links also passed.
- Actual UI integration decoded and analyzed **all eight recordings**, producing **60 sampled frames**: 50 CHAD and 10 overhead. CHAD has **398 mapped bay observations**; overhead has 20 analyzed observations plus its third pending inventory bay.
- Preparation took **119.45s** with cached media/model, including setup/empty-bank checks, analysis, reporting and UI handling. This includes work beyond detector inference; it is not a live throughput benchmark. No source issues or Tk callback errors occurred.
- Across CHAD samples, the sum of Reference/MOG2/Vehicle processing had median **237.73ms** and 95th percentile **313.44ms**. These per-frame timings exclude decoding, report writes and UI rendering. Results come from this computer/run, not a real-time guarantee.
- Final decision coverage across CHAD observations was **92.71%**. **Accuracy, false-vacant and false-occupied rates were not measured independently.** Reviewed reference/calibration periods appear in the replay, so a model accuracy claim would be unsupported.

Measured outputs: `runs/areas/20260918T185845_684414Z`. Machine-readable summaries: [mapped-measurements.json](runs/verification/mapped-measurements.json), [interface-mapped-check.json](runs/verification/interface-mapped-check.json). See [FINAL_RESULTS.md](FINAL_RESULTS.md) for the per-view final counts and uncertainties.

The actual UI check verified each view's own states, the shared P009 ID, the new Vehicle column, nine Camera 1 bays, backward/forward seeking, completed-window reset, playback pause/resume, live-tab pause and overhead alignment rejection. Camera 1's near-row P009 is occupied via the detector even when Reference/MOG2 are unknown. The adjacent P008 is not forced vacant when empty-image evidence fails.

Inspected `mapped-near-row.png`, `mapped-summary.png`, `mapped-chad-camera-2.png` and the corrected Camera 3 polygon annotation. The chart, five-column table, selectable reason text, video count strip and scrolling summaries fit the 1280x720 display. Screenshots capture only the test's own application window. Additional screenshots for Cameras 3/4, areas, video and live view are in `runs/verification/mapped-*.png`.

The original 8-pixel alignment guard was not loosened. Camera 2/3 far-row identity across views is unverified, and capture offsets are unknown. No real synchronized multicamera fusion or external live parking test is claimed. Source videos remain prerecorded. The remaining evaluation needs at least 30 independently captured/manual-labelled frames, with occupied and vacant examples across separate periods, excluded from the empty bank and calibration. Document both classified accuracy and coverage/error counts before claiming reliability.

## Historical validation records

The sections below describe earlier versions. Their smaller inventories, two-method results, timings and test totals are historical; current behavior is above.

Latest update: **18 September 2026**. **Default Run opens the parking areas, chart and video interface.** It provides two sites, actual CHAD camera selection, and recorded Reference/MOG2/final estimates every three video seconds, with ten-second summaries. The timed terminal comparison is available with `--terminal`. Independent parking accuracy and real cross-camera correspondence remain unmeasured.

## Areas and additional source validation

The full suite passed **125 tests in 56.17 seconds** (`runs/verification/tests-areas-full.xml`). New checks cover nine unique CHAD bay IDs, six pending bays expanding the occupancy range, separate site/recording totals, three overhead inventory bays, invalid site mappings and clearing counts when selecting a view-only camera. After the video layout fix and adding two explicit calibration-guard cases, **19 focused tests passed in 4.87 seconds** (`tests-areas-final.xml`): invalid unlabelled MOG2 frames cannot update the model; invalid labelled frames still abort calibration.

The actual interface check analyzed **49 sampled frames / 137 paired bay observations** across five analyzed recordings and decoded all **eight** selectable recordings. Latest preparation took **15.16 seconds**, versus 17.66 seconds in the previous check, using cached media/calibration. There were no source issues or Tk callback errors. Tests exercised final counts, seeking, pause/resume, area navigation and later overhead drift. The corrected video layout keeps the count strip visible on the 1280×720 screen. This measures integrated preparation, not standalone detector latency.

Current evidence: `runs/areas/20260918T135145_877105Z`, `runs/verification/interface-check.json`, and screenshots `interface-areas.png`, `interface-overview.png`, `interface-watch.png`, `interface-overhead.png`, `interface-chad-camera-2.png` through `-4.png`. Only the test application's window was captured.

CHAD final states for its three calibrated bays are unchanged; the nine-bay interface adds six unknowns. The overhead recipe has 20 reviewed labels (five per state for each of two bays), separate from the empty reference, but all from one short recording. At 12 seconds both calibrated bays are vacant and the third is unknown. This is also the reference instant and is **not independent validation**. Samples 15–27 seconds fail alignment and become unknown. No alignment threshold was relaxed. Additional views are view only, not validated synchronized fusion. See [PARKING_AREAS.md](PARKING_AREAS.md).

The following sections retain earlier measurements and their original three-bay scope.

## Earlier interface validation

The full automated suite passed **120 tests in 48.52 seconds** (`runs/verification/tests-interface-full.xml`), including 12 interface tests covering chart arithmetic, unknown-state rendering, past-only sample/window lookup, stale/disconnected/error previews, sanitized errors, bounded queues, and actual local HTTP snapshot/MJPEG input. Local synthetic camera input does not establish external parking-camera access.

The actual four-recording UI check (`checks/check_interface.py`) completed **39 sampled frames / 117 paired bay observations** in preparation, then verified all four video decoders, their final chart counts, seeking backward/forward, summary reset, pause/resume and live-tab navigation. Latest preparation took **13.58 seconds** with cached media/calibrations (an earlier check took 12.95 seconds); timings are illustrative, not a standalone method benchmark. No Tk callback errors were reported. Final counts match the table below.

Latest interface evidence: `runs/comparison/20260917T171824_811397Z`, `runs/verification/interface-check.json`, and `interface-overview.png`, `interface-watch.png`, `interface-live.png`. Screenshots were inspected and the layout adjusted for the actual 1280×720 screen so playback controls, chart percentage and bay scope remain visible. Only the check's own application window was captured. Terminal compatibility was verified with `main.py --terminal --video chad-2 --fast --frames 1` (exit 0).

The interface precomputes chronological recorded observations before playback; its review/seek behavior is not an end-to-end live analysis test. Real authorized live input, live occupancy for a newly configured camera, and independent accuracy evaluation remain outstanding. Detector logic and calibration were not changed for the interface.

## Both methods across all four recordings

The normal timed run completed all four clips: **39 sampled frames, 117 paired bay observations, 13 per-recording window summaries, no skipped ticks, no errors**. Playback/reporting elapsed time was **33.062 seconds**, excluding preparation. The first ten-second summaries were emitted approximately 78–94 ms after the target; all measured window lateness was between 0 and 94 ms. Processing was sequential across recordings at each common relative sample time; this is not a hard real-time guarantee or synchronized capture from four cameras.

| Recording | Reference occupied / vacant / uncertain | MOG2 occupied / vacant / uncertain | Reference / MOG2 decision coverage |
| --- | --- | --- | --- |
| CHAD 1 | 12 / 14 / 4 | 16 / 10 / 4 | 86.67% / 86.67% |
| CHAD 2 | 10 / 19 / 4 | 10 / 19 / 4 | 87.88% / 87.88% |
| CHAD 3 | 6 / 13 / 2 | 6 / 13 / 2 | 90.48% / 90.48% |
| CHAD 4 | 11 / 22 / 0 | 0 / 22 / 11 | 100.00% / 66.67% |

Aggregate reference counts were **39 occupied / 68 vacant / 10 uncertain**, and MOG2 counts **32 occupied / 64 vacant / 21 uncertain**, with zero unknown observations for either branch. Reference coverage was **91.45%**, MOG2 **82.05%**. There were 89 pairs with agreeing binary decisions and 28 with at least one unresolved decision. There were no binary occupied-versus-vacant disagreements in this run; different uncertain/definite decisions remain visible. These are decision distributions/coverage, **not accuracy**.

Reference median processing durations for clips 1–4 were 32.16, 32.25, 31.74 and 32.80 ms; MOG2 medians were 10.38, 8.71, 10.04 and 9.72 ms. Reference timing includes shared validation/alignment; MOG2 timing is the incremental foreground/scoring stage after that check. Neither includes decoding, image/CSV writing or waiting, so these figures do not compare standalone end-to-end method speed. Some software tests ran concurrently.

MOG2 calibration used 99 existing reviewed labels from CHAD 1–3, with separate 95th/5th percentile boundaries for foreground proportions. CHAD 4 was excluded. All three bay distributions separated; MOG2 nonetheless leaves CHAD 4's red-SUV bay uncertain throughout the tested sequence. That outcome is retained rather than lowering thresholds for an agreeable result. See [MOG2.md](MOG2.md) for initialization, morphology, chronology, exact boundaries and background-absorption limits.

Final historical estimates use each recording's last sampled frame, with both methods required to agree for a definite state:

| Recording | Last frame time | CHAD-P001 | CHAD-P002 | CHAD-P003 | Final counts: occupied / vacant / uncertain |
| --- | --- | --- | --- | --- | --- |
| CHAD 1 | 26.993633 s | Occupied | Vacant | Vacant | 1 / 2 / 0 |
| CHAD 2 | 29.996633 s | Uncertain | Vacant | Vacant | 0 / 2 / 1 |
| CHAD 3 | 17.984633 s | Vacant | Occupied | Vacant | 1 / 2 / 0 |
| CHAD 4 | 29.996633 s | Vacant | Uncertain | Vacant | 0 / 2 / 1 |

CHAD 2 P001 and CHAD 4 P002 are occupied under reference comparison and uncertain under MOG2, so their final consensus is uncertain. These are three monitored bays across different recording periods, not twelve distinct bays or a current live occupancy claim.

The full automated suite passed **101 tests in 48.23 seconds**, including 12 new MOG2/comparison tests. They exercise removal of shadow labels and isolated noise, first-frame parked-car handling, short static-car retention, departure, one model update per frame, chronological/duplicate rejection, read-only calibration probes, interruption recovery, missing references/calibration, identity joins, four actual synthetic video decoders, isolated failures and unequal clip lengths. The later final-summary addition passed **19 focused tests in 17.39 seconds**, including seven consensus cases and saved-summary checks. A further accelerated run reproduced all final states and saved the historical estimates in `runs/comparison/20260917T161258_089149Z/final-summary.json`. The prior independent-camera workflow remains tested and unchanged.

Evidence:

- `runs/verification/tests-mog2-comparison.xml`: full 101-test result.
- `runs/verification/tests-mog2-final-summary.xml`: focused post-summary checks.
- `runs/verification/mog2-all-first.txt`: initial accelerated run, including actual calibration.
- `runs/verification/mog2-all-timed.txt`: normal combined playback console output.
- `runs/verification/mog2-comparison-measurements.json`: normal run path, per-method metrics, exact timing and counts.
- `runs/verification/mog2-single-chad2.txt`: individual-recording CLI check.
- `runs/verification/mog2-final-summary.txt`: final combined-run output with the final historical table.
- `runs/verification/mog2-annotated-example.png`: visually inspected MOG2 annotation with an explicit method label; the cleaned foreground mask was also inspected.

No independent real-world accuracy, false-vacant/false-occupied error rate, long-duration parked-car retention, live indoor performance or actual cross-camera correspondence is claimed. Prior measurements below are retained as historical records of earlier modes.

## Shared bay IDs and ten-second reporting: 17 September

The extension keeps each camera's calibrated appearance comparison, then maps local polygons onto physical IDs. The built-in B01/B02/B03 polygons map to CHAD-P001/CHAD-P002/CHAD-P003 across all four supplied recordings. These recordings are from one physical camera, not four synchronized views. Real footage tests therefore validate the default one-camera path; two-video synthetic fixtures validate fusion behavior only.

Normal timed command: `python main.py`. The first two summaries closed at video seconds 10 and 20, approximately **10.015 and 20.000 wall-clock seconds** after replay scheduling began. The final 9.996633-second partial window was reported approximately 18.4 ms after the video's end. Ten samples, three summaries, no skipped ticks and no camera errors were recorded; elapsed replay/reporting time was **30.047 seconds**. Setup/download time is excluded from this replay clock.

Actual Video 1 summaries:

| Video window | Latest states P001 / P002 / P003 | P003 occupied-time estimate | Latest occupied / vacant / uncertain / unknown |
| --- | --- | --- | --- |
| 0–10 s | occupied / vacant / uncertain | 60–100% | 1 / 1 / 1 / 0 |
| 10–20 s | occupied / vacant / vacant | 0–80% | 1 / 2 / 0 / 0 |
| 20–29.996633 s, partial | occupied / vacant / vacant | 0% | 1 / 2 / 0 / 0 |

P001's estimated occupied time was 100% and P002's 0% in each window. These are percentages of sampled-state duration, not probabilities or independent accuracy. The final state is kept distinct from historical duration.

All four recordings completed through the new shared-ID runner:

| Clip | Sample ticks | Window summaries, including partial | Occupied / vacant / uncertain bay observations | Median detector ms |
| --- | --- | --- | --- | --- |
| chad-1 | 10 | 3 | 12 / 14 / 4 | 31.32 |
| chad-2 | 11 | 4 | 10 / 19 / 4 | 41.03 |
| chad-3 | 7 | 2 | 6 / 13 / 2 | 48.10 |
| chad-4 | 11 | 4 | 11 / 22 / 0 | 28.81 |

No unknown/failed camera observations occurred in these footage runs. The counts match the prior detector results: the calibration, references and thresholds were unchanged. Timings vary with concurrent testing and exclude decoding, writing and waiting; this is not a controlled performance benchmark. The whole-frame annotation was visually checked; shared-ID labels were then separated into two lines below their bays to prevent overlap and the corrected image was inspected again.

The full suite passed **88 tests in 31.38 s** after the initial extension. A subsequent resolution-error regression check was added; the final focused suite passed **30 tests in 11.93 s**, covering this and the revised annotations/fusion/replay path. The separate support suite passed **21 checks in 1.022 s**. Tests cover agreement, disagreement, uncertain evidence, stale/future observations, synchronization, duplicate/missing mappings, unique counts, exact window boundaries, duration arithmetic, actual decoding of two synthetic videos, decode failures, shorter camera recordings and unavailable camera fallback. Synthetic fixtures do not measure real parking accuracy.

Evidence:

- `runs/verification/multiview-measurements.json`: actual run directories, counts, windows and latencies.
- `runs/verification/multiview-timed.txt`: normal wall-clock Video 1 console run.
- `runs/verification/multiview-chad-2.txt`, `multiview-chad-3.txt`, `multiview-chad-4.txt`: accelerated footage checks.
- `runs/verification/tests-multiview.xml`, `tests-multiview-final.xml`: automated checks.
- `runs/verification/multiview-support-tests.txt`: unchanged display/download support checks.
- Each referenced `runs/sites/CHAD-carpark/...` folder contains site mapping, fused history, window JSON/CSV and per-camera annotated outputs. Fused latest occupancy is unavailable after the run ends; the historical window file retains the last estimate.

**Still required for real multi-camera validation:** synchronized authorized recordings of shared physical bays, a visually verified polygon-to-bay mapping, separate calibration for each perspective, and independent manually labelled periods. No automatic visual re-identification, live multicamera acquisition, vehicle-recognition model or confidence averaging was added. See [MULTICAMERA.md](MULTICAMERA.md).

## Current OpenCV and occupancy checks

The user's basic check loaded OpenCV 4.14.0 with Python 3.12.14, decoded and processed all **899 frames** of Video 1, and displayed them successfully. Its saved report is `runs/opencv-check/result.json` with `status=passed` and `occupancy_tested=false`. This proves the basic image pipeline works; it does not itself classify parking.

The subsequent occupancy runs used the existing Gaussian/grayscale, per-polygon empty-reference difference, percentile boundaries and alignment checks. All four recordings completed with **39 sampled frames / 117 bay observations**, zero unknown results and zero unavailable frames.

| Recording | Frames | Occupied / vacant / uncertain observations | Decision coverage | Median / p95 detector time |
| --- | --- | --- | --- | --- |
| Video 1 | 10 | 12 / 14 / 4 | 86.67% | 28.90 / 33.17 ms |
| Video 2 | 11 | 10 / 19 / 4 | 87.88% | 29.74 / 37.88 ms |
| Video 3 | 7 | 6 / 13 / 2 | 90.48% | 28.99 / 30.44 ms |
| Video 4 | 11 | 11 / 22 / 0 | 100.00% | 28.36 / 39.90 ms |

Overall **107 of 117 observations were classified (91.45% coverage)**; 10 remained uncertain. Coverage measures how often a decision is made, not whether it is correct. Maximum measured setup-view displacement across these runs was **0.9824 pixels**, below the unchanged 8-pixel limit. Original source capture timestamps and source frame age remain unknown.

The table counts bay observations across time, not unique cars. Latency includes the analyzer's alignment/comparison work and excludes downloads, frame decoding, PNG/CSV writes and waiting.

Artifacts:

- `runs/verification/chad-occupancy-measurements.json`: full measurements, per-video run directories and calibration metadata.
- `runs/verification/occupancy-chad-1-expanded.txt` through `occupancy-chad-4-expanded.txt`: full terminal output from accelerated verification runs.
- Each listed run directory contains `latest.png`, `latest.json`, `history.jsonl`, `summary.csv`, `slots.csv` and `run.json`.

The final annotated images from Videos 1 and 4 were visually inspected. Their labels/counts correspond to the marked bays: Video 1 ends with B01 occupied and B02/B03 vacant; Video 4 ends with B02 occupied and B01/B03 vacant. The foreground SUV is outside the monitored scope. This spot inspection is not a full accuracy evaluation.

## Three-second timing

Command: `python main.py --frames 5` (no `--fast`).

Five actual observations were processed at source positions **0.000, 3.003, 6.006, 9.009 and 12.012 seconds**, with no skipped samples. Consecutive processing starts were separated by **2.9352, 3.0125, 3.0433 and 2.9523 wall-clock seconds**. This meets the approximate three-second replay target with ordinary decode/processing jitter. It is not a hard real-time guarantee.

Evidence: `runs/verification/occupancy-timing.json` and `runs/verification/occupancy-three-second-run.txt`. Millisecond precision was then added to terminal timestamps to avoid whole-second truncation making approximately three-second intervals appear as two or four seconds. Exact source-frame positions stay in the output files; displayed video labels round to 00:00, 00:03, 00:06, etc.

## Calibration coverage and limits

The first recipe's five samples per state came only from seconds 1–5. Actual full-clip runs exposed many later uncertain observations. The samples were expanded after visual review across more of Videos 1–3; no arbitrary threshold adjustment, forced binary state, new detector, or reference replacement was introduced. The initial accelerated runs are retained as `occupancy-chad-<n>-fast.txt` for diagnosis.

Recipe version 2 has **99 labelled bay examples in 39 unique full images**:

| Bay | Vacant examples | Occupied examples | Vacant maximum (95th percentile) | Occupied minimum (5th percentile) |
| --- | --- | --- | --- | --- |
| B01 | 10 | 25 | 0.0928724103 | 0.4275638460 |
| B02 | 21 | 11 | 0.0195616106 | 0.4484225195 |
| B03 | 26 | 6 | 0.0144162118 | 0.3318076261 |

All three calibrated successfully. The setup frame, polygons, zero-second empty references and original decision rules are unchanged. Additional labels include vacant bays with pedestrians, so pedestrian presence is not labelled as a parked vehicle. Reference frames are excluded from calibration and duplicate frame/slot pairs are rejected.

The exact samples are in `presets/chad-camera-1.json` and `VIDEO_SOURCES.md`; the reviewed contact sheet is `assets/calibration-review-expanded.jpg`. Generated files are under `data/chad/preset-608ae95f8e05c30d/`; the old preset was retained.

**No independent accuracy claim is made.** Videos 1–3 contribute calibration examples; replaying them is a demonstration. Video 4 does not contribute calibration images, but one separate clip still does not satisfy the planned two-period, 30-labelled-frame evaluation. Accuracy on classified observations, false-vacant errors and false-occupied errors remain pending that evaluation.

## Automated checks

- **63 pytest tests passed in 21.87 seconds**, including four new terminal/replay cases. XML: `runs/verification/tests-terminal-occupancy.xml`.
- **21 support checks passed in 0.763 seconds**, covering source downloads, recipe sample separation, scheduling and display support. Log: `runs/verification/desktop-support-tests.txt`.
- New tests check explicit per-bay/partial-rate formatting, unavailable occupancy rather than false zero counts, and real local lossless-video decoding through the replay/analyzer/reporter. A simulated second-frame decode failure verifies unavailable latest results while retaining the prior timestamped history. Synthetic fixtures are software checks, not real parking accuracy evidence.
- The restored pre-change suite also passed all 59 original tests before the new terminal tests were added. XML: `runs/verification/tests-opencv-restored.xml`.

## Source transport checks and earlier loading failure

The four author-published CHAD MP4s passed size/CRC32/SHA-256 validation after selective ZIP range downloads. Separate FFmpeg inspection decoded **899, 989, 599 and 989 frames**, respectively, at 1920×1080 and approximately 29.97 fps. Evidence: `runs/verification/chad-media-inspection.json`.

Earlier on 15 September, the same installed OpenCV extension failed Windows Application Control during import. Those failed diagnostics are retained in `basic-opencv-check.txt`, `desktop-headless-current.txt` and `opencv-suite-current.txt` under `runs/verification/`. They describe an earlier state and must not be read as the current result. No security setting was changed by the assistant during the successful occupancy work.

## Historical OpenCV evidence

## Recorded indoor demo: 10 September update

The hardcoded [Pexels indoor clip](https://www.pexels.com/video/a-car-stopping-in-a-parking-lot-4707190/) was downloaded successfully by the new `demo` command and checked against its pinned SHA-256. It contains 543 frames at approximately 23.976 fps, 1920×1080, lasting 22.647625 seconds. Analysis uses a 960×540 copy. The camera is fixed, but the low angle does not reveal clear painted bay boundaries, so the preset measures one test region rather than a verified parking bay.

Command: `.\.venv\Scripts\python.exe -m parking_probe demo --headless`

Artifacts: `runs/demo-indoor/20260909T195706_985660Z/`.

| Measurement | Actual result |
| --- | --- |
| Sampled frames processed | 46 |
| Actual sample interval | 0.5005 video seconds |
| Vacant / occupied / uncertain / unknown | 5 / 20 / 21 / 0 |
| Unavailable frames | 0 |
| Classified coverage | 54.35% |
| Maximum setup-view displacement | 0.154 pixels |
| Detector processing median / p95 | 18.66 / 21.40 ms |
| Original source capture timestamp | Unknown; not replaced with download time |
| Saved annotated MP4 | Reopened successfully: 46 frames, 1000×710, approximately 1.998 fps |

Latency is the analyzer duration, including alignment and difference scoring; it excludes the initial download, preset preparation, PNG/CSV/MP4 writing and preview waits. These are measurements on this machine, not a performance guarantee.

Five visually inspected empty examples and five occupied examples were used for the agreed percentile calibration, separate from the reference. Resulting boundaries: vacant maximum `0.0121277913`; occupied minimum `0.1338345277`. Differences between those remain uncertain. All examples and playback are from the same short recording. **Accuracy and false-vacant/false-occupied error rates were not calculated as independent validation.** At least 30 labelled frames from separate capture periods are still required for that evaluation.

The complete calibration contact sheet and final annotated PNG were opened and visually inspected. A three-frame run also exercised the actual OpenCV preview window and verified cache reuse; its artifacts are at `runs/demo-indoor/20260909T195926_397593Z/`. Keyboard/mouse early-stop interaction was not automated.

The expanded automated suite passed **59 tests in 14.91 seconds** using `.\.venv\Scripts\python.exe -m pytest -q --junitxml=runs/verification/tests-video.xml`. The ten new cases cover download caching/corruption recovery, bounded network failure and partial-file cleanup, actual local video decoding, frame bounds, normal EOF versus decoding failure, output metadata and CSV fields, preserving separate runs, rejecting recorded input as live camera input, and invalid sample intervals. Dependency consistency and Python compilation checks also passed.

Use [QUICK_START.md](QUICK_START.md) to launch the demo. The sections below retain the original controlled-test evidence; synthetic results must not be confused with the real-video measurements above.

## Environment

| Component | Tested version |
| --- | --- |
| Python | 3.12.14 |
| OpenCV package | opencv-python 4.14.0.94 |
| OpenCV library | 4.14.0 |
| NumPy | 2.5.3 |
| Requests | 2.34.2 |
| pytest | 9.1.1 |
| Operating system | Windows 11, build 26200 |
| Video backend | FFmpeg available |
| Preview backend | Win32 UI available |

Dependencies are isolated in `.venv`. Exact tested package versions are in `requirements-tested.txt`.

## Automated tests

Command: `.\.venv\Scripts\python.exe -m pytest -q --junitxml=runs/verification/tests.xml`

**49 tests passed in 15.56 seconds.** The machine-readable result is saved in `runs/verification/tests.xml`.

Coverage includes:

- Valid polygon geometry and rejection of crossing, touching, duplicate, undersized, noninteger, or out-of-bounds corners.
- Vacant and occupied decision boundaries, intermediate uncertainty, overlapping calibration distributions, and the minimum sample count.
- Per-bay reference comparison, missing references, null calibration, changed polygons, and occupancy arithmetic with unresolved bays.
- Resolution changes, camera movement, featureless images, stale frames, and source timestamps in the future.
- HTTP image retrieval and explicit capture timestamps from a local simulator.
- HTTP authentication headers, unauthorized responses, malformed images, redirects, response-size limits, read timeouts, and retry recovery.
- MJPEG decoding through a separate stream worker, repeated reads with recent frames, and worker cleanup.
- Rejection of local recording paths as live URLs and omission of credentials from reported errors.
- Calibration and held-out synthetic evaluation; rejection of reference-image reuse, copied calibration images, and overlapping session IDs.
- JSON/CSV/image reporting, successful-history retention after a failure, missing-camera reports, headless polygon import, explicit empty-reference confirmation, and offline-mode identification.
- The complete online command-line path from a local HTTP simulator through analysis and saved reports, followed by a source failure that clears current occupancy while preserving history.

`pip check` found no broken dependency requirements. Python compilation checks passed for the source, scripts and tests. The Windows setup script was rerun successfully using the pinned versions, and the Windows launcher successfully displayed the command help. A fresh installation on a separate computer was not tested.

## Synthetic detector exercise

Command: `.\.venv\Scripts\python.exe scripts/verify_prototype.py`

This exercise generated artificial image patterns, two artificial bay polygons, 20 calibration frames, and 30 held-out frames. Session names were simulated labels, not real recording periods. Occupancy labels were known from generation, not manually assessed parking images.

| Measurement | Synthetic result |
| --- | --- |
| Held-out generated frames | 30 |
| Bay observations | 60 |
| Classified observations | 55 |
| Unresolved observations | 5 |
| Decision coverage | 91.67% |
| Correct classified observations | 55 of 55 |
| False-vacant / false-occupied observations | 0 / 0 |
| Median processing duration | 15.28 ms per generated frame |
| 95th percentile processing duration | 17.77 ms |
| Maximum processing duration | 21.11 ms |

These timing measurements exclude live retrieval, file reporting, and GUI display. They apply only to the generated 800×480 images on this computer. **The synthetic accuracy is not a real parking accuracy estimate and does not satisfy the planned real-camera evaluation.** The synthetic report explicitly sets `minimum_evaluation_requirements_met` to false.

Artifacts:

- `runs/self-test/synthetic-report.json`: full measurements and provenance.
- `runs/self-test/calibration-report.json`: sample counts and fitted boundaries.
- `runs/self-test/preview/latest.png`: annotated synthetic example.
- `runs/self-test/failure-preview/latest.png`: unavailable/stale example.
- Associated JSON and CSV reports in the preview directories.

Both rendered images were visually inspected. Labels, percentages, timestamps, and status text are readable. The synthetic image is prominently labelled as a software test. The failure panel shows unavailable occupancy and unresolved bays rather than reusing the prior percentage.

## Not yet validated

- An actual owner-authorized live indoor camera endpoint, its credentials, its permitted sampling rate, its image quality, and its genuine update behavior.
- Real parking polygons, manually confirmed empty references, or thresholds fitted to that camera.
- At least 30 manually labelled real frames across separate recording periods.
- Real false-vacant/false-occupied rates, lighting/glare/occlusion robustness, and long-running behavior with the chosen source.
- Provider-specific RTSP/HLS compatibility. The stream integration test used local MJPEG.
- Interactive mouse drawing in an actual camera setup session; polygon import and rendered output were tested.

The next step is to supply an authorized existing indoor camera URL through the documented environment variable, run the connection check, and inspect its captured view. No new camera installation is needed.
