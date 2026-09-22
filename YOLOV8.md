# Selective YOLOv8 verification

**22 September audit:** the original three calibrated CHAD bays retain all 117 Reference/MOG2 observations unchanged. Additional mapped bays have incomplete reference/calibration coverage. Both active profiles are YOLOv8s (small). See [MAPPING_CALIBRATION_AUDIT.md](MAPPING_CALIBRATION_AUDIT.md) for the per-view table, exact models and score/mapping checks.

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.

Implemented 19 September 2026. Normal VS Code **Run** now shows Reference, MOG2, YOLOv8 and Final estimate for every mapped bay. See [QUICK_START.md](QUICK_START.md) for use, [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md) for all 69 overhead bays, and [FINAL_RESULTS.md](FINAL_RESULTS.md) for measured outputs.

## Decision rule requested by the user

| Reference | MOG2 | Action | Final estimate |
| --- | --- | --- | --- |
| Occupied | Occupied | Skip YOLO for this bay | Occupied |
| Vacant | Vacant | Skip YOLO for this bay | Vacant |
| Occupied | Vacant (or reversed) | Request YOLO | Occupied if verified; otherwise uncertain |
| Either uncertain or unknown | Any state | Request YOLO | Occupied if verified; otherwise uncertain/unknown |

Missing evidence is also routed to YOLO. One full-frame inference serves all requested bays in that frame. Other bays are marked **SKIPPED** in the YOLO column; a detection elsewhere in the same image cannot override their matching definite Reference/MOG2 decisions. Original method results remain visible. If all evidence is unavailable, the result is unknown. Invalid/stale source frames are never submitted as fresh evidence.

The final rule does not average grayscale differences, MOG2 ratios and detector scores: these are different measurements, not calibrated occupancy probabilities. `final_decision()` and `needs_verification()` in [yolo.py](src/parking_probe/yolo.py) implement the rule.

## What a YOLO result means

The implementation follows the proposal's phase-three **YOLOv8s**, 640-pixel full-frame, batch-one verification. A retained vehicle box must have object score **at least 0.80**, including exactly 0.80; intersect at least **25% of the bay polygon's area**; and have its association point inside exactly one qualifying bay. All polygons, including already settled neighbours, participate in association to prevent assigning their cars to another bay. The association point is the box centre in the overhead view and 82% down the box in oblique CHAD views.

Vehicle candidates are parsed at 0.15 and suppressed with class-agnostic NMS IoU 0.45. This lower candidate threshold does not lower the final 0.80 occupied threshold. Weak boxes, ambiguous assignment, or no qualifying box leave the requested bay **uncertain**. Occluded bays or unavailable inference produce unknown verification evidence. **No detection does not establish vacancy.** Therefore a permanently empty bay without sufficient Reference/MOG2 calibration can remain uncertain despite being mapped correctly.

Vacancy currently requires agreement between the two calibrated classic branches. The former MobileNet-SSD/reviewed-empty-bank supplement is retained as legacy code, but is not used by normal Run. This deliberately changes some previously reported vacancies into uncertain results under the newly requested rule.

## Models and runtime

Both profiles use YOLOv8s architecture through **OpenCV DNN on CPU**, with 640×640 letterboxed RGB input, scale 1/255 and padding 114. They are separate fixed view profiles, not two detector votes or two inference passes per frame:

| Profile | Used for | Weights |
| --- | --- | --- |
| `coco` | CHAD Cameras 1–4 | Official Ultralytics YOLOv8s COCO |
| `aerial` | Overhead demo | `dronefreak/visdrone-yolov8s`, trained on VisDrone aerial imagery |

The standard COCO weights produced no vehicle detections above 0.25 on the initial overhead frame, including additional orientation/size/crop development trials. A known bus control image produced a strong bus detection, confirming that inference itself worked. The aerial profile detected overhead vehicles without training on this clip or changing the proposal's threshold. Neither that development check nor the model publisher's metrics establish accuracy on these parking bays.

The two ONNX files are bundled under `assets/models/` (about 85 MiB together). [The manifest](assets/models/yolov8s-manifest.json) pins checkpoint provenance and exported file sizes/SHA-256; runtime verifies integrity before loading. Full source, licensing and export details are in [YOLOV8-SOURCES.md](third_party/YOLOV8-SOURCES.md). No account, API key, CUDA or model download is required for normal Run on this computer. PyTorch/Ultralytics were installed for conversion, but normal inference imports neither.

## Queue, timing and provenance

One daemon worker serves a bounded queue with **one pending frame** (at most one executing plus one waiting). Jobs carry camera ID, frame ID, requested slot IDs, profile and timestamps. Superseded jobs/responses are rejected; completed identity must match the requesting observation. Queue-full, closed worker, inference failure and a five-second wait timeout preserve unresolved results. This recorded prototype waits for each frame's verification before joining its output; it is not a live asynchronous service.

JSON includes requested/skipped slots, model profile, qualifying detections, object scores, queue delay, inference duration, processing completion and source/frame identities. CSV/history, annotated frames and ten-second windows include all four methods. Final processing duration sums the three branch durations; decoding/registration, report writing and rendering are outside that sum. Original camera capture timestamps are unknown; local decode time and video offsets remain explicit.

The interface analyzes recordings chronologically before review, then reveals samples every **three video seconds** and summaries every **ten video seconds**. Seeking reads saved observations rather than teaching MOG2 backwards. Recorded periods and different cameras are not fused into live availability.

## Proposal scope

Implemented: selective verification, YOLOv8s inference, full-frame batching, threshold/association checks, bounded worker, provenance, stale/superseded rejection, separate evidence columns and final per-frame estimates. The user's explicit definite-agreement trigger is used instead of the proposal's probability-trigger stage.

Not implemented in this task: learned logistic probability fusion, three-snapshot confirmation, persistent state transitions, database, Flutter, network service, deployment or automatic cross-view identity matching. These remain later stages. No proposal text was treated as permission to expand those stages.

## Validation and limitations

Automated tests cover the routing matrix, exact threshold boundaries, unique/ambiguous bay association, no-hit uncertainty, failure/stale evidence, queue capacity, timeout, superseded responses, matching identities and full-frame inference reuse. The actual interface check covers all eight recordings and all 69 overhead polygons; details and measurements are in [VALIDATION.md](VALIDATION.md).

Many stationary bays never show both states in the short clip. Only three overhead bays have verified empty references and two-state calibration; the other 66 are still analyzed through selective YOLO. The last measured overhead sample has **48 occupied, 2 vacant and 19 uncertain out of 69**. These are experimental predictions, not manually labelled ground truth. Independent accuracy, false-vacant and false-occupied rates still require at least 30 separately captured, manually labelled evaluation frames.

To improve unresolved bays, obtain verified empty references and at least five separate vacant and five occupied calibration examples per bay, or develop/validate a better detector for this view. Do not mark a bay vacant simply because a vehicle was missed.
