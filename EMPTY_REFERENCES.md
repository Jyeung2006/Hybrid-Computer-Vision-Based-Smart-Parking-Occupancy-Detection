# Reviewed empty examples (retained calibration material)

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.

Originally implemented **21 September 2026** after the user asked to find suitable empty examples and help the system recognize vacant bays.

## What was found

The existing recordings contain usable examples from the **same physical bay and camera view**. No unrelated stock photograph, generated background or detector prediction was used as an empty label. Reference images were extracted from the already downloaded source videos; no manual download, API key or new installation is needed.

There is reviewed empty evidence for **30 bay/view entries**: 15 overhead, 8 CHAD Camera 1, 3 Camera 2, 2 Camera 3 and 2 Camera 4. A bay that stays occupied in all supplied footage still has no verified empty reference. Cross-view images are not interchangeable; the counts are reference coverage, not a combined car-park capacity.

| Source | Bays with empty examples |
| --- | --- |
| Overhead | WL07, ML03, ML11, MR05, MR08, MR10, EL07, EL09, EL11, ER02, ER09, ER10, W01, W02, E01 |
| CHAD Camera 1 | B01–B08; B09's SUV never provides an empty reference |
| CHAD Camera 2 | F02, F03, F04 |
| CHAD Camera 3 | F02, F03 |
| CHAD Camera 4 | N10, N11 |

These are assistant-reviewed examples for an experimental demonstration. They are not an independent human-labelled accuracy dataset.

## Inspect the saved examples

The actual masked bay crops, their full-frame paths, pixel hashes and fitted limits are saved under `assets/empty-review/`. [manifest.json](assets/empty-review/manifest.json) connects each crop to the exact original reference frame and polygon. Adjacent pixels outside a bay polygon are neutralized in the review crop; analysis still uses the unchanged full frame and polygon mask.

- [Overhead empty reference gallery](assets/empty-review/overhead-empty-gallery.jpg)
- [CHAD Camera 1 gallery](assets/empty-review/chad-empty-gallery.jpg)
- [Camera 2 gallery](assets/empty-review/chad-camera-2-empty-gallery.jpg)
- [Camera 3 gallery](assets/empty-review/chad-camera-3-empty-gallery.jpg)
- [Camera 4 gallery](assets/empty-review/chad-camera-4-empty-gallery.jpg)

Contact sheets preserve the visual selection process: [overhead group 1](assets/empty-review/overhead-candidates-1.jpg), [group 2](assets/empty-review/overhead-candidates-2.jpg), [group 3](assets/empty-review/overhead-candidates-3.jpg), [EL09 late clear examples](assets/empty-review/overhead-EL09-late.jpg), and [CHAD late examples](assets/empty-review/chad-late-candidates.jpg).

## Exact selections and rejected examples

Overhead recipe version 4 adds twelve bays to the three that already had references:

- WL07, ML03, ML11, MR05, MR08, MR10, EL07, EL11, ER02, ER09 and ER10: reference at **0 seconds**, separate reviewed vacant examples at **5, 10, 15, 20 and 26 seconds**.
- EL09: reference at **27 seconds**, separate clear examples at **24, 24.5, 25.5, 26 and 26.5 seconds**. Earlier crops contain passing objects/shadows, so they were not used as added clean references.
- W01 retains its 12-second reference and gains a **27-second** empty image in its reference bank. W02 and E01 retain their verified reference/calibration sets detailed in [OVERHEAD_MAPPING.md](OVERHEAD_MAPPING.md).

All frames use the existing guarded registration into the setup view. Empty examples do not bypass resolution/alignment checks. The twelve vacant-only bays do **not** become fully two-state calibrated: the original minimum of five vacant and five occupied examples still applies to Reference/MOG2. The empty-image fallback is separate evidence.

CHAD Camera 1 recipe versions 5–6 add a clear late empty image at **recording 3, 18 seconds** for B05–B08, extending the previously reviewed lighting examples. B05–B07 also include the reviewed clear 15-second frame to cover their intermediate lighting appearance. B04 at 15/18 seconds and B08 in recording 4 at 27 seconds contain people; these were **not** added as clean references. Existing Camera 2–4 empty examples were reused and their views inspected. Original references and historical generated presets remain on disk.

