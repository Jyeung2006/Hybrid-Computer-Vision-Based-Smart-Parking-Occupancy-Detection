# Mapped CHAD cameras and vehicle evidence

**22 September audit:** the original three calibrated CHAD bays retain all 117 Reference/MOG2 observations unchanged. Additional mapped bays have incomplete reference/calibration coverage. Both active profiles are YOLOv8s (small). See [MAPPING_CALIBRATION_AUDIT.md](MAPPING_CALIBRATION_AUDIT.md) for the per-view table, exact models and score/mapping checks.

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.

## Current selective-YOLO implementation — 19 September 2026

Normal Run now uses **Reference / MOG2 / YOLOv8 / Final estimate**. Matching definite classic results are retained; uncertain, missing or conflicting evidence triggers YOLOv8s. No qualifying detection remains uncertain. This supersedes the earlier SSD Vehicle/empty-bank decision rule and its vacancy counts below. CHAD mappings remain 9/5/4/3 bays across Cameras 1/2/3/4; overlapping periods are not fused.

The overhead site now maps **all 69 visible painted bays**, divided west 24 / middle 22 / east 23. Guarded registration corrects this clip's small drift; all ten samples remain usable. Only three bays have full classic calibration; YOLO verifies the others. The former three-bay subset and later-drift failure below are historical.

Current details: [YOLOV8.md](YOLOV8.md), [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md), [FINAL_RESULTS.md](FINAL_RESULTS.md), [QUICK_START.md](QUICK_START.md). YOLO verification is now implemented; later probability fusion, temporal confirmation and persistence remain deferred.

## Earlier implementation and source history

The following dated record preserves the prior algorithms, measurements and source research. Its descriptions of no YOLO, Vehicle fallback, three overhead bays and unavailable later overhead frames are superseded above.

Updated **19 September 2026**. Cameras 2–4 now have their own polygons, stable local IDs, frame analysis, per-bay states, annotated playback and summaries. Camera 1 analyzes all nine mapped bays. The user explicitly authorized adding a pretrained OpenCV vehicle detector when incomplete examples prevented Reference/MOG2 calibration.

## Views and identity

| Actual camera | Recording(s) | Mapped inventory | Identity limits |
| --- | --- | --- | --- |
| Camera 1 | 1_029_0, 1_038_0, 1_049_0, 1_054_0 | P001–P007 far row; P008/P009 near row | Four periods of this same view; not four cameras. |
| Camera 2 | 2_036_0 | P009; C2-F01–C2-F04 | Far-row IDs are view-local pending verified correspondence. |
| Camera 3 | 3_073_0 | P009; C3-F01–C3-F03 | Far-row IDs are view-local pending verified correspondence. |
| Camera 4 | 4_075_0 | P009/P010/P011 | Three storefront-row bays; hatched access area excluded. |

All IDs above have the `CHAD-` prefix. These are visible subsets, not full camera/site capacity. Polygons are at 1280x720 analysis resolution. Camera 3 mapping was corrected against painted boundaries and a clipped fourth far-row region was removed. Camera 2's last polygon excludes the foreground shrub.

