# Quick check: why bays remain unresolved

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.

Checked **20 September 2026** at the user's request. This was a diagnostic check; production thresholds, classification rules, models, calibration and UI were not changed.

## Finding

**YOLO inference works, but the integration removed the previous vacancy evidence path.** This is the main regression in how useful the output appears. The new policy can establish occupied from YOLO, but cannot establish vacant from YOLO. If Reference/MOG2 are missing or uncertain, a genuinely empty bay can therefore remain uncertain for the entire video. Long duration alone does not change that decision: temporal confirmation has not been implemented.

The earlier version was not only Reference/MOG2. It also used MobileNet-SSD through OpenCV and a guarded, manually reviewed empty-image bank. That bank could provide vacancy evidence when full classic two-state calibration was missing. When introducing selective YOLO, I disabled that bank, instead of retaining a vacancy-verification stage after the requested YOLO check. This explains the large increase in unresolved vacancies. The user's rule about routing unresolved cases to YOLO did not inherently require losing all empty-image evidence; the integration choice created this limitation.

## Checks performed

- Read the current `yolo.py`, earlier `vehicle.py`, Reference and MOG2 paths, integration code and saved observations.
- Audited the user's newer completed run, `runs/areas/20260919T161628_245646Z`: **60 of 60 inference jobs completed**, no inference errors and no source issues. The overhead source has ten valid samples; its unresolved states are not caused by camera drift rejection in this run.
- Matched **398 CHAD bay observations** to the same recording/frame/bay in the previous SSD run, `runs/areas/20260918T185845_684414Z`. **Zero Reference/MOG2 state changes** occurred. **Zero matching definite classic agreements were overwritten** by YOLO.
- Loaded both actual bundled ONNX models through OpenCV 4.14.0 and ran fresh inference on the last Camera 1 recording-one frame (27 seconds) and last overhead frame (27 seconds). Both reproduced their saved per-bay YOLO states. Model integrity checks passed as part of loading.
- Re-ran the focused YOLO suite: **18 passed in 1.30 seconds**, including trigger, threshold, no-hit, association, queue/error and stale-identity behavior. Passing tests verify the implemented rule, not its usefulness or independently measured accuracy.
- Visually inspected the last overhead frame with the 19 unresolved polygons highlighted. Six contain visible vehicles; the other 13 appear empty. This is a single-frame visual diagnostic, not the planned independent labelled accuracy study.

## Exact before/after CHAD comparison

These counts are repeated bay observations over 50 sampled frames, not 398 different parking spaces.

| Earlier final state | Current final state | Observations |
| --- | --- | ---: |
| Occupied | Occupied | 100 |
| Vacant | Vacant | 62 |
| Vacant | Uncertain | 207 |
| Uncertain | Uncertain | 29 |

The classic branches themselves did not regress. The 207 lost vacancy decisions came from removing the previous supplemental empty-evidence policy. For example, Camera 1 recording one now leaves B04–B08 uncertain at 27 seconds: Reference is unknown, MOG2 uncalibrated/uncertain, and YOLO has no uniquely assigned vehicle. Previously these bays could be declared vacant when their reviewed empty appearance matched.

## The 19 unresolved overhead bays at 27 seconds

**Six occupied-looking bays have detections but fail the 0.80 object-score cutoff:**

| Bay | Best uniquely assigned vehicle score | Reason |
| --- | ---: | --- |
| OVER-WL03 | 0.698 | Below 0.800 |
| OVER-WL09 | 0.588 | Below 0.800 |
| OVER-WL11 | 0.659 | Below 0.800 |
| OVER-WR02 | 0.665 | Below 0.800 |
| OVER-ER05 | 0.788 | Below 0.800 |
| OVER-ER08 | 0.646 | Below 0.800 |

Thus these six are not missing detections; the final acceptance threshold rejects them. Object scores are model outputs, not calibrated parking occupancy probabilities. Lowering a global cutoff without checking false positives would change the trade-off, not establish correctness.

**Thirteen empty-looking bays have no uniquely assigned candidate and no accepted vacancy result:** WL07, W01, ML03, ML11, MR05, MR08, MR10, EL07, EL09, EL11, ER02, ER09 and ER10. Twelve lack the complete classic reference/calibration path. W01 is calibrated but its current appearance lies inside both uncertain bands:

| W01 evidence | Current value | Vacant maximum | Occupied minimum |
| --- | ---: | ---: | ---: |
| Reference difference | 0.017694 | 0.009008 | 0.196856 |
| MOG2 foreground fraction | 0.037587 | 0.017920 | 0.588112 |

A small appearance change relative to the narrow vacant calibration range is sufficient to make W01 uncertain. This check did not isolate which lighting, shadow, interpolation or scene factor caused its score change. Most overhead bays have no full two-state calibration at all: **66 out of 69**. Mapping their polygons includes them in the total, but does not supply missing references or labels.

![Nineteen unresolved polygons at the last overhead frame](runs/verification/unresolved-audit/overhead-1-unresolved.png)

## Why waiting does not resolve it

Reference computes appearance difference, MOG2 computes foreground evidence, and selective YOLO independently verifies each requested sample. The ten-second summary reports the existing observations; it does not convert repeated uncertainty into certainty. The proposal's temporal confirmation/persistence stage remains deferred. An unchanging empty scene supplies no vehicle detection, and the current verifier has no positive empty-state evidence path, so uncertainty can repeat indefinitely. An unchanging car with a score below the cutoff can do the same.

## Appropriate correction after this diagnosis

Retain the requested rule: definite Reference/MOG2 agreement is kept, and any unresolved/disagreeing case still reaches YOLO. Restore **verified empty-reference evidence after verification** to resolve genuinely empty bays when geometry, visibility and appearance match and there is no conflicting vehicle evidence. Populate missing empty evidence from visually checked examples, without using predictions as labels or treating a missed detection alone as vacancy. Keep the evidence/reasons visible.

For low-score occupied bays, inspect labelled examples for this view and evaluate the detector cutoff/association before adopting a different threshold. Temporal confirmation can reduce flicker after usable occupied/vacant evidence exists; repeated uncertainty alone is insufficient. No thresholds were loosened and no states were forced during this quick check.

## Reproduction and files

Added [checks/diagnose_unresolved.py](checks/diagnose_unresolved.py), a read-only audit that writes diagnostic files under `runs/verification/unresolved-audit/`. It compares saved states, re-runs both models on the selected frames, checks per-bay reproduction and reports weak uniquely assigned candidate scores. The report is [report.json](runs/verification/unresolved-audit/report.json); test results are [tests-yolo-quick-check.xml](runs/verification/tests-yolo-quick-check.xml).

```powershell
.\.venv\Scripts\python.exe checks/diagnose_unresolved.py
.\.venv\Scripts\python.exe -m pytest tests/test_yolo.py -q
```

The audit defaults to the diagnosed run and also accepts another run directory as its first argument. It expects the same built-in recordings/recipes and a previous SSD run for comparison. Source code for production inference was left unchanged; the check explains the current limitation rather than claiming it has been fixed.
