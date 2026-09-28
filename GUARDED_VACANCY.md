# Guarded vacancy in the recorded parking prototype

**Historical primary policy:** normal Run now uses [OpenCV-first decisions](OPENCV_FIRST.md). The guarded reviewed-empty route remains as a fallback; this document records the earlier YOLO-first replay.

Implemented and replayed on 23 September 2026. This is the current **normal Run / F5** policy for the recorded CHAD and overhead views. The restored `Capstone Implementation_19Sep (1)` folder was left unchanged. The earlier strict decision result and its documentation remain historical baselines.

## What Final now means

At each 3-second sample, definite matching Reference and MOG2 decisions remain immediate. If they disagree or either is unresolved, YOLOv8s still runs. A clear, uniquely associated vehicle detection keeps its existing **occupied** route. No model, detector threshold, overlap threshold, polygon or empty reference was relaxed to obtain additional vacant decisions.

For an otherwise unresolved bay, a candidate vacant observation requires all of these:

1. A successfully retrieved, non-stale image of the configured resolution, aligned to the setup view; the mapped bay must be in the reviewed visible inventory and not marked occluded.
2. Neither Reference nor MOG2 says occupied. Any definite occupied/vacant conflict blocks vacancy.
3. Successful YOLO inference on that same camera/frame; no qualifying detection, no ambiguous/weak overlap, and no raw vehicle box touching the polygon or its conservative surrounding band. The existing raw vehicle-box floor remains 0.15. A box near a bay is a reason to **withhold** vacancy, never a reason to mark occupied.
4. If an empty reference is configured, a valid reviewed empty-evidence bank or full two-state calibration must be available and the current appearance must match its existing limit. A mismatch or invalid/missing metadata leaves Final unresolved. The program never replaces an empty reference automatically.

The same bay must pass for **three consecutive samples in the same camera and recording**: typically 0, 3 and 6 seconds. The first two stay uncertain. Failed/missed/duplicate frames, a time gap, changed camera/recording, replay, or backward seek reset the streak. Streaks never transfer between the four CHAD recording periods. Unknown remains unknown when all usable evidence is absent. On GUI seeking/replay, the chart, current bay table, video overlay and current area counts recount three played samples; the saved ten-second windows remain clearly labelled analysis history.

When a reviewed empty reference matches, the reason is `guarded_vacant_reviewed_empty_three_no_detections`. When **no** reviewed empty reference exists, three clean no-detection samples may yield `provisional_vacant_three_no_detections`. The latter is explicitly labelled **VACANT (P)** / *provisional, based on repeated no detection* in the current interface; `final_confirmed_by` remains null. Neither type is an occupancy probability. The single-frame Reference, MOG2 and YOLO columns remain visible. The Final column, JSON/CSV rows, annotated images and ten-second bay summaries preserve the evidence and provisional flag.

## Measured replay

Used the saved strict baseline `runs/areas/20260922T152412_835535Z` and replayed all five source groups to `runs/areas/20260923T114108_587187Z` with the same YOLOv8s COCO/aerial profiles. This is **60 sampled frames and 1,088 bay observations** across eight recordings. Counts below are per-frame bay observations, **not** unique physical spaces, and recordings from different times are not fused. Reference, MOG2, YOLO states and YOLO reasons matched the baseline for every corresponding observation.

| Recording | Observations | Before O / V / U / ? | After O / V / U / ? | Uncertain → vacant |
| --- | ---: | ---: | ---: | ---: |
| CHAD-1 | 90 | 22 / 10 / 58 / 0 | 22 / 21 / 47 / 0 | 11 |
| CHAD-2 | 99 | 22 / 18 / 59 / 0 | 22 / 45 / 32 / 0 | 27 |
| CHAD-3 | 63 | 14 / 12 / 37 / 0 | 14 / 28 / 21 / 0 | 16 |
| CHAD-4 | 99 | 22 / 22 / 55 / 0 | 22 / 58 / 19 / 0 | 36 |
| CHAD camera 2 | 25 | 10 / 0 / 15 / 0 | 10 / 3 / 12 / 0 | 3 |
| CHAD camera 3 | 16 | 8 / 0 / 8 / 0 | 8 / 2 / 6 / 0 | 2 |
| CHAD camera 4 | 6 | 2 / 0 / 4 / 0 | 2 / 0 / 4 / 0 | 0 |
| Overhead | 690 | 482 / 8 / 200 / 0 | 482 / 64 / 144 / 0 | 56 |
| **All observations** | **1,088** | **582 / 70 / 436 / 0** | **582 / 221 / 285 / 0** | **151** |

