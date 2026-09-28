# Final recorded parking estimates

**Current normal Run:** see [OpenCV-first decisions](OPENCV_FIRST.md). The dated sections below preserve earlier policy results and are not current accuracy measurements.

## Current guarded-vacancy replay — 23 September 2026

The latest all-view replay changed **151 of 1,088** per-frame bay observations from uncertain to vacant after three consecutive clean observations with reviewed empty matches. Occupied observations stayed at 582; totals changed from **582 occupied / 70 vacant / 436 uncertain / 0 unknown** to **582 / 221 / 285 / 0**. No no-reference provisional vacancy occurred in these recordings. Reference, MOG2 and YOLO evidence remained unchanged. The final overhead sample is **48 occupied / 9 vacant / 12 uncertain / 0 unknown** out of 69, an occupancy range of **69.6–87.0%**. These recorded estimates have no independent accuracy or false-vacant measurement. The full per-view/per-bay comparison, rule, risks and reproducible checks are in [GUARDED_VACANCY.md](GUARDED_VACANCY.md) and [the saved report](runs/verification/guarded-vacancy-report.json).

## Historical strict-policy result — 22 September 2026

Removed the separate empty-image override. Every definite Final now has support from displayed Reference/MOG2 agreement or a qualifying YOLO vehicle. All three unknown/uncertain cannot produce vacant. See [DECISION_FIX.md](DECISION_FIX.md). These remain experimental estimates, not guaranteed ground truth.

| View / recording | Total | Occupied | Vacant | Uncertain | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Camera 1 / recording 1 | 9 | 2 | 2 | 5 | 0 |
| Camera 1 / recording 2 | 9 | 2 | 2 | 5 | 0 |
| Camera 1 / recording 3 | 9 | 2 | 2 | 5 | 0 |
| Camera 1 / recording 4 | 9 | 2 | 2 | 5 | 0 |
| Camera 2 | 5 | 2 | 0 | 3 | 0 |
| Camera 3 | 4 | 2 | 0 | 2 | 0 |
| Camera 4 | 3 | 1 | 0 | 2 | 0 |
| Overhead | 69 | 48 | 2 | 19 | 0 |

Overhead at 27 seconds: **48 occupied, 2 vacant, 19 uncertain / 69**, occupancy range **69.6-97.1%**. The previous 21 September 48/14/7 count used the now-retired heuristic. Its twelve additional final vacancies are no longer called model-confirmed. Area counts remain west 17/1/6 of 24, middle 17/0/5 of 22, east 14/1/8 of 23 (occupied/vacant/uncertain).

Current actual interface run: [runs/areas/20260921T161408_115721Z](runs/areas/20260921T161408_115721Z), all eight recordings complete and no source issues. [decision-check.json](runs/verification/decision-check.json) validates **60 sampled frames / 1,088 bay observations**, including chart and ten-second final-state consistency. All **652 definite observations** have displayed-method support; that measures policy consistency, not accuracy. Independent accuracy/error rates remain unmeasured. Results from different CHAD periods/views are not summed as live capacity.

## Historical results below

The following dated runs are retained for audit. Their counts and policies do not override the current section.

## 19 September: all overhead bays and selective YOLOv8

Measured **19 September 2026**, documentation completed **20 September 2026**. These are the last sampled frames of separate recordings, not synchronized live availability or manually labelled ground truth. Do not add overlapping CHAD view capacities.

