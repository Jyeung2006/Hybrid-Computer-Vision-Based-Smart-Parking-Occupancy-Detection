# Experimental Reference priority comparison

22 September 2026. This is an opt-in comparison beside the existing Final estimate. MOG2 remains in use. The normal Final policy and [DECISION_FIX.md](DECISION_FIX.md) remain unchanged.

## Use it

1. Run `main.py` in VS Code using the project's `.venv` interpreter and wait for preparation.
2. Open **Occupancy overview** and enable **Show alternate: Reference priority (experimental)**. It starts OFF each time you launch the app.
3. Compare **Final estimate** with **EXP: Alternate**. Scroll the table right if needed. Select a bay to see both confirmation sources; scroll the overview down on smaller windows.
4. Use **Reports → View external validation report** for the read-only report. **Open saved results → experimental-reference-priority** contains the opt-in JSONL/CSV comparison.

The chart, video labels, area availability and 10-second summaries always use the primary Final. Turning the toggle off hides the comparison; an already exported historical comparison is retained. No new inference runs when toggling. No download, installation or new URL is needed. The Live camera tab remains a viewer; this feature compares recorded observations, not live parking availability.

## Exact rule and exports

`final_decision_reference_priority(reference, mog2, verified, *, reference_calibrated=False)` is in [alternate_policy.py](src/parking_probe/alternate_policy.py). It uses a calibrated definite Reference **occupied or vacant** result, with `confirmed_by: reference_only_experimental`. Otherwise it delegates to the existing `final_decision` unchanged. In particular, missing YOLO detections do not establish vacancy.

This implements the detailed requested rule, which is broader than the shorthand “Reference-alone vacant.” It can replace a primary YOLO occupied confirmation with Reference vacant. That conflict is deliberately exposed in the comparison and error counts below.

Calibration validity comes from the existing Analyzer's reference/setup/polygon/preprocessing hash checks and valid separated thresholds, captured as `reference_calibrated` in each new replay row. Reference image presence alone is insufficient. The saved-log diagnostic uses the matching saved calibration/config files and checks MOG2 model signatures. Missing provenance defaults to ineligible, never assumed calibrated.

Normal GUI runs save their original primary results plus calibration provenance. Only enabling the toggle writes a separate `experimental-reference-priority/history.jsonl`, `observations.csv` and manifest. Each enriched JSON observation retains primary `final` and adds `final_alt` with `experimental: true`, `primary: false` and the alternate slots/summary. CSV retains all primary fields and adds `final_alt_state`, `final_alt_reason`, `final_alt_confirmed_by`, `final_alt_policy`, `final_alt_experimental`, and `final_alt_is_primary`. No primary field is repurposed. New worker samples also refresh this export while the toggle is on.

Programmatic replay callers can explicitly pass `run_comparison(..., verification=True, alternate_policy=True)` to save both fields directly in that run's combined JSON/CSV. The keyword defaults to False. Branch images and time-window summaries remain primary. `yolo.py`, `mog2.py`, and `output.py` required no changes.

## MOG2 contribution from existing calibrated-bay logs

Input: [the existing strict-policy run](runs/areas/20260921T161408_115721Z/), not a new replay. The selected sets are CHAD Camera 1 B01/B02/B03 and overhead W01/W02/E01. Cameras 2–4 have no jointly calibrated bays and are excluded. Observations are repeated sampled bay/time pairs, not independent trials or unique capacity.

| Selected set | Observations | Definite agreement / overlap | MOG2 definite, Ref unresolved | Ref definite, MOG2 unresolved | Classic confirmations with no other recorded route |
|---|---:|---:|---:|---:|---:|
| CHAD B01–B03 | 117 | 89/89 (100%) | 7 (5.98%) | 18 (15.38%) | 89 |
| Overhead W01/W02/E01 | 30 | 12/12 (100%) | 3 (10.00%) | 4 (13.33%) | 12 |
| Combined | 147 | 101/101 (100%) | 10 (6.80%) | 22 (14.97%) | 101 |