O = occupied, V = vacant, U = uncertain, ? = unknown. Every one of the 151 changes was an uncertain-to-vacant decision with a reviewed empty-reference match and three clean observations. **Zero no-reference provisional vacancies occurred in these recordings**, although the rule and tests support that route. No occupied result changed. The final sampled overhead frame is **48 occupied, 9 vacant, 12 uncertain, 0 unknown out of 69**; its occupancy range is **69.6–87.0%**, since the 12 unresolved bays might be occupied. These remain historical experimental estimates.

Changed bays, with number of changed observations in each recording:

| Recording | Bay IDs and changed observations | Reason |
| --- | --- | --- |
| CHAD-1 | P005: 2, P006: 5, P007: 4 | Reviewed empty match + three clean YOLO no-detections |
| CHAD-2 | P005: 9, P006: 9, P007: 9 | Same |
| CHAD-3 | P004: 3, P005: 5, P006: 4, P007: 4 | Same |
| CHAD-4 | P004: 9, P005: 9, P006: 9, P007: 9 | Same |
| CHAD camera 2 | C2-F04: 3 | Same |
| CHAD camera 3 | C3-F03: 2 | Same |
| Overhead | EL11: 8, ER02: 8, ER09: 8, ER10: 8, ML11: 8, MR05: 8, W01: 3, WL07: 5 | Same |

Full physical IDs, changed frame IDs and reasons are in [guarded-vacancy-report.json](runs/verification/guarded-vacancy-report.json). The replay audit also checked the decision policy, exact frame/bay pairing, the eight completed recording summaries and **20** ten-second/partial windows. The added guard's recorded processing duration was **8.51 ms median / 9.99 ms 95th percentile** across 60 sample pairs; this excludes YOLO, Reference/MOG2, decoding, report writing and GUI rendering. The replay took about 50 seconds with `fast=True`; that is offline processing, not a measured live frame rate. GUI playback still reveals results at three-second video intervals.

## Tests, limits and files

`python -m pytest -q` passed **278 tests** in 90.59 seconds. The focused guard tests cover a matching/mismatching reviewed reference; missing-reference provisional labelling; occupied/conflicting classic evidence; clear/weak/nearby vehicle boxes; stale and failed inference; occluded or unreviewed bay mapping; missed/gapped/duplicate/backward samples; separate camera/recording streaks; replay reset; unchanged definite base decisions; and GUI playback recounting. The full replay report verified identical underlying Reference/MOG2/YOLO results and that all changes follow the permitted guarded route.

A separate saved-run GUI check (`checks/check_guarded_interface.py`) loaded all eight recordings without inference, exercised the real overview and video widgets at 0/3/6 seconds, verified the bay becomes vacant only on the third played sample, then sought back to 6 seconds and verified it returns to uncertain until a fresh streak is played. It reported no Tk callback errors. [GUI check result](runs/verification/guarded-vacancy-interface/result.json), [overview](runs/verification/guarded-vacancy-interface/guarded-overview.png), [video](runs/verification/guarded-vacancy-interface/guarded-video.png).

There is **no independent ground-truth label set for these exact CHAD/overhead replay observations**. Thus false-vacant errors and accuracy **have not been established**. Calibration labels and reviewed empty examples cannot be reused as independent evaluation. The separate PKLot labelled experiment is a different source/cadence and does not validate this new recorded-video rule. A small, distant or occluded car can evade full-frame YOLOv8s, especially if its score falls below the existing 0.15 raw box floor; three missed detections do not prove empty space. A setup alignment check and reviewed bay map do not guarantee that a person or other object never occludes a bay. The reviewed empty appearance check adds a guard but can vary with lighting. No live indoor camera was tested.

Implementation: `src/parking_probe/vacancy_guard.py` adds the scoped streak and evidence guard; `comparison.py` applies it to normal verification, final results and windows; `interface_model.py` resets displayed streaks on replay/seek; `interface.py`, `areas.py` and `output.py` label provisional results and keep chart/video/area counts consistent. `checks/check_guarded_vacancy.py` replays or audits saved runs; `tests/test_vacancy_guard.py` contains focused tests. The normal CHAD preparation now loads its reviewed empty-evidence metadata. The strict baseline checker `checks/check_decisions.py` and dated result documents remain for the earlier policy.

To reproduce the audit without new inference:

```powershell
.\.venv\Scripts\python.exe checks/check_guarded_vacancy.py --existing-run runs/areas/20260923T114108_587187Z
```

To rerun inference on all built-in views:

```powershell
.\.venv\Scripts\python.exe checks/check_guarded_vacancy.py
```

For the application, select this project's `.venv` interpreter in VS Code, open `main.py` and press Run. Wait for preparation, choose a site/recording, and use Occupancy overview or Watch video. Selecting a bay shows its Final reason; **VACANT (P)** means provisional no-reference evidence. The source videos and both YOLOv8s model files are already cached on this computer. No camera URL or API key is needed for recorded testing.
