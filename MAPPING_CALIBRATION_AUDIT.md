# Mapping, calibration and YOLO audit from the original version

**22 September 2026.** The user asked why the original Reference/MOG2 display looked better, whether missing reference mappings cause uncertainty, which YOLOv8 size is running, and why its results vary. This is a diagnostic audit; it does not change production polygons, thresholds, reference labels, models or decision rules.

## Findings

The main implementation gap is **incomplete calibration of the expanded bay inventory**, combined with a strict vehicle-detection cutoff and the successive changes to the extra empty-image decision path. Drawing a polygon, assigning an ID, attaching an empty reference and calibrating a classifier are four distinct steps. The expanded interface includes bays that completed only the first two or three steps.

### The original working bays did not regress

Compared original Reference/MOG2 run `runs/comparison/20260917T161258_089149Z` with the current actual UI run `runs/areas/20260921T161408_115721Z`, matching recording, source frame and bay ID:

- **117 matching observations** of B01/B02/B03 across the four original Camera 1 recordings.
- **Zero Reference or MOG2 state changes.** Every original recipe field for these three bays, including polygons and label selections, is preserved.
- All **62 original vacant** and **27 original occupied** consensus results remain the same.
- Of 28 original unresolved observations, YOLO now supplies occupied for 14; 14 remain unresolved. This is a decision comparison, not independent accuracy measurement.

The early display monitored only these three selected, calibrated bays. Later changes expanded Camera 1 to nine bays, added the other camera angles and expanded overhead to 69. Comparing the earlier small calibrated subset with that full inventory made the system look as though the original methods had stopped working.

### Exact current setup coverage

| View | Mapped polygons | Usable empty references | Fully calibrated Reference + MOG2 | Reference present but incomplete calibration | No empty reference |
| --- | ---: | ---: | ---: | ---: | ---: |
| CHAD Camera 1 | 9 | 8 | 3 | 5 | 1 |
| CHAD Camera 2 | 5 | 3 | 0 | 3 | 2 |
| CHAD Camera 3 | 4 | 2 | 0 | 2 | 2 |
| CHAD Camera 4 | 3 | 2 | 0 | 2 | 1 |
| Overhead | 69 | 15 | 3 | 12 | 54 |

These are bay/view entries, not additive unique site capacity. All configured reference files load at the correct resolution; no configured reference was lost or broken. The missing entries are genuinely absent from the configuration.

- Camera 1: B01-B03 are calibrated. B04-B08 each have **20 vacant and zero occupied examples**. B09's SUV bay has no empty reference.
- Camera 2: F02/F03/F04 each have five vacant and zero occupied examples. N09/F01 have no empty reference.
- Camera 3: F02/F03 each have five vacant and zero occupied examples. N09/F01 have no empty reference.
- Camera 4: N10/N11 each have five vacant and zero occupied examples. N09 has no empty reference.
- Overhead: W01/W02/E01 are calibrated. Twelve additional bays have reviewed empty-only examples; 54 have no empty reference.

Reference requires a valid reference and separate vacant/occupied score distributions before assigning a state. MOG2 also requires a verified empty background and fitted per-bay boundaries. Thus an existing empty image can still produce Reference **unknown** (`missing_or_invalid_calibration`) and MOG2 **uncertain** (`mog2_uncalibrated`). Missing references produce unknown directly. A stationary empty image cannot supply the missing occupied examples.

This is a setup-completeness issue in my implementation. The UI's mapped-bay count should not be read as a count of fully calibrated classifiers.

## Polygon and reference-image inspection

Checked all **90 bay/view polygons** for valid coordinates at the actual analysis resolution, matching runtime/recipe geometry and unique local/physical IDs within each view. Reviewed the five annotated last-frame views and the saved empty-reference galleries. CHAD frames and overlays use the same 1280x720 coordinate system; overhead uses 1100x720 with guarded registration. The latest 60 sampled frames have **zero alignment errors and zero YOLO inference errors**.

