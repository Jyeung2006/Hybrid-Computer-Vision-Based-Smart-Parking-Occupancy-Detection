# Review or edit a bay

**Historical guide:** its B08 alignment-exclusion and overlap-diagnostic instructions describe the 24 September experiment, which was rolled back. For normal Run behavior, see [OPENCV_FIRST.md](OPENCV_FIRST.md).

Normal Run remains **guarded vacancy (YOLO-assisted)**. The overlap experiment is disabled for normal decisions. “70% outside vehicle boxes” does not mean 70% confidence that a bay is empty.

1. Find the camera, local slot and physical ID in [the 90-bay audit](BAY_BOUNDARY_PER_BAY.md). `B08` in Camera 1 is `CHAD-P008`; `F02` is view-local in Camera 2. Do not transfer polygons between camera views or combine recording periods.
2. Open the linked contact sheet, then the native `*-raw.png`, `*-before.png` and `*-after.png` images in `runs/verification/bay-boundary-audit/<camera>/`. CHAD uses 1280×720; overhead uses registered 1100×720. Compare setup and start/middle/end frames; inspect moving cars, people and shadows separately. An occupied vehicle silhouette is not the painted footprint.
3. Read that bay's `issue`, `excluded_own_bay`, `marking_obscured` and seven non-bay categories in `per-bay-review.csv`. “Not observed” is not proof when markings are hidden. Read `production-per-bay.csv` for actual blocker counts by recording. `replay-final/<source>/observations.csv` and `history.jsonl` retain each sample's scores and reasons.
4. To practise drawing, use the existing [drawing guide](BAY_DRAWING_GUIDE.md) with a separate practice config. Back up the preset before integration. Normal Run reads `presets/*.json`, not the practice config. Preserve `id`, `bay_id` and site inventory. Trace the visible footprint with a modest margin; retain enough asphalt for a small or offset vehicle. A curved edge can use more than four ordered vertices.
5. A polygon change requires re-review of **every affected reference and calibration example**, with the new outline. Retain only labels supported by visible pixels; never manufacture the missing state. Updating the preset creates a new cache. Verify that the Reference polygon signature, empty-match signature and MOG2 model signature changed. Full two-state calibration still needs both states. B08 currently has 20 vacant and zero occupied examples, so it remains incompletely calibrated.
6. `alignment_exclusion_polygon`, where present, excludes a broader region from background alignment feature matching. It is **not** the displayed bay or the occupancy-scoring mask. B08 retains the old exclusion over the adjacent curb to preserve the established alignment checks. Do not relax alignment limits to force acceptance of another recording.
7. The old overlap scripts were retired with the rollback. Replay the current OpenCV-first policy to a fresh dated directory and compare all four state counts:

   ```powershell
   .\.venv\Scripts\python.exe checks/check_opencv_first.py
   .\.venv\Scripts\python.exe checks/check_opencv_first_interface.py
   .\.venv\Scripts\python.exe -m pytest -q
   ```

The saved overlap fields report actual intersection/bay area, both anchor estimates, neighbouring overlaps, candidate ownership and blockers. These are geometry diagnostics. A weak box, uncertain owner, large spill, missing/failed inference, invalid frame, classic occupied evidence, unusable/mismatching reference, or interrupted three-sample streak prevents the corresponding guarded vacancy. No-reference vacancy, when allowed by the existing guard, is explicitly **provisional, based on repeated no detection**.

In the interface, inspect the separate Reference/MOG2/YOLO/Final columns. Seeking or replaying resets the displayed three-sample guard; saved ten-second summaries remain analysis history. Camera 4's original 4.97-second clip supplies only 0s and 3s and cannot finish a streak. The additional 13.27-second clip is separate and currently rejected for alignment; it supplies no extra observations to the original streak.
