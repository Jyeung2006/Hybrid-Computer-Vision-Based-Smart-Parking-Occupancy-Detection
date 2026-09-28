# Bay-boundary audit and overlap experiment — 24 September 2026

**Historical audit, rolled back 25 September:** the B08 geometry and active alignment/overlap diagnostics described below are no longer used by normal Run. The saved evidence and results remain for review. See [OPENCV_FIRST.md](OPENCV_FIRST.md) for the current policy.

All **90 bay/view entries** were visually inspected before the production geometry edit. Camera-1 **B08 / CHAD-P008** included a strip of concrete beside the curved curb; its left edge now follows visible asphalt. The other 89 polygons and all IDs remain unchanged. The overlap implementation is available for offline experiments and records diagnostics in normal Run, but **no neighbour exemption was enabled in production**: the experiment failed a reviewed occlusion case. Higher vacancy counts are not evidence of improved accuracy.

The restored sibling `Capstone Implementation_19Sep (1)` and the nested historical project were not modified. Pre-existing edits to `QUICK_START.md`, `BAY_DRAWING_GUIDE.md`, `EDGE_OVERLAP_AND_BAY_AUDIT_PROMPT.md` and `drawing-overhead.json` were left intact.

## Evidence and geometry

- [Per-bay audit table](BAY_BOUNDARY_PER_BAY.md): all 90 local/physical IDs, issues, decisions and contact-sheet links.
- [Structured visual review](assets/bay-boundary-review/visual-review.json): camera, analysis resolution, recording/time evidence, separate sidewalk/roadway/curb/shrub/hatched-zone/neighbour/other categories, excluded footprint, obscured markings and before/after vertices. The same data are exported as [CSV](runs/verification/bay-boundary-audit/per-bay-review.csv).
- [Evidence index](runs/verification/bay-boundary-audit/evidence-index.json): native analysis frames for **all 60 samples**. Each bay was inspected in setup plus selected start/middle/end crops from each of its recordings; Camera 4 has only two samples. This is a Codex visual review of image pixels, not an independent human ground-truth survey.
- [Camera-1 before](runs/verification/bay-boundary-audit/chad/setup-before.png), [after](runs/verification/bay-boundary-audit/chad/chad-1-000.0s-after.png), [B08 temporal evidence](runs/verification/bay-boundary-audit/chad/B08-contact.png), [B08 corrected comparison](runs/verification/bay-boundary-audit/b08-before-after.png).
- [Camera-2 F02](runs/verification/bay-boundary-audit/chad-camera-2/F02-contact.png): the exposed painted footprint is retained. At 12s, F01's box overlaps **15.858%** of F02, while covering **98.474%** of F01. Its lower anchor is 9.97px inside F01, less than the experimental 10.30px ownership margin. All tested candidate cutoffs therefore retain uncertainty for F02. Changing the polygon to remove this box would misrepresent the bay.
- Overhead rectangles remain approximate analysis regions. Many perimeters are hidden by parked vehicles; some east-left rectangles may include a thin median/curb strip. These are explicitly unresolved in the table. No unseen boundary was guessed and no occupied silhouette was used as a substitute for paint. The WR07/W02 one-pixel overlap was tested in memory: **zero YOLO state, production-veto or candidate-veto changes** across ten frames and all five cutoffs. No production trim was made.

B08's other three edges were retained. The new eight-vertex outline follows the asphalt beside the curved concrete boundary, with a small margin, rather than shrinking toward the neighbouring car. [Original recipe bytes](assets/bay-boundary-review/chad-camera-1-expanded-before.json) are preserved. The updated preset is recipe v7.

All five B08 reference/bank images and twenty vacant-labelled examples were re-extracted and visually rechecked using the proposed polygon: [sheet 1](runs/verification/bay-boundary-audit/b08-proposal/labels-1.png), [sheet 2](runs/verification/bay-boundary-audit/b08-proposal/labels-2.png), [sheet 3](runs/verification/bay-boundary-audit/b08-proposal/labels-3.png), [sheet 4](runs/verification/bay-boundary-audit/b08-proposal/labels-4.png). No occupied examples were added. Reference and MOG2 two-state calibration still report insufficient occupied examples.

The final cache is `data/chad-mapped/Camera-1/preset-6c74713aff4fc87e/`; the old `preset-36a2f03813a8db2c/` is retained. Polygon-bound Reference, MOG2 and empty-match metadata were regenerated. B08's fitted empty-match limit changed from **0.0140923606 to 0.0142640484** under the existing fitting formula and reviewed samples. This is geometry-dependent recalibration, not a manually selected threshold change. The image hashes are unchanged because these are the same source frames; the polygon signature changed from `58e327f5…` to `2359fcd2…`.

The first geometry replay exposed an alignment side effect: adding curb pixels to the background feature mask rejected Camera-1 recording `chad-4` at 12s. That run is retained under `runs/verification/bay-boundary-audit/replay/`. B08 now has a separate `alignment_exclusion_polygon` equal to the old broad exclusion. Only background feature selection uses it; bay scoring/display use the corrected asphalt polygon. Alignment limits remain unchanged. The successful replays preserve all original alignment decisions and raw detections.