There is no broad coordinate-scale error or shifted mapping explaining the unresolved bays. This is a visual/code sanity check, not a surveyed ground-truth polygon validation.

Two local details deserve distinction:

- Overhead WR07 and W02 overlap by a **one-pixel-high strip**, about 2.28% of the smaller continuous polygon area. A diagnostic-only in-memory trim of WR07's bottom edge removes the overlap and changes **zero YOLO bay states across all ten overhead samples**. It does not explain the widespread uncertainty. The production preset remains unchanged in this audit.
- Camera 2 F02 is physically empty in the inspected last frame, but the axis-aligned detection box of the neighbouring F01 vehicle touches it. The conservative association rule reports weak/ambiguous overlap. This is a box-to-bay association limitation; making that box disappear or moving the painted bay polygon to fit it would be misleading.

Reviewed reference crops show the correct bay surfaces. Neighbouring vehicle edges, shadows, people and lighting can still alter those pixels in later frames. In particular, an empty reference is not a guarantee that every later empty frame falls below the calibrated difference boundary.

Annotated coverage maps (green = both calibrated, amber = empty reference only, purple = no empty reference; white rectangles are vehicle detections):

- [Camera 1](runs/verification/mapping-calibration-audit/chad-last.jpg)
- [Camera 2](runs/verification/mapping-calibration-audit/chad-camera-2-last.jpg)
- [Camera 3](runs/verification/mapping-calibration-audit/chad-camera-3-last.jpg)
- [Camera 4](runs/verification/mapping-calibration-audit/chad-camera-4-last.jpg)
- [Overhead](runs/verification/mapping-calibration-audit/overhead-last.jpg)

The same directory includes setup-frame overlays, [per-bay.csv](runs/verification/mapping-calibration-audit/per-bay.csv) and [report.json](runs/verification/mapping-calibration-audit/report.json), with every bay's reference status, counts, method reasons, final state and detector evidence. Actual empty crops are linked in [EMPTY_REFERENCES.md](EMPTY_REFERENCES.md).

## Which model is running

Both current profiles are **YOLOv8s (small)**, not YOLOv8n. Normal Run uses one chosen YOLO profile per camera frame, through OpenCV DNN on the CPU. The earlier MobileNet-SSD supplement is a separate historical path; it is not stacked before YOLO in normal Run.

| Camera group | Weights | Exported file | Classes |
| --- | --- | --- | ---: |
| CHAD | Official Ultralytics YOLOv8s trained on COCO | `assets/models/yolov8s-coco.onnx` | 80 |
| Overhead | `dronefreak/visdrone-yolov8s`, fine-tuned for aerial imagery | `assets/models/yolov8s-aerial.onnx` | 11 |

Both use static **640x640 input, batch 1, FP32, ONNX opset 12**. Verified file SHA-256 values, ONNX names metadata and all vehicle class indices against [the manifest](assets/models/yolov8s-manifest.json). There is no detected wrong-class-index mix-up. COCO vehicle IDs are 2/3/5/7; aerial vehicle IDs are 3/4/5/8/9. Neither model has a vacant-parking-bay class. Source details and pinned checkpoint revisions are in [YOLOV8-SOURCES.md](third_party/YOLOV8-SOURCES.md).

