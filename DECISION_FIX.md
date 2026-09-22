# Final decisions must be supported by the displayed methods

Updated **22 September 2026** after the user reported that Reference, MOG2 and YOLOv8 could all remain uncertain/unknown while Final said vacant.

## Cause

The 21 September empty-reference change added a fourth, undisplayed decision path. It compared the bay against reviewed empty images and, after three supporting samples plus a successful no-hit YOLO pass, could override Final to vacant. This was an experimental appearance heuristic, **not a YOLOv8 vacant classification**. It did not change the three displayed branch states. The confusing result reported by the user was therefore possible by design, and that design did not meet the user's requested method-confirmed result.

The problem was shared across camera views in `comparison.py`, rather than a failure to load OpenCV or YOLO. All camera mappings, models and actual branch measurements are retained.

## Corrected rule

| Reference / MOG2 | YOLOv8 | Final |
| --- | --- | --- |
| Both vacant | Skipped | Vacant; confirmed by Reference + MOG2 |
| Both occupied | Skipped | Occupied; confirmed by Reference + MOG2 |
| Either unresolved, or disagreement | Qualifying vehicle in this bay | Occupied; confirmed by YOLOv8 |
| Either unresolved, or disagreement | No/weak/ambiguous detection | Uncertain |
| All evidence unavailable | Unknown | Unknown |

The current detector outputs vehicle classes; it has no vacant-parking-space class. Consequently no YOLO detection, a long unchanged image, an empty-bank match, or repeated uncertain samples cannot confirm vacancy. A future vacant classifier must be independently validated before adding a new definite decision path. The score cutoff remains 0.80, with existing unique-bay association and overlap safeguards.

“Confirmed” here identifies which implemented methods support the estimate; it is not a guarantee of correctness or an accuracy claim.

## Code and output changes

- Removed the empty-match override and its parameter from `yolo.final_decision`.
- Removed empty scoring/streak tracking from normal Run's comparison pipeline. Preparation no longer fits the unused bank for each normal replay.
- Kept the reviewed source images, polygons, labels and historical diagnostic utility. They remain useful calibration material; they are not relabelled as model confirmations. The original Reference branch still uses its validated two-state calibration.
- JSON/CSV rows record `final_confirmed_by` as `reference_and_mog2`, `yolov8`, or null. Per-bay final JSON also records `confirmed_by`. Results carry policy `definite_opencv_agreement_else_yolov8_vehicle_else_unresolved_v2`.
- The same final result feeds the chart, area counts, video overlays, saved summaries and ten-second windows. Selecting a bay states its confirming method or “No method confirmation”. YOLO shows SKIPPED when classic agreement made inference unnecessary.
- Historical output directories are retained. Restarting the interface creates a new run with the corrected rule; an already-running Python process continues using the code it loaded earlier.

## What is still needed to recognize more empty bays

Only three overhead bays currently have full two-state classic calibration. Fifteen overhead bays have reviewed empty examples, but empty examples alone cannot demonstrate that the classifier distinguishes a parked vehicle from an empty bay. CHAD's additional bays have the same data limitation where recordings show only one state.

For the current Reference/MOG2 approach, obtain at least five separate vacant and five occupied examples for each affected bay, separate from the reference, and check that their score distributions separate. If they overlap, retain uncertainty and use better viewing conditions or a different classifier. A parking-specific vacant/occupied classifier trained and evaluated on representative labelled bay crops is another route; the existing vehicle-only YOLO weights cannot be renamed into such a classifier. Independent accuracy and false-vacant/false-occupied rates still require separate labelled capture periods.

No reference was invented, no prediction was converted into a ground-truth label, and no confidence threshold was reduced to make the output definite.

## Run and verify

1. Close the old parking window and run `main.py` again in VS Code with the project's `.venv` interpreter.
2. Wait for preparation, then select the site/view/recording. Open Occupancy overview and click a bay to see its confirmation source.
3. Read uncertain as **not confirmed**, never as available parking. No additional download or installation is needed here.

Reproducible all-view check:

```powershell
.\.venv\Scripts\python.exe checks/check_decisions.py --baseline runs/areas/20260920T171708_941751Z
.\.venv\Scripts\python.exe -m pytest -q
```

The checker validates all eight recordings, charts and final window states, audits the prior run by camera/recording, and writes [decision-check.json](runs/verification/decision-check.json). See [FINAL_RESULTS.md](FINAL_RESULTS.md), [VALIDATION.md](VALIDATION.md) and [WORK_LOG.md](WORK_LOG.md) for measured results and the full record.

## Measured all-camera audit

| Recording | Prior vacant without classic agreement | Prior vacant with all three unresolved |
| --- | ---: | ---: |
| Camera 1 / recording 1 | 28 | 27 |
| Camera 1 / recording 2 | 46 | 44 |
| Camera 1 / recording 3 | 21 | 19 |
| Camera 1 / recording 4 | 43 | 43 |
| Camera 2 | 6 | 6 |
| Camera 3 | 4 | 4 |
| Camera 4 | 0 | 0 |
| Overhead | 97 | 94 |

These count bay observations across sampled frames, not unique parking spaces. The corrected real UI replay has zero unsupported definite decisions across 1,088 observations. All 244 tests passed. Current overhead: 48 occupied, 2 vacant, 19 uncertain; removing the unsupported confirmations does not by itself improve the models' ability to recognize vacant bays.

The before/after match found zero Reference, MOG2 or YOLO state changes; 245 heuristic vacant observations became uncertain. See [decision-before-after.json](runs/verification/decision-before-after.json). This correction enforces honest method-supported results; it does not solve missing vacant-state training/calibration data.