## Overlap rule and safety decision

`src/parking_probe/bay_overlap.py` computes continuous box intersection divided by actual bay area, the existing profile anchor, the estimated lower-box anchor at 82% box height, and overlaps with all mapped bays, including settled neighbours. Concave footprints use rectangle clipping; convex footprints retain the existing OpenCV calculation. This lets B08 follow the curb without measuring its bounding rectangle as the bay.

The candidate may exempt a small spill only when both anchors are safely inside the same unique neighbouring bay, the existing **0.80** detector threshold and **0.25** owner-coverage requirement pass, no competing near-anchor ownership exists, and the target spill is below the experimental cutoff. Weak detections, small own-bay detections, uncertain ownership, edge anchors and large/spanning boxes block vacancy. Every other guard remains required: same-frame successful inference, aligned non-stale image, reviewed visibility, no classic occupied conflict, usable matching reviewed reference when configured, and three consecutive three-second samples scoped to camera/recording/bay. Missing references retain the explicitly provisional route; configured unusable references cannot use that route.

Normal Run retains its existing padded-box veto and occupied/agreement precedence. `vacancy_overlap_mode=diagnostic_only` records the candidate explanation without changing Final. Offline `GuardedVacancy(..., experimental_spill=...)` is the only opt-in; it marks the decision policy experimental. No UI control silently enables it. YOLOv8s COCO/aerial weights, input size, classes, raw floor, NMS and production occupied thresholds were unchanged.

Using identical saved raw boxes, the candidate comparisons were:

| Maximum spill / bay area | Extra vacancies with old geometry | Extra vacancies with corrected geometry | Reviewed occlusion violations |
| --- | ---: | ---: | ---: |
| 0% | 38 | 41 | 1 |
| 5% | 54 | 57 | 1 |
| 10% | 55 | 58 | 1 |
| 20% | 55 | 58 | 1 |
| 30% (“70% outside boxes”) | 55 | 58 | 1 |

These are experimental uncertain-to-vacant observations, not accuracy gains. Geometry alone changes **zero production decisions**; its three additional experimental vacancies occur in B08 in `chad-2`, through changed empty-appearance measurements after removing the curb.

Every candidate cutoff calls **B08 in `chad-4` at 15s vacant despite a pedestrian partially obscuring it**. The reference average still matches, showing why vehicle-box ownership plus average appearance cannot guarantee a clearly visible bay. This is a failed visibility safeguard, not a claim that a parked car was present. Production keeps that observation uncertain. None of the candidates was promoted. A small vehicle below the raw detection floor, or a small obstruction diluted in an average pixel score, remains a risk; no segmentation model or pedestrian detector was silently introduced.

The [43-case development review](runs/verification/bay-boundary-audit/development-visual-labels.csv) includes neighbouring spill, moving cars, small/offset parked vehicles, pedestrians and shadows. There are 38 cases with visible occupancy and five explicitly unresolved/occluded cases. Production makes 12/38 definite decisions (**31.58% coverage**); candidates make 16/38 (**42.11%**). There are zero observed false vacancies among four production and eight candidate vacant predictions on those known cases, but every candidate fails the occluded case above. These selected, correlated development examples are not independent validation. Synthetic missed-detection/occlusion tests supplement them; they do not establish real-world recall.

## Full production replay

Baseline: `runs/areas/20260923T114108_587187Z`. Final replay: `runs/verification/bay-boundary-audit/replay-final/`.

All eight recordings, **60 frames / 1,088 bay observations**, were replayed with the unchanged YOLOv8s profiles. **Every raw detection list and model configuration field matches the corresponding baseline frame exactly.** Reference/MOG2/YOLO states and YOLO reasons also match. All 20 ten-second/partial windows reconcile with their bay counts.

| Recording | Before occupied / vacant / uncertain / unknown | After occupied / vacant / uncertain / unknown |
| --- | --- | --- |
| CHAD-1 | 22 / 21 / 47 / 0 | 22 / 21 / 47 / 0 |
| CHAD-2 | 22 / 45 / 32 / 0 | 22 / 45 / 32 / 0 |
| CHAD-3 | 14 / 28 / 21 / 0 | 14 / 28 / 21 / 0 |
| CHAD-4 | 22 / 58 / 19 / 0 | 22 / 58 / 19 / 0 |
| Camera 2 | 10 / 3 / 12 / 0 | 10 / 3 / 12 / 0 |
| Camera 3 | 8 / 2 / 6 / 0 | 8 / 2 / 6 / 0 |
| Camera 4 | 2 / 0 / 4 / 0 | 2 / 0 / 4 / 0 |
| Overhead | 482 / 64 / 144 / 0 | 482 / 64 / 144 / 0 |
| **Total** | **582 / 221 / 285 / 0** | **582 / 221 / 285 / 0** |