One-branch percentages use all observations in that row; agreement uses only overlapping definite decisions. The 101 classic confirmations comprise 31 occupied and 70 vacant observations. They have no alternate confirmation **in recorded evidence** when the classic agreement route is removed. YOLO was skipped on these bays, so this cannot establish what an unrun detector would have returned. Allowing Reference alone is a separate policy change; the diagnostic does not prove MOG2 is necessary under every possible policy or supplies independent statistical evidence.

| Selected set | Primary occupied / vacant / unresolved | EXP occupied / vacant / unresolved | Primary → EXP coverage |
|---|---:|---:|---:|
| CHAD B01–B03 | 41 / 62 / 14 | 41 / 68 / 8 | 88.03% → 93.16% |
| Overhead W01/W02/E01 | 7 / 8 / 15 | 9 / 9 / 12 | 50.00% → 60.00% |
| Combined | 48 / 70 / 29 | 50 / 77 / 20 | 80.27% → 86.39% |

The nine additional definite results comprise seven vacant and two occupied observations. **CHAD/overhead have no independent labels beyond the calibration set; this measures agreement and coverage, not accuracy.** Their false-vacant rate is unmeasured, not zero. Accepting one branch increases reliance on its sensitivity to lighting, shadows and vehicle appearance. The alternate cannot repair uncalibrated bays.

## Frozen PKLot comparison

Only already-saved calibration/test predictions are re-derived. The selected aerial profile, thresholds, partitions, original predictions and freeze are unchanged. The policy was requested after the original test results were inspected, so this is a **post-hoc comparison**, not a newly preregistered held-out result.

On the 20,673 test observations, primary coverage is **25.26%**; experimental coverage is **29.17%**. Classified accuracy changes from **100.00%** to **98.14%**. The alternate produces **106 false-vacant and 6 false-occupied** observations, versus zero recorded errors in the primary's smaller classified subset. It changes **84 correct YOLO occupied confirmations to false-vacant**, resolves 232 uncertain observations as vacant and 576 as occupied. Of its 316 vacant predictions, 106 are wrong (**33.54%**); this denominator differs from the standard false-vacant rate.

Conditional false-vacant rate = false-vacant / (correct occupied + false-vacant). For the alternate it is **106 / 5,814 = 1.82%**; Reference alone was **106 / 3,914 = 2.71%**. The lower alternate percentage reflects extra occupied confirmations from YOLO in its fallback route, not fewer false-vacant errors. Both have **0.70%** false-vacant over all 15,118 occupied test labels. See [EXTERNAL_VALIDATION.md](EXTERNAL_VALIDATION.md#post-hoc-experimental-reference-priority-comparison) for calibration and test tables and confusion counts.

## Reproduce without inference

```powershell
.\.venv\Scripts\python.exe checks/diagnose_mog2_contribution.py
.\.venv\Scripts\python.exe checks/compare_reference_priority.py
.\.venv\Scripts\python.exe checks/check_reference_priority_results.py
```

Results: [MOG2 diagnostic](runs/verification/reference-priority/mog2-contribution.json), [selected replay comparison](runs/verification/reference-priority/calibrated-bay-comparison.csv), [PKLot metrics](runs/verification/reference-priority/pklot-reference-priority.json), [PKLot per-observation comparison](runs/verification/reference-priority/pklot-observations.csv), and [delivery audit](runs/verification/reference-priority/delivery-check.json).

The old freeze fingerprints whole source files, including `comparison.py`. Its new additive export/provenance support necessarily changes that file's hash. Original matching sources were copied to [frozen-source](runs/verification/reference-priority/frozen-source/) **before editing**. The new comparison checks those archived hashes, the unchanged frozen artifacts, exact frame/truth sets and original primary metrics. The existing strict `evaluate_pklot.py`/`check_pklot_results.py` checks will reject the changed current source tree; they were intentionally not weakened or used to reopen the experiment. Use the saved report or the commands above for this historical comparison. No frozen hash was updated.

For the supplied questions, reasoning and verification corrections, see [AI_CONSULTATION_LOG.md](AI_CONSULTATION_LOG.md). Implementation and test details are in [WORK_LOG.md](WORK_LOG.md).