P009 is the storefront SUV bay, manually associated across all four views using the storefront/patio layout and the [publisher's camera diagram](https://github.com/TeCSAR-UNCC/CHAD). P008 is the adjacent near bay in Camera 1; it is **not** Camera 4's P010/P011. Camera 1 can assess P008/P009 directly, so no alternate-view state is substituted. Camera 4 does not provide a reliable unobstructed P008 polygon.

Cross-view SIFT/homography trials produced too few reliable correspondences and were rejected. The code does not automatically identify arbitrary matching bays. Camera 2/3 far-row correspondence remains unverified and is explicitly labelled view-local; their capacities are never added to Camera 1's capacity.

Selected recordings have no verified synchronized capture offsets. A view's P009 observation is historical for that recording only. Even when two clips show the same SUV, this does not establish simultaneous recording times. Final method fusion happens within the same frame; cross-camera/time averaging is not performed. A proper synchronized installation still needs a surveyed bay registry and verified time alignment.

## Why Reference and MOG2 can remain unresolved

The original P001–P003 retain two-state calibration. Several added bays show only empty ground; P009 never supplies a verified empty reference in the selected clips. The original requirement of at least five empty and five occupied examples remains in force. Reference reports unknown without valid calibration/reference; MOG2 reports its own missing-reference or uncalibrated state. An occupied vehicle is not used as an empty MOG2 background.

The new **Vehicle** column uses [MobileNet-SSD](https://github.com/chuanqi305/MobileNet-SSD) through OpenCV DNN, with no YOLO. It can recognize visible vehicles without a bay-specific empty image. Model attribution, revision and integrity hashes are in [third_party/MOBILENET-SSD.md](third_party/MOBILENET-SSD.md).

## Supplemental evidence and final decision

1. Decode/validate the frame using the existing resolution, freshness and setup-alignment guards. Failure yields unknown; no stale occupancy is asserted.
2. Run CPU detection on the full image and four overlapping crops. Remove duplicates using overlap/containment. Keep car, bus and motorbike candidates from score 0.25.
3. Associate a detection to one convex bay polygon using a lower-box anchor at 82% of box height. An occupied match requires score at least 0.65, anchor at least 3 pixels inside the bay, and box intersection at least 20% of bay area. Ambiguous or weak overlaps block vacancy.
4. Vacancy requires a manually reviewed empty-image match **and** no conflicting vehicle overlap. No vehicle detected is insufficient. Gaussian/grayscale normalized mean absolute difference is used, not an occupancy probability.
5. Opposing definite states from any methods yield **uncertain**. Otherwise agreement between Reference and MOG2 is used; a definite Vehicle result can supplement incomplete Reference/MOG2 evidence. All methods unavailable yields **unknown**; remaining incomplete evidence is **uncertain**.

The detector score and empty-difference score measure different things and are never averaged. A model can miss vehicles or mistake objects for vehicles; ground polygons and box anchors are approximate, especially with oblique views. These are per-frame occupancy estimates, not proof that a vehicle has remained parked. Temporal confirmation and independent accuracy evaluation remain outstanding.

## Reviewed empty images

`presets/chad-camera-1-expanded.json` preserves the original three-bay calibration and adds B04–B08 with reviewed vacant examples. Their empty bank contains Camera 1 recording 1 at 0s, recording 2 at 0s, recording 3 at 10s, and recording 4 at 0s, subject to alignment/hash checks. Reference images are distinct from the five vacant example frames per period. B09 has no empty bank. Other cameras use reviewed frame-0 empty images with five distinct vacant examples where available.

This is explicitly a **vacant-only supplemental heuristic**, not two-state calibration. The per-bay tolerance is `min(0.04, max(0.012, 1.5 * vacant-score 95th percentile + 0.005))`. It measures the minimum difference to the reviewed bank. Pixel hashes bind references/setup/polygons to the tolerance; mismatches disable that evidence. References are never replaced automatically. All recipe times, labels and polygons are in the four preset JSON files; generated manifests/configs are under `data/chad-mapped/Camera-N/preset-.../`.

Camera 1 recording 4 contributes empty examples to the expanded vehicle demonstration. It therefore is **not an independent held-out evaluation** of that branch. Historical held-out descriptions for the original three-bay terminal experiment do not apply to this expanded demo.

At the last sample of Camera 1 recording 3, P004–P008 still differ from the reviewed empty bank beyond their tolerances. They remain uncertain rather than being forced vacant. The near SUV P009 remains occupied. This is recorded explicitly in [FINAL_RESULTS.md](FINAL_RESULTS.md).

## Output and validation

The interface shows **Bay ID / Reference / MOG2 / Vehicle / Final estimate**, with selectable explanations, a circle chart, coloured video overlays and scrolling ten-second summaries for all mapped CHAD bays. Empty/occupied counts and unresolved ranges refer only to that selected view. Area rows follow its selected recording and show sample time.

Runs are saved under `runs/areas/<UTC-run>/`, with `chad/`, `chad-camera-2/`, `chad-camera-3/`, `chad-camera-4/` and `overhead/` subfolders. CHAD reports include four method folders, per-sample JSON/CSV, detections, reasons, difference/model scores, processing timings, ten-second histories and final summaries. Top-level inventory/source-status/area-summary files document scope and failures. The overhead branch remains Reference/MOG2 only. Original source capture times remain unknown.

Recorded analysis is prepared chronologically before playback to preserve MOG2 state and allow safe seeking. The interface reveals estimates every three video seconds; completed windows appear at ten seconds or at the end of a shorter clip. A 4.97-second Camera 4 clip only produces a final partial window, not an invented ten-second observation.

Automated and actual-video results are in [VALIDATION.md](VALIDATION.md). Demonstration coverage is measurable; independent accuracy, false-vacant and false-occupied rates are not yet established for this expanded detector. A suitable next evaluation needs separately captured, manually labelled occupied and vacant examples for every target bay, without reusing the setup/empty bank or calibration periods. No external live camera has been tested.