The demonstrations use reference images selected from the same recordings being replayed, including later moments. This is offline setup followed by recorded review, not proof that an unattended live system could learn these references from future frames.

## Retired 21 September decision process - historical only

1. Matching definite Reference/MOG2 states remain unchanged. An unresolved or conflicting pair still requests YOLO, as the user specified.
2. A qualifying YOLO vehicle gives occupied. The vehicle threshold remains **0.80**.
3. After successful YOLO verification, an unresolved bay can become an **empty candidate** only when its pixels match a verified empty reference, no weak/ambiguous vehicle overlap touches the bay, neither classic branch says occupied, and the source is valid and visible.
4. **Three consecutive supporting observations** at the three-second sample interval confirm vacant. Checks at 0, 3 and 6 seconds can confirm at 6 seconds. This is not a nine-second delay.
5. New conflicting evidence, failed/stale input, a large time gap, backward time or a repeated frame resets the candidate streak. A previously confirmed fallback vacancy is not carried through missing or contradictory evidence. Each recording has its own tracker. Matching definite classic vacancy can support the streak while keeping its original result.

An empty match alone, a missed detection alone or elapsed time alone cannot establish vacancy. A source/model failure does not allow the empty fallback. Original YOLO cells remain uncertain when there is no qualifying vehicle; **Final estimate** can then say vacant because of the additional positive empty-image evidence. Selecting the bay shows its empty difference, threshold and confirmation count.

## Empty-match threshold and provenance

The matcher uses the same Gaussian-smoothed grayscale normalized absolute difference as the reference branch, taking the best match in the manually reviewed reference bank. Each bank needs a verified reference plus at least five distinct, aligned vacant examples separate from its own reference images. Duplicate/reference examples are excluded. Its experimental tolerance is:

`min(0.04, max(0.012, percentile95(empty_scores) * 1.5 + 0.005))`

This restores the earlier conservative empty-appearance heuristic; it is not a learned probability or full two-state calibration. If supplied occupied examples fall inside that tolerance, the empty fallback is disabled for that bay. Setup/reference/polygon hashes and preprocessing version must match. Additional bank images are accepted only with recorded pixel hashes. References are not automatically replaced or learned from predicted vacancy.

## Historical testing and remaining limits

The new tests cover missing/tampered references, a parked car missed by the detector, low-score vehicle overlap, opposing classic occupancy, failed verification, stale frames, three-sample confirmation, independent trackers, duplicate frames, gaps and backward time. The actual replay checks every new vacant decision for successful verification, a valid match, no conflicting vehicle/occupied evidence and a three-sample streak. Detailed measured results are in [FINAL_RESULTS.md](FINAL_RESULTS.md) and [VALIDATION.md](VALIDATION.md).

Short recordings can end before confirmation: Camera 4 contains samples at 0 and 3 seconds only. EL09 clears late and may also have only two clean supporting samples before the overhead clip ends. People crossing bays and changing appearance can correctly interrupt a streak. Six overhead occupied bays still have detector scores below 0.80; this task does not lower that cutoff or fabricate empty examples for them.

A confirmed three-check demo vacancy is not the proposal's full persistent state/transaction stage. There is no database, automatic cross-camera identity discovery or live availability claim. Independent accuracy and false-vacant/false-occupied rates still require a separate labelled evaluation set.

## Run and reproduce

Current normal use: restart `main.py` and read Final with its displayed-method confirmation. The fallback described above is retired. Original crops and the historical manifest are preserved; the exporter uses that historical reference-review run. Existing three-second samples, ten-second summaries, area totals and video navigation remain.

```powershell
.\.venv\Scripts\python.exe checks/check_decisions.py
.\.venv\Scripts\python.exe checks/export_empty_examples.py
.\.venv\Scripts\python.exe -m pytest -q
```

The current replay creates a fresh results directory and [decision-check.json](runs/verification/decision-check.json). The exporter retains [empty-replay-check.json](runs/verification/empty-replay-check.json) as its historical reviewed-reference source. Historical implementation: [empty_evidence.py](src/parking_probe/empty_evidence.py), [view_presets.py](src/parking_probe/view_presets.py), and [comparison.py](src/parking_probe/comparison.py). Every change and measurement is recorded in [WORK_LOG.md](WORK_LOG.md).