Primary references: [Ultralytics YOLOv8 variants](https://docs.ultralytics.com/models/yolov8/), [the aerial model publisher](https://huggingface.co/dronefreak/visdrone-yolov8s). Publisher benchmark numbers are not this parking prototype's accuracy.

## Why an occupied-looking bay can remain uncertain or change state

The application accepts a vehicle only at score **0.80 or higher**, with its anchor uniquely inside one bay and sufficient polygon overlap. This cutoff is an application choice, not a built-in requirement of YOLOv8. Ultralytics' prediction API exposes a configurable confidence threshold; its documented default is 0.25. That default is not automatically a suitable parking threshold either. [Prediction settings](https://docs.ultralytics.com/modes/predict/)

At overhead time 27 seconds, six visually occupied unresolved bays have unique candidate vehicle detections:

| Bay | Detector score | Why not accepted |
| --- | ---: | --- |
| WL03 | 0.6981 | Below 0.80 |
| WL09 | 0.5883 | Below 0.80 |
| WL11 | 0.6590 | Below 0.80 |
| WR02 | 0.6652 | Below 0.80 |
| ER05 | 0.7883 | Below 0.80 |
| ER08 | 0.6456 | Below 0.80 |

This is different from YOLO detecting nothing. The box is present but fails the acceptance rule. The other 13 overhead unresolved bays have no qualifying vehicle and cannot get a definite vacancy from the current calibrated branches. No vehicle detection alone is not a vacant prediction.

There is also real threshold-related variation across video frames. For example, the ML05 vehicle has scores **0.814, 0.794, 0.811** at 0/3/6 seconds: Final becomes occupied/uncertain/occupied under the unchanged 0.80 rule. EL05 similarly crosses the boundary: 0.828/0.798/0.820. Full timelines for nine affected overhead bays are saved in the report. These are not occupancy probabilities.

Each approximately 103x43-pixel overhead polygon becomes only about **60x25 pixels** at the model's input scale. Detail loss, camera angle, frame changes and the difference between training imagery and this scene are plausible contributors to score variation. This audit did not perform a controlled larger-resolution/model comparison, so it does not attribute every fluctuation to one of those factors.

Repeated the identical last frame **three times for each of five views**: detections were exactly identical, and all freshly derived YOLO states matched the saved states. There is no evidence of random inference results or a model-loading failure in those checks. Reproducibility does not prove detection accuracy, and distinct video frames can still receive different scores.

## Why the intermediate version looked more complete

The MobileNet-SSD version had an additional empty-reference matching fallback. Comparing 398 CHAD observations from its recorded run to the current version gives **zero Reference/MOG2 state changes**, but **207 previously vacant Final results now uncertain**. Those vacancies came from the extra empty-appearance decision path, not from newly completed two-state calibration.

The first YOLO integration removed that path; the later empty-reference work reinstated it with three-check confirmation; the 22 September correction removed it again after the user required visible method confirmation. That sequence changed the final decision coverage without fixing the underlying missing calibration. The previous apparent completeness was not proof that all bays had been reliably classified by the three displayed methods.

## What should be fixed next

1. Keep the original calibrated B01-B03 as the regression baseline and explicitly track **mapping, reference availability and calibration readiness separately** for every additional bay.
2. For Reference/MOG2, collect separate occupied and vacant examples for the affected bay/view and verify separable score distributions. The current rule needs at least five examples of each state, separate from its reference. A bay that never changes in these short clips cannot supply its missing state; more suitable same-camera footage is required.
3. Evaluate the YOLO cutoff and bay association against manually labelled frames from separate capture periods. Include stationary cars, neighbouring boxes and truly vacant bays. A smaller cutoff may recover detections but must be checked for false occupied assignments; changing it blindly does not solve vacancy recognition.
4. Test more image detail, tiled inference or parking-specific fine-tuning if occupied-bay recall remains inadequate. A larger model alone does not supply a vacant class or missing calibration. If positive vacant classification is required beyond the classic methods, train/evaluate a dedicated occupied/vacant bay classifier with representative labelled crops.

No production threshold, model or occupancy label was changed during this investigation. The audit identifies missing setup and decision-policy limitations instead of forcing certainty. Independent accuracy, false-vacant/false-occupied rates and the planned separate-period evaluation remain outstanding.

## Reproduce

```powershell
.\.venv\Scripts\python.exe checks/audit_mapping_calibration.py
```

Uses cached footage/models, saved runs and the existing ONNX package from the model-export environment. It writes only to `runs/verification/mapping-calibration-audit/`. It does not require new media, new weights or an external inference API.
