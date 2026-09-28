# OpenCV-first recorded parking estimates

The normal popup now shows **Reference, MOG2, MobileNet + empty, YOLOv8, and Final** for each mapped bay. The older MobileNet-SSD model is loaded locally through OpenCV DNN. Its reviewed-empty appearance result is displayed under MobileNet, not misreported as a calibrated Reference classification. YOLOv8 is requested for a bay only when all three OpenCV routes are unresolved or when definite Reference and MOG2 results conflict. A full-frame YOLO pass may still run when another bay in the same frame needs verification.

## Decision flow for each bay

The program samples each recording every three video seconds. It analyzes the same sample with the calibrated empty-image **Reference** comparison, the **MOG2** foreground model, and the local **MobileNet-SSD + reviewed-empty** route. Reference compares the bay image with its reviewed empty image and uses calibrated vacant/occupied score boundaries; a score between boundaries is uncertain, and missing valid calibration is unknown. MOG2 measures foreground in the bay against its own calibrated boundaries; a boundary gap, missing calibration, or restabilization can leave it uncertain. MobileNet detects and assigns vehicles to bay polygons; where no vehicle overlaps ambiguously, a close match to a reviewed empty appearance can instead establish vacancy. No vehicle detection by itself does **not** establish vacancy.

```mermaid
flowchart TD
    A[Valid sampled frame: Reference, MOG2, MobileNet + empty] --> B{Reference and MOG2 definite?}
    B -->|Same state| C[Final = their shared state; skip YOLO for this bay]
    B -->|Opposite states| D[Request YOLO for this bay]
    B -->|Only one definite| E[Final = that definite state; skip YOLO for this bay]
    B -->|Neither definite| F{MobileNet + empty definite?}
    F -->|Yes| G[Final = MobileNet occupied or reviewed-empty vacant; skip YOLO]
    F -->|No| D
    D --> H{Qualifying YOLO vehicle in this bay?}
    H -->|Yes| I[Final = occupied; source YOLO]
    H -->|No, classic methods conflict| J[Final = Reference state; record conflict and YOLO outcome]
    H -->|No, all OpenCV unresolved| K{Eligible reviewed-empty guard: three clean samples?}
    K -->|Yes| L[Final = vacant; source reviewed-empty guard]
    K -->|No, valid frame and successful YOLO pass| M[Final = OCCUPIED (P); provisional]
    K -->|No, frame or model unusable| N[Final = unknown]
```

YOLO keeps its existing vehicle confidence and bay-association checks. A full-frame model pass may be needed when **any** bay requests it, but its detections cannot change another bay already resolved by OpenCV. A YOLO non-detection is not evidence of vacancy. The guarded vacancy branch requires a reviewed empty match and three consecutive clean observations; the old no-reference provisional vacancy route is disabled in normal OpenCV-first runs.

## Why the camera can show uncertain boxes while the overview says occupied

The **Reference, MOG2, MobileNet, and YOLOv8 columns are separate method outputs**; an uncertain result in one column does not mean Final is uncertain. Another method may be definite. If all methods fail to decide on a valid sample, the user-selected occupied fallback makes Final **OCCUPIED (P)**. This is a conservative availability assumption, **not** a confirmed vehicle or a measured accuracy improvement. It contributes to the occupied count but remains separately counted as provisional. If the frame or verification is unusable, Final stays **unknown** instead of guessing.

In the popup's **Watch video** view, the bay outline reflects **Final**, not the Reference column. A provisional occupied outline is amber and carries `O(P)`; its color can look like an uncertain outline at a glance. Check the **Final estimate** column and click the bay to read its exact source and reason. If viewing a separately saved Reference or MOG2 image, its uncertain boxes are that method's raw result and may legitimately differ from Final. The overview chart, areas, Watch video outlines, ten-second summaries, and saved Final rows use the same Final decision. Camera footage between three-second samples retains the most recent sampled estimate, so a momentary view can also differ from the last analysis frame.