| View / recording | Last sample | Mapped | Occupied | Vacant | Uncertain | Unknown | Occupancy range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Camera 1 / 1_029_0 | 27s | 9 | 2 | 2 | 5 | 0 | 22.2-77.8% |
| Camera 1 / 1_038_0 | 30s | 9 | 2 | 2 | 5 | 0 | 22.2-77.8% |
| Camera 1 / 1_049_0 | 18s | 9 | 2 | 2 | 5 | 0 | 22.2-77.8% |
| Camera 1 / 1_054_0 | 30s | 9 | 2 | 2 | 5 | 0 | 22.2-77.8% |
| Camera 2 / 2_036_0 | 12s | 5 | 2 | 0 | 3 | 0 | 40.0-100.0% |
| Camera 3 / 3_073_0 | 9s | 4 | 2 | 0 | 2 | 0 | 50.0-100.0% |
| Camera 4 / 4_075_0 | 3s | 3 | 1 | 0 | 2 | 0 | 33.3-100.0% |
| Overhead / carPark | 27s | 69 | 48 | 2 | 19 | 0 | 69.6-97.1% |

The overhead site includes **all 69 visible painted bays**, even stationary occupied/empty bays. Its west/middle/east areas have 24/22/23 bays; final counts are respectively **17/1/6**, **17/0/5**, **14/1/8** occupied/vacant/uncertain. The final chart reads **48 / 69 occupied**, **2 vacant**, **19 uncertain**, range **69.6-97.1%**. Uncertain does not mean free; zero identified vacancies does not prove an area full.

Matching definite Reference/MOG2 results are retained; either uncertain/unknown or disagreement triggers YOLO. YOLO requires score at least 0.80 and unique bay association to establish occupied. No qualifying detection cannot establish vacancy. Only three overhead bays have full two-state classic calibration; the other 66 still receive YOLO assessment. Thus every bay is mapped and included, without pretending every result is definite.

CHAD's near SUV P009 is assessed directly and is occupied in the sampled views. Camera 1 P008 remains uncertain under the new policy. Earlier SSD/empty-bank vacancy results below are **superseded**, because one-sided empty matching is no longer part of normal Run. Original Reference/MOG2 states remain visible; inference does not manufacture empty references or copy another recording's result.

Actual run: [runs/areas/20260919T085852_114918Z](runs/areas/20260919T085852_114918Z). Evidence: [interface-yolo-check.json](runs/verification/interface-yolo-check.json), [yolo-measurements.json](runs/verification/yolo-measurements.json), [annotated 69-bay map](assets/previews/overhead-69-bays.jpg). The run saved all four branches, IDs, timing, per-frame rows, ten-second windows and annotated output. Source capture times remain unknown; video positions and local processing timestamps are recorded.

The interface check processed **60 sampled frames / 1,088 bay observations**, with zero source issues or Tk callback errors. Decision coverage over the full sampled sequence was **40.70% CHAD** and **71.01% overhead**; these differ from a last-frame coverage and are **not accuracy**. Independent accuracy, false-vacant and false-occupied rates still need separate manually labelled evaluation frames. See [VALIDATION.md](VALIDATION.md) and [YOLOV8.md](YOLOV8.md).

## Historical SSD supplement results — superseded

The following records the previous implementation. Its counts and decision rule do not describe current normal Run.

Updated **19 September 2026**. All four CHAD camera views now have mapped results using Reference, MOG2 and the approved OpenCV Vehicle supplement. These are the **last sampled frames of separate recordings**, not simultaneous live availability. Do not add these overlapping inventories into one car-park total.

| View / recording | Last sample | Mapped | Occupied | Vacant | Uncertain | Unknown | Occupancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Camera 1 / 1_029_0 | 27s | 9 | 2 | 7 | 0 | 0 | 22.2% |
| Camera 1 / 1_038_0 | 30s | 9 | 2 | 7 | 0 | 0 | 22.2% |
| Camera 1 / 1_049_0 | 18s | 9 | 2 | 2 | 5 | 0 | 22.2–77.8% |
| Camera 1 / 1_054_0 | 30s | 9 | 2 | 7 | 0 | 0 | 22.2% |
| Camera 2 / 2_036_0 | 12s | 5 | 2 | 3 | 0 | 0 | 40.0% |
| Camera 3 / 3_073_0 | 9s | 4 | 2 | 2 | 0 | 0 | 50.0% |
| Camera 4 / 4_075_0 | 3s | 3 | 1 | 2 | 0 | 0 | 33.3% |