[Full comparison](runs/verification/bay-boundary-audit/replay-comparison.json), [per-recording/per-bay counts and blockers](runs/verification/bay-boundary-audit/production-per-bay.csv), [production changed decisions](runs/verification/bay-boundary-audit/production-changes.csv). There are no changed production decisions. Each candidate has its own `*-changes.csv` with every changed recording/frame/bay, old/new state, streak, reference score/limit, actual overlaps and owner evidence. The JSON includes all candidate counts for every bay, including unchanged ones.

B08's actual production blocker is the nearby vehicle box on all 39 Camera-1 samples. Camera-2 F02 has weak/ambiguous YOLO overlap on all five samples; F03 has the nearby-box veto. Camera-3 F02 also has the nearby-box veto. Camera-2 F04 and Camera-3 F03 complete their guarded streaks. Camera-4 N10/N11 stop at streak 2. Other bay-specific blockers are listed in the CSV; uncertainty is not attributed wholesale to a missing guard.

## Camera 4 and held-out limits

The original `4_075_0.mp4` is 4.9667s and supplies only 0s and 3s. Its two unresolved bays cannot complete a three-sample streak.

A longer same-camera member, **`4_074_0.mp4` (13.2667s, 398 frames, 30fps)**, was legitimately retrieved by byte ranges from the already pinned public CHAD archive and verified against the cached member name/size/CRC. Its SHA-256 is `29705d20211d9f81141b64c3cca9a1459dad509f7027e545a9788fe783574556`. [Source/provenance record](runs/verification/bay-boundary-audit/camera4-longer-source.json). It is stored separately under `data/chad-boundary-review/` and is not added to normal Run or combined with the original clip.

Five frames (0/3/6/9/12s) were visually labelled before inference: N09 and N11 have parked vehicles; N10's ground is obscured by the foreground sedan. [Labels](runs/verification/bay-boundary-audit/camera4-holdout-labels.csv), [annotated last frame](runs/verification/bay-boundary-audit/camera4-longer-12s-bays.png). The existing setup alignment detects approximately **29–31px displacement**, beyond its unchanged 8px limit. All 15 bay observations therefore remain **unknown**, with no completed streak and no YOLO inference applied. References/calibration were not fitted on these frames.

This gives **0% decision coverage**, zero vacant predictions, and an undefined false-vacant-per-vacant-prediction rate. It demonstrates rejection of an incompatible view, not successful occupancy accuracy. Although it is a separate file withheld from fitting, publisher capture times are unknown and its labels are Codex visual review rather than independent human adjudication. **Accuracy and general false-vacant risk have not been established on held-out, manually labelled separate capture periods across the views.** Additional independently adjudicated data, including small/missed vehicles and occlusion, are required before enabling a neighbour exemption.

## Verification and reproduction

`python -m pytest -q`: **304 passed**. The 26 added focused tests cover own-bay/small/weak vehicles, neighbour spill, spanning/competing/edge anchors, concave intersection, missed detections with a reference mismatch, pedestrian-like/shadow appearance changes, explicit occlusion, reference/calibration invalidation, separate alignment masks, invalid times and Camera 4's two-sample limit. Existing tests cover failed inference, stale frames, gaps, camera/recording resets, backward seeking, playback, provisional labelling and occupied precedence. An initial GUI run hit a transient missing Tk runtime file; the GUI module retry and subsequent complete test run passed without code or runtime-file changes for that issue.

The actual interface was exercised on **all 60 samples in all eight recordings**: three-second hold behavior, separate Reference/MOG2/YOLO/Final columns, chart legends, video overlays, areas, ten-second summaries and seek resets. [GUI result](runs/verification/bay-boundary-audit/interface/result.json), [Camera-1 overlay](runs/verification/bay-boundary-audit/interface/chad-1-video.png), [overhead overview](runs/verification/bay-boundary-audit/interface/overhead-1-overview.png). No Tk callback errors occurred.

```powershell
# Re-export native before evidence using the archived baseline recipe.
.\.venv\Scripts\python.exe checks/bay_boundary_audit.py
.\.venv\Scripts\python.exe checks/write_boundary_review.py
# Audit an existing replay, or omit --existing-run and choose a fresh --out.
.\.venv\Scripts\python.exe checks/check_bay_overlap.py --existing-run runs/verification/bay-boundary-audit/replay-final
.\.venv\Scripts\python.exe checks/review_boundary_labels.py
.\.venv\Scripts\python.exe checks/check_boundary_interface.py --run runs/verification/bay-boundary-audit/replay-final
.\.venv\Scripts\python.exe -m pytest -q
```

[Brief review/edit guide](BAY_BOUNDARY_REVIEW_GUIDE.md). The tracked visual-review JSON and archived preset preserve the review decisions; large native images, replays and model/data caches remain in the existing ignored `runs/` and `data/` directories. No model, source recording, production detector threshold, physical ID or site inventory was replaced.