Final uses matching Reference/MOG2 results first, then either definite classic result, then MobileNet for two unresolved classic results. A Reference/MOG2 conflict requests YOLO; a qualifying vehicle means occupied, otherwise Reference wins. For all-OpenCV-unresolved bays, a qualifying YOLO vehicle means occupied; a reviewed-empty three-sample guard can still establish vacancy. With a valid frame and successful YOLO pass but no definite result, Final is **OCCUPIED (P)**: a provisional occupied guess, counted as occupied and shown separately in the popup, areas, video, ten-second reports and saved rows. Failed or unusable frames remain unknown. The former no-reference provisional vacancy route is disabled under this policy.

The 24 September B08 curb-edge geometry and active alignment/overlap diagnostics were rolled back to the pre-audit preset. Saved audit evidence remains available under `runs/verification/bay-boundary-audit/`; that geometry is historical, not the normal Run preset. Other preset polygons, IDs, model weights and detection thresholds were not changed.

The full replay report is [report.json](runs/verification/opencv-first/report.json), and the [GUI check](runs/verification/opencv-first/interface/result.json) loads its saved results without inference. Across 1,088 sampled bay observations, the previous Final was **582 occupied / 221 vacant / 285 uncertain / 0 unknown**. OpenCV-first produced **684 occupied / 404 vacant / 0 uncertain / 0 unknown**, including **96 provisional occupied** observations. YOLO requests fell from **987 to 573** bay observations, including **262 to 15** across Camera 1's four recordings. These are repeated observations, not unique bays or independent accuracy trials. Reference and MOG2 states match the saved baseline for every paired frame.

**Known limitation:** B08/CHAD-P008 in `chad-4` at 15 seconds is marked vacant by MobileNet's reviewed-empty route even though a pedestrian partly obscures the bay. The old MobileNet model did not detect that person; the empty score remains below the fitted limit. The restored route thus has a known obstruction false-vacant case. Do not interpret zero uncertain results as validated accuracy. Independent labelled frames, particularly pedestrians, shadows, small vehicles and neighbour spill, are needed before making an accuracy claim.

## Processing time and live-use scope

The current popup is a **recorded-video review application**. It completes all selected recordings' analysis before enabling playback; the Live camera tab is a viewer and does not yet run this occupancy pipeline on incoming frames. That full-recording wait is an application workflow choice, **not** the time needed to analyze one new camera frame. A true live version would need to capture and analyze frames continuously, update the display as results arrive, and handle frames that are late or unavailable.

The following are measured **per sampled frame, not per bay**, from the local OpenCV-first run at `runs/areas/20260924T195956_624775Z`. It contains 50 CHAD frame analyses (39 Camera 1, 5 Camera 2, 4 Camera 3, 2 Camera 4) and 10 overhead frame analyses, at three-video-second intervals. These are observed desktop timings, not a live-camera benchmark or a guaranteed frame rate. Medians and 95th-percentile sample values are rounded to milliseconds.

| Stage | CHAD median / p95 | Overhead median / p95 | Scope |
| --- | ---: | ---: | --- |
| Video frame decode | 120 / 171 ms | 92 / 108 ms | Local MP4 retrieval; live camera capture/network cost would differ |
| Reference | 32 / 43 ms | 25 / 27 ms | Includes frame validation/alignment and empty-image comparison |
| MOG2 | 11 / 15 ms | 23 / 31 ms | Foreground model and per-bay scoring |
| MobileNet + empty match | 87 / 104 ms | 83 / 88 ms | Detector plus reviewed-empty comparison and bay assignment |
| YOLOv8 **when requested** | 182 / 275 ms (11 frames) | 209 / 263 ms (10 frames) | Entire selective verification branch; skipped calls excluded |
| YOLOv8 model inference within requested calls | 182 / 275 ms | 195 / 250 ms | Inference only; overhead branch also has association work |

Adding local video decode to the saved Final branch's summed method times gives an **approximate** median per-frame processing cost of **241 ms** for Camera 1 frames without YOLO (28 frames), **431 ms** for Camera 1 frames with YOLO (11 frames), and **437 ms** for overhead frames (all 10 requested YOLO). These estimates exclude popup rendering, file/report writing, model startup, calibration, and any live-camera capture or network delay. They should not be read as independently measured end-to-end live latency. The current sampling interval is three video seconds, so these per-frame measurements alone do not make the existing popup a live occupancy monitor.