Camera 1's near row is assessed directly: **P009 occupied** in every sampled CHAD view; **P008 vacant** at the final samples of Camera 1 recordings 1/2/4, and **uncertain** in recording 3. Its final P004–P008 differences exceed the reviewed empty-match tolerances. No failed calibration is hidden and no other-period result is substituted.

Final occupied bays are P001/P009 in Camera 1 recordings 1/2, and P002/P009 in recordings 3/4. Camera 2's occupied IDs are P009/C2-F01; Camera 3's are P009/C3-F01; Camera 4's is P009. Other mapped bays are vacant except the five stated uncertain bays. All IDs use prefix `CHAD-`.

**Decision rule:** opposing definite methods produce uncertain. Otherwise Reference/MOG2 agreement is retained or a definite Vehicle result supplies the estimate. Missing vehicle detection alone cannot establish vacancy. This is an experimental method combination, not calibrated probability or temporal confirmation. Reference/MOG2 may remain unknown/uncertain because added bays lack full two-state examples.

The overhead site still shows two vacant/one unknown at 12s (0–33.3%). Later camera drift invalidates its final observation: all inventory bays unknown and occupancy unavailable. Three example bays do not describe its entire visible car park.

Measured run: `runs/areas/20260918T185845_684414Z`. Per-recording final summaries and annotated images are saved under each camera's folder. Combined measurements: [mapped-measurements.json](runs/verification/mapped-measurements.json). UI check: [interface-mapped-check.json](runs/verification/interface-mapped-check.json). There were no source issues or callback errors.

CHAD produced **50 sampled frames / 398 bay observations**, with **92.71% decision coverage**. This is the proportion receiving a definite result, not accuracy. Independent accuracy and false-vacant/false-occupied rates remain unmeasured. Setup/calibration periods are reused in this demonstration.

[Short guide](QUICK_START.md) · [Mapping and evidence](CAMERA_MAPPING.md) · [Validation](VALIDATION.md) · [Work log](WORK_LOG.md)

## Earlier calibrated-subset results

Verified combined run: `runs/comparison/20260917T161258_089149Z`.
These are the **last sampled frames of separate recordings**, covering only three marked bays per recording. They are historical experimental estimates, not current live availability.

| Recording | Last sampled video time | CHAD-P001 | CHAD-P002 | CHAD-P003 | Final counts |
| --- | --- | --- | --- | --- | --- |
| CHAD 1 | about 27 s | Occupied | Vacant | Vacant | 1 occupied, 2 vacant |
| CHAD 2 | about 30 s | Uncertain | Vacant | Vacant | 2 vacant, 1 uncertain |
| CHAD 3 | about 18 s | Vacant | Occupied | Vacant | 1 occupied, 2 vacant |
| CHAD 4 | about 30 s | Vacant | Uncertain | Vacant | 2 vacant, 1 uncertain |

**Decision rule:** occupied/vacant requires agreement between reference comparison and MOG2. A disagreement or incomplete decision is uncertain; both methods unavailable remains unknown. There were no unknown final bays in this run.

For CHAD 2 P001 and CHAD 4 P002, reference comparison says occupied while MOG2 says uncertain. The final estimate therefore remains uncertain. Occupancy across the three monitored bays is 33.3% for CHAD 1 and CHAD 3, and 0–33.3% for CHAD 2 and CHAD 4. Counts are never summed across these separate periods.

Normal Run opens the chart/video interface, prepares all four recordings and displays the selected recording's estimates every three video seconds. Use `main.py --terminal` for the timed console tables and printed final historical summary. Each run saves `final-summary.json` and `final-summary.csv` alongside detailed branch results. Source capture dates remain unknown. The new interface check reproduced the final states above; see [INTERFACE.md](INTERFACE.md).

[Short guide](QUICK_START.md) · [MOG2 details](MOG2.md) · [Validation](VALIDATION.md) · [Work log](WORK_LOG.md)
