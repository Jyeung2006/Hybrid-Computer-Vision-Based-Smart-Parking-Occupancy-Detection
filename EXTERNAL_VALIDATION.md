# External validation: PKLot UFPR04

**22 September comparison update:** the original frozen results below are retained. The current source tree adds an opt-in alternate policy, so the old strict frozen-run commands reject its changed whole-file hash. For the saved-data comparison, run `checks/compare_reference_priority.py`; see the [post-hoc section](#post-hoc-experimental-reference-priority-comparison) and [consultation verification notes](AI_CONSULTATION_LOG.md#verification-notes-added-22-september-2026).

Measured 22 September 2026. This is a separate, reproducible validation of the existing production Reference, MOG2 and selective YOLOv8s branches.

**Scope:** outdoor UFPR04 only. These results do not establish, change or improve CHAD/overhead accuracy, their missing calibration, or performance on any indoor/live camera. This experiment can reveal failures; adequate example counts do not guarantee separable scores.

**Measured outcome:** the selected `aerial` pipeline achieved **100.0000% accuracy on classified decisions**, at **25.2600% coverage**. Fitting calibrated **19/28 Reference** bays and **0/28 MOG2** bays. Final confirmed **0 vacant observations**. These results do not demonstrate a generally accurate, complete parking-occupancy system.

## Run it

From the project folder in the VS Code PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe checks/evaluate_pklot.py
```

The delivered test is already complete: this command checks the frozen experiment and displays its saved measurements rather than fitting or testing it again. It does not open or change the parking interface. Normal `main.py` behavior is unchanged.

On a fresh checkout, the same command downloads the 4.90 GB archive, verifies it, extracts UFPR04, prepares the day split, fits thresholds, compares profiles on calibration data, freezes settings and evaluates both profiles on the test days. No API key, GPU or new dependency is required; use the existing Python environment. Allow about 7 GB of disk space for the archive, extracted data and results.

Optional staged commands on an **unopened experiment**:

```powershell
.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase prepare
.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase fit
.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase calibrate
.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase test
```

Once `test-started.json` exists, fitting/calibration are locked. Implementation, runtime, references, thresholds, model manifest and partition hashes must match the freeze. Completed test days are reused from checkpoints. A process interrupted inside a day may repeat that unfinished day under the identical freeze; it cannot retune parameters. Do not delete the lock and reuse these test days for model selection.

## Verified production interfaces and proposal scope

Before changes, read the current `catalog.py`, `areas.py`, `view_presets.py`, `comparison.py`, `yolo.py`, `mog2.py`, `mog2_calibration.py`, `monitor.py`, `evaluation.py` and `output.py`. Also checked the proposal sections 3.7–3.8, configuration, vision, source and registration code.

- `prepare_preset`, `prepare_mog2` and `run_comparison` expect video files/frame indexes, not XML snapshot sequences. The closest equivalent is `SnapshotRecording`: it supplies chronological real `Frame` objects to the unchanged `Analyzer.analyze`, `MOG2Branch.analyze`, `YOLOBranch.analyze` and `yolo.final_decision` algorithms. It uses the existing classic `consensus` function as an OpenCV-only baseline.
- Recipes/configurations use string `id` values, integer-coordinate `polygon` entries and individual `reference_image` files. Reference calibration carries setup/reference/polygon/preprocessing hashes. MOG2 calibration carries a model signature. The new converter and fitter produce these existing formats.
- Existing evaluation supported multiple labelled slots but computed single-branch metrics inline. `ClassificationMetrics` is now shared by both evaluators; `reference_boundaries` shares the existing percentile fitting and metadata. No duplicate Reference or MOG2 classifier was introduced.
- The proposal also describes probability fusion, fine-tuning, a full-frame YOLO-only comparator, temporal confirmation, Brier score, deployment and operational experiments. This scoped addition measures the currently implemented selective pipeline. Its YOLO rows are **selective verification**, not a YOLO-only whole-dataset classifier; appearance scores are not occupancy probabilities. Those broader proposal stages remain separate.

## Dataset, license and integrity

Dataset: [PKLot](https://web.inf.ufpr.br/vri/databases/parking-lot-database/), Almeida et al., *Expert Systems with Applications* 42(11):4937–4949 (2015), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [local attribution](third_party/PKLOT-LICENSE.md). UFPR04 and UFPR05 are two views of one UFPR car park; PUCPR is another car park. Only UFPR04 is used here.

The university domain did not resolve locally. The [pinned original-archive mirror](https://huggingface.co/datasets/teenygrad/pklot/tree/9604b05ad6dfd5ab5817b5fa6600d375754562fb) supplied the original JPEG/XML archive. This is not a resized/reshuffled Roboflow export.

- Archive size: **4,898,276,304 bytes**; SHA-256 `e89bbc1dc735298c478688d50c7a682fb3b0076a87b6634923132709f2d2fa9b`.
- The downloaded bytes matched the mirror’s published Git LFS hash. No independent university-side checksum was available. Source revision is pinned in code; extracted member hashes are recorded and checked.
- Extracted **3,791 original 1280×720 images and 3,791 XML files**, with 28 stable slot IDs. The parser accepts original `<point>` and `<Point>` spelling. Unknown/missing occupancy annotations are excluded from binary ground truth, not silently labelled vacant.
- Labelled slot observations: **105,845**; unlabelled slot/frame pairs: **303**.
- Frames retain their filename capture timestamp with an unspecified dataset timezone. Historical capture time is separate from local decode/processing time, so old dataset dates do not trigger the live stale-frame guard.

## Fixed day split

Random seed **20260922**, sorted unique dates shuffled with Python `random.Random`, largest-remainder 60/20/20 allocation. Weather folders do not define sessions: the same date always remains in one partition. No image sampling was used. Byte-content duplication is rejected during partitioning; decoded-content overlap/duplication is rejected during analysis.

| Partition | Days | Frames | Labelled bays | Occupied truth | Vacant truth | Unlabelled | Sunny / cloudy / rainy frames |
|---|---:|---:|---:|---:|---:|---:|---|
| fit | 18 | 2341 | 65355 | 24046 | 41309 | 193 | 1228 / 974 / 139 |
| calibrate | 6 | 709 | 19817 | 6971 | 12846 | 35 | 439 / 158 / 112 |
| test | 6 | 741 | 20673 | 15118 | 5555 | 75 | 431 / 276 / 34 |

**fit dates:** 2012-12-08, 2012-12-13, 2012-12-14, 2012-12-15, 2012-12-16, 2012-12-17, 2012-12-18, 2012-12-19, 2012-12-21, 2012-12-22, 2012-12-23, 2012-12-24, 2012-12-27, 2012-12-28, 2012-12-29, 2013-01-16, 2013-01-18, 2013-01-19.

**calibrate dates:** 2012-12-07, 2012-12-11, 2012-12-25, 2012-12-26, 2013-01-20, 2013-01-21.

**test dates:** 2012-12-12, 2012-12-20, 2013-01-15, 2013-01-17, 2013-01-22, 2013-01-29.

These are 60/20/20 percentages of days, not necessarily of frames. The class mix differs materially across partitions; this is reported rather than balanced using test labels. The authors’ original split protocol differs; this experiment uses the user-requested proposal split.

## Fitting data and geometry

All **28 / 28** references come from XML-labelled vacant fitting frames that passed the production alignment check. The first complete fitting frame supplies the fixed setup geometry. A reference may be shared across bays when all those bays are labelled empty; every frame used as any reference is excluded from threshold-fitting scores for every bay. Other images pass unchanged at original resolution.

The fitting set contains three distinct polygon/camera arrangements. Fitting-image inspection confirmed that the camera moved between periods. A fixed first-fit setup is deliberately retained: the production eight-pixel alignment guard rejects displaced views. No test geometry is used to move a polygon or create a new reference. Consequently this is a test of a fixed-configuration pipeline on the whole UFPR04 sequence, including its changed-view failure handling, not a claim that every dataset image has a calibrated camera configuration.

Reviewed fitting-only geometry examples:

![Initial fitting camera position](runs/verification/pklot-fit-geometry-0.png)

![Second fitting camera position](runs/verification/pklot-fit-geometry-1.png)

![Third fitting camera position](runs/verification/pklot-fit-geometry-2.png)

The existing fitter uses the 95th percentile of vacant scores and 5th percentile of occupied scores. At least five examples of each state are necessary, but overlapping distributions remain uncalibrated regardless of sample count. There is no threshold lowering or automatic empty override.

![Fitting score distributions for three representative bays](runs/verification/pklot-fit-score-distributions.png)

| Bay | Reference vacant / occupied | Reference status | MOG2 vacant / occupied | MOG2 status |
|---|---:|---|---:|---|
| UFPR04-P01 | 705 / 869 | uncalibrated: overlapping_score_distributions | 705 / 869 | uncalibrated: overlapping_score_distributions |
| UFPR04-P02 | 752 / 821 | uncalibrated: overlapping_score_distributions | 752 / 821 | uncalibrated: overlapping_score_distributions |
| UFPR04-P03 | 693 / 881 | uncalibrated: overlapping_score_distributions | 693 / 881 | uncalibrated: overlapping_score_distributions |
| UFPR04-P04 | 760 / 813 | calibrated | 760 / 813 | uncalibrated: overlapping_score_distributions |
| UFPR04-P05 | 784 / 790 | calibrated | 784 / 790 | uncalibrated: overlapping_score_distributions |
| UFPR04-P06 | 853 / 721 | calibrated | 853 / 721 | uncalibrated: overlapping_score_distributions |
| UFPR04-P07 | 811 / 759 | calibrated | 811 / 759 | uncalibrated: overlapping_score_distributions |
| UFPR04-P08 | 835 / 727 | uncalibrated: overlapping_score_distributions | 835 / 727 | uncalibrated: overlapping_score_distributions |
| UFPR04-P09 | 812 / 746 | calibrated | 812 / 746 | uncalibrated: overlapping_score_distributions |
| UFPR04-P10 | 697 / 839 | uncalibrated: overlapping_score_distributions | 697 / 839 | uncalibrated: overlapping_score_distributions |
| UFPR04-P11 | 842 / 728 | calibrated | 842 / 728 | uncalibrated: overlapping_score_distributions |
| UFPR04-P12 | 825 / 746 | calibrated | 825 / 746 | uncalibrated: overlapping_score_distributions |
| UFPR04-P13 | 859 / 688 | calibrated | 859 / 688 | uncalibrated: overlapping_score_distributions |
| UFPR04-P14 | 789 / 778 | calibrated | 789 / 778 | uncalibrated: overlapping_score_distributions |
| UFPR04-P15 | 840 / 719 | uncalibrated: overlapping_score_distributions | 840 / 719 | uncalibrated: overlapping_score_distributions |
| UFPR04-P16 | 849 / 723 | calibrated | 849 / 723 | uncalibrated: overlapping_score_distributions |
| UFPR04-P17 | 854 / 718 | calibrated | 854 / 718 | uncalibrated: overlapping_score_distributions |
| UFPR04-P18 | 842 / 731 | calibrated | 842 / 731 | uncalibrated: overlapping_score_distributions |
| UFPR04-P19 | 855 / 718 | calibrated | 855 / 718 | uncalibrated: overlapping_score_distributions |
| UFPR04-P20 | 978 / 592 | calibrated | 978 / 592 | uncalibrated: overlapping_score_distributions |
| UFPR04-P21 | 902 / 666 | calibrated | 902 / 666 | uncalibrated: overlapping_score_distributions |
| UFPR04-P22 | 800 / 770 | uncalibrated: overlapping_score_distributions | 800 / 770 | uncalibrated: overlapping_score_distributions |
| UFPR04-P23 | 828 / 745 | uncalibrated: overlapping_score_distributions | 828 / 745 | uncalibrated: overlapping_score_distributions |
| UFPR04-P24 | 824 / 749 | calibrated | 824 / 749 | uncalibrated: overlapping_score_distributions |
| UFPR04-P25 | 790 / 783 | calibrated | 790 / 783 | uncalibrated: overlapping_score_distributions |
| UFPR04-P26 | 789 / 786 | uncalibrated: overlapping_score_distributions | 789 / 786 | uncalibrated: overlapping_score_distributions |
| UFPR04-P27 | 828 / 747 | calibrated | 828 / 747 | uncalibrated: overlapping_score_distributions |
| UFPR04-P28 | 837 / 735 | calibrated | 837 / 735 | uncalibrated: overlapping_score_distributions |

Skipped fitting frames (scores excluded; invalid images never update MOG2): `{"background_alignment_failed": 231, "background_matches_too_concentrated": 46, "camera_view_changed": 484, "insufficient_background_matches": 4, "reference_source_frames": 1}`.

Exact percentile boundaries, reference frame identities, per-slot sample hashes and per-day MOG2 counts are in the JSON report and `data/pklot/experiment/fit.json`. All fitting scores are retained in `fit-scores.json`.

For scale comparison only, the original CHAD B01/B02/B03 MOG2 calibration used vacant/occupied counts **10/25, 21/11 and 26/6** (see [FINAL_RESULTS.md](FINAL_RESULTS.md) and its stored calibration). Those are different cameras/data and are not combined here. Example quantity alone cannot be compared as accuracy.

## Calibration and frozen profile selection

Both fixed **YOLOv8s (small)** profiles use OpenCV DNN, 640×640 full-frame input, a 0.80 qualifying vehicle score and the existing unique-bay overlap/anchor association. COCO uses the existing 0.82 vertical anchor; aerial uses 0.50. Weights, cutoffs, classic thresholds and final-decision policy are unchanged during calibration and testing.

Calibration chooses the profile with the largest fraction of all labelled observations decided correctly; ties prefer fewer false-vacant errors, then COCO. This penalizes abstention rather than rewarding 100% accuracy on very few decisions. No thresholds or neural weights are fitted using calibration/test labels.

**Selected before test: `aerial`.** This is the empirically better operating profile under these fixed settings, not an isolated proof that anchor geometry alone caused the difference.

| Profile | Calibration accuracy on classified % | Coverage % | Correct / all truth % | False vacant | False occupied |
|---|---:|---:|---:|---:|---:|
| coco | 100.0000 | 1.1505 | 1.1505 | 0 | 0 |
| aerial | 100.0000 | 12.4540 | 12.4540 | 0 | 0 |

Freeze SHA-256: `bd4aed4bcd178a52cc27712ff770ff8674bae1ff8252c3c5547cab81b2d3a112`. Both test profiles below were specified in advance; the primary profile is not reselected by test performance.

## Held-out test metrics

**Definitions:** occupied is positive. Accuracy, precision, recall and F1 below are computed on definite occupied/vacant predictions. Coverage is definite predictions divided by all labelled observations. The full 2×4 matrix retains uncertain and unknown predictions. “Correct / all” also penalizes abstentions. Undefined means the denominator is zero, not an unmeasured placeholder.

False-vacant (FV) = true occupied predicted vacant; false-occupied (FO) = true vacant predicted occupied. Rates labelled “all” use **all** occupied/vacant ground truth respectively; conditional rates use only the corresponding classified ground truth. A zero FV rate with low coverage is not proof of safe vacancy detection.

| Method | Accuracy % | Precision % | Recall % | F1 % | Coverage % | Correct / all % |
|---|---:|---:|---:|---:|---:|---:|
| reference | 97.2881 | 99.8427 | 97.2918 | 98.5507 | 19.9777 | 19.4360 |
| mog2 | undefined | undefined | undefined | undefined | 0.0000 | 0.0000 |
| opencv_consensus | undefined | undefined | undefined | undefined | 0.0000 | 0.0000 |
| yolo_coco | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.6772 | 0.6772 |
| yolo_aerial | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 25.2600 | 25.2600 |
| final_coco | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.6772 | 0.6772 |
| final_aerial | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 25.2600 | 25.2600 |

**Abstention-sensitive occupied detection:** conditional recall/F1 can be 100% when the system only confirms a few cars and never decides vacant. The following recall counts unresolved occupied observations as missed positives. Its F1 combines that recall with occupied precision; unresolved observations remain unknown/uncertain in the confusion matrix and are not relabelled vacant.

| Method | Occupied precision % | Occupied recall over all true occupied % | F1 including missed occupied observations % |
|---|---:|---:|---:|
| reference | 99.8427 | 25.1885 | 40.2282 |
| mog2 | undefined | 0.0000 | 0.0000 |
| opencv_consensus | undefined | 0.0000 | 0.0000 |
| yolo_coco | 100.0000 | 0.9260 | 1.8351 |
| yolo_aerial | 100.0000 | 34.5416 | 51.3471 |
| final_coco | 100.0000 | 0.9260 | 1.8351 |
| final_aerial | 100.0000 | 34.5416 | 51.3471 |

These additional values are saved in [pklot-abstention-metrics.json](runs/verification/pklot-abstention-metrics.json). The primary report retains the original conditional metrics and full confusion matrices.

| Method | TP | TN | FV | FO | FV/all occupied % | FO/all vacant % | Conditional FV % | Conditional FO % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| reference | 3808 | 210 | 106 | 6 | 0.7012 | 0.1080 | 2.7082 | 2.7778 |
| mog2 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | undefined | undefined |
| opencv_consensus | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | undefined | undefined |
| yolo_coco | 140 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | undefined |
| yolo_aerial | 5222 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | undefined |
| final_coco | 140 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | undefined |
| final_aerial | 5222 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | undefined |

The YOLO rows include all labelled bays; `not_requested_opencv_agreement` appears as unknown for that branch and is not a failed inference. Requested-only measurements are also reported in JSON:

| Selective verifier | Requested labelled observations | Classified | Accuracy % | Coverage within requests % |
|---|---:|---:|---:|---:|
| coco | 20673 | 140 | 100.0000 | 0.6772 |
| aerial | 20673 | 5222 | 100.0000 | 25.2600 |

### Full confusion matrices

| Method | Truth | Predicted occupied | Predicted vacant | Uncertain | Unknown |
|---|---|---:|---:|---:|---:|
| reference | occupied | 3808 | 106 | 262 | 10942 |
| reference | vacant | 6 | 210 | 19 | 5320 |
| mog2 | occupied | 0 | 0 | 6189 | 8929 |
| mog2 | vacant | 0 | 0 | 318 | 5237 |
| opencv_consensus | occupied | 0 | 0 | 6189 | 8929 |
| opencv_consensus | vacant | 0 | 0 | 318 | 5237 |
| yolo_coco | occupied | 140 | 0 | 6049 | 8929 |
| yolo_coco | vacant | 0 | 0 | 318 | 5237 |
| yolo_aerial | occupied | 5222 | 0 | 967 | 8929 |
| yolo_aerial | vacant | 0 | 0 | 318 | 5237 |
| final_coco | occupied | 140 | 0 | 6049 | 8929 |
| final_coco | vacant | 0 | 0 | 318 | 5237 |
| final_aerial | occupied | 5222 | 0 | 967 | 8929 |
| final_aerial | vacant | 0 | 0 | 318 | 5237 |

### Weather-stratified test metrics

| Method | Weather | N | Accuracy % | Precision % | Recall % | F1 % | Coverage % | FV / FO | FV/all occupied % | FO/all vacant % |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| reference | sunny | 12016 | 97.1690 | 99.8236 | 97.1674 | 98.4776 | 30.8672 | 99 / 6 | 1.0739 | 0.2145 |
| reference | cloudy | 7720 | 98.3373 | 100.0000 | 98.3294 | 99.1576 | 5.4534 | 7 / 0 | 0.1215 | 0.0000 |
| reference | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| mog2 | sunny | 12016 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| mog2 | cloudy | 7720 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| mog2 | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| opencv_consensus | sunny | 12016 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| opencv_consensus | cloudy | 7720 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| opencv_consensus | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| yolo_coco | sunny | 12016 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.9571 | 0 / 0 | 0.0000 | 0.0000 |
| yolo_coco | cloudy | 7720 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.3238 | 0 / 0 | 0.0000 | 0.0000 |
| yolo_coco | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| yolo_aerial | sunny | 12016 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 38.4820 | 0 / 0 | 0.0000 | 0.0000 |
| yolo_aerial | cloudy | 7720 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 7.7461 | 0 / 0 | 0.0000 | 0.0000 |
| yolo_aerial | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| final_coco | sunny | 12016 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.9571 | 0 / 0 | 0.0000 | 0.0000 |
| final_coco | cloudy | 7720 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.3238 | 0 / 0 | 0.0000 | 0.0000 |
| final_coco | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |
| final_aerial | sunny | 12016 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 38.4820 | 0 / 0 | 0.0000 | 0.0000 |
| final_aerial | cloudy | 7720 | 100.0000 | 100.0000 | 100.0000 | 100.0000 | 7.7461 | 0 / 0 | 0.0000 | 0.0000 |
| final_aerial | rainy | 937 | undefined | undefined | undefined | undefined | 0.0000 | 0 / 0 | 0.0000 | 0.0000 |

The JSON contains each weather stratum’s complete confusion matrix and conditional/unconditional error rates. Rainy test coverage is based on only 34 snapshots; do not infer broad weather robustness from this small subset. Adjacent observations remain correlated within days.

## Alignment, abstentions and MOG2 cadence

| Partition | Frames | Alignment failures | MOG2 updates | MOG2 gap resets |
|---|---:|---|---:|---:|
| calibrate | 709 | `{"background_alignment_failed": 209, "background_matches_too_concentrated": 28, "camera_view_changed": 103, "insufficient_background_matches": 1}` | 368 | 2 |
| test | 741 | `{"background_alignment_failed": 214, "background_matches_too_concentrated": 100, "camera_view_changed": 188, "insufficient_background_matches": 6}` | 233 | 0 |

Selected final profile `aerial`, stratified by the **unchanged** alignment guard:

| Alignment | Labelled observations | Accuracy % | Coverage % | Correct / all % |
|---|---:|---:|---:|---:|
| alignment_accepted | 6507 | 100.0000 | 80.2520 | 80.2520 |
| alignment_rejected | 14166 | undefined | 0.0000 | 0.0000 |

- Reference score distributions can overlap because of lighting, reflections, shadows and different vehicle appearances. An occupied score below the empty distribution cannot be repaired merely by collecting more copies of the same states.
- Reference calibration is unknown when invalid/overlapping; MOG2 is uncertain when uncalibrated. YOLO is requested for any unresolved or conflicting pair, but frame alignment failure prevents inference. A qualifying vehicle can confirm occupied. No detection remains uncertain and cannot establish vacancy. Definite classic agreement is retained exactly.
- `MOG2Branch(..., expected_sample_interval=300)` resets after a gap **greater than 1,500 seconds** (five expected intervals). Omitting this new keyword preserves the previous 15-second video limit and existing calibration signatures, including other replay sampling intervals. CHAD/overhead settings/assets are unchanged.
- Every dataset day starts a fresh model seeded from **fitting-only** empty reference patches. Updates follow the chronological snapshots, including unlabelled bays, at the existing 0.001 per-observation learning rate. The model adapts unsupervised during a held-out day; labels never enter its updates. No model state crosses days or partitions.
- Five minutes of unseen movement occur between snapshots. At this cadence, 500 samples span roughly 41.7 hours rather than 25 minutes at three seconds. MOG2 does not store a literal 500-image buffer: the explicit 0.001 learning rate controls adaptation and is not rescaled to wall time. Do not present this as continuous-video motion performance. Two observations after a gap reset retain the existing restabilizing behavior.
- The legacy 15-second limit would reset at ordinary 300-second intervals. Regression tests verify zero such resets at 300-second spacing and a reset only beyond the new limit; actual counts above also include real larger gaps and gaps caused by unusable images. This is a cadence behavior check, not a measured continuous-video accuracy comparison.

## Processing latency

Milliseconds on this Windows computer with the existing Python/OpenCV environment, CPU DNN and two OpenCV threads. Per-profile pipeline sums include image decoding/checksum, Reference, MOG2 and that selective verifier. Both profiles were executed sequentially for this experiment; this is not a dedicated production throughput benchmark. File reporting and UI rendering are excluded. Failures/skipped inference can make unconditional latency look faster.

| Stage | Samples | Median ms | P95 ms | Maximum ms |
|---|---:|---:|---:|---:|
| decode | 741 | 8.5632 | 10.7759 | 102.3501 |
| reference | 741 | 52.5423 | 73.9460 | 140.4696 |
| mog2 | 233 | 31.9082 | 43.9000 | 54.9403 |
| yolo_coco | 741 | 0.1266 | 592.2760 | 1155.6231 |
| pipeline_coco | 741 | 62.0721 | 709.0466 | 1329.1166 |
| yolo_aerial | 741 | 0.1198 | 584.0328 | 1127.8765 |
| pipeline_aerial | 741 | 62.0672 | 712.9336 | 1301.3700 |
| both_profiles_wall | 741 | 65.0641 | 1305.2398 | 2461.3150 |

Test YOLO error/skip reasons: `{"aerial:background_alignment_failed": 214, "aerial:background_matches_too_concentrated": 100, "aerial:camera_view_changed": 188, "aerial:insufficient_background_matches": 6, "coco:background_alignment_failed": 214, "coco:background_matches_too_concentrated": 100, "coco:camera_view_changed": 188, "coco:insufficient_background_matches": 6}`. Alignment-rejection reasons are propagated by the verifier and mean inference was blocked by the source/view guard, not that ONNX inference crashed.

## Artifacts and reproducibility

- [`checks/evaluate_pklot.py`](checks/evaluate_pklot.py): staged/runnable check, independent of the app.
- [`runs/verification/pklot-evaluation.json`](runs/verification/pklot-evaluation.json): complete measured report, exact unrounded metrics and per-bay counts.
- [`data/pklot/partitions.json`](data/pklot/partitions.json): immutable split, original image/XML hashes, truth labels and original polygons. Individual phase manifests are under `data/pklot/manifests/`.
- [`data/pklot/experiment/`](data/pklot/experiment/): derived recipe, setup, reference copies, config, fit scores and MOG2 calibration. No examples are added to existing cameras.
- [`runs/verification/pklot/frozen.json`](runs/verification/pklot/frozen.json): exact selected profile, code/runtime/model/artifact fingerprints and calibration measurements.
- [`runs/verification/pklot/test-started.json`](runs/verification/pklot/test-started.json): test-opening receipt. `calibrate/` and `test/` retain per-day, per-frame, per-bay predictions, branch reasons, scores and timing.
- [`checks/render_pklot_report.py`](checks/render_pklot_report.py): regenerate this document from saved measurements without inference.
- [`checks/plot_pklot_fit.py`](checks/plot_pklot_fit.py): regenerate the fitting-only geometry views and score histograms. This optional plotting command needs Matplotlib (already installed here); evaluation itself needs only the existing core dependencies.
- [`checks/check_pklot_results.py`](checks/check_pklot_results.py): independently audit saved label identities, decision routing, confusion counts, ratios, freeze and protected files without inference.
- [`tests/test_pklot.py`](tests/test_pklot.py): XML formats, day leakage, metric denominators, gap behavior/signature compatibility, snapshot chronology, profile selection, test locks and real-branch adapter/checkpoint integration.

Verification: **254 tests passed in 64.16 seconds**; [test report](runs/verification/pklot-tests-final.xml). The [saved-result audit](runs/verification/pklot-delivery-check.json) checks all calibration/test observations against original labels, branch routing, matrix arithmetic, disjoint dates/content and the freeze. It confirms **636 protected existing files unchanged**. [Legacy signature checks](runs/verification/pklot-legacy-signatures.json) also confirm existing current-camera MOG2 calibration signatures still match. The application UI was not relaunched for this checks-only addition.

Model manifest: [`assets/models/yolov8s-manifest.json`](assets/models/yolov8s-manifest.json). No fine-tuning occurred. The existing COCO/VisDrone pretrained weights are used as supplied; this experiment does not audit their complete upstream training provenance.

### Local archive and disk space

`data/pklot/PKLot.tar.gz` is the pinned original PKLot dataset download used to prepare this independent validation experiment. It is **4,898,276,304 bytes (about 4.56 GiB)**. The project extracted only UFPR04's **3,791 full-resolution JPEG images and 3,791 XML annotations** into `data/pklot/UFPR04/`; the archive also contains data outside the subset used in the experiment. The extracted files and other local PKLot metadata currently occupy about **1.25 GB** separately from the archive.

Normal CHAD/overhead camera operation, opening saved validation reports, and checks that read the already-extracted UFPR04 files do not read the tarball. The acquisition code first checks `data/pklot/extraction.json` and verifies the extracted member hashes; with that receipt and files intact, it does not reopen or download the archive. Therefore, after confirming the extracted files are retained, the tarball can be removed to recover about 4.56 GiB **without affecting normal parking operation or the saved results**. Keep it if an offline, byte-for-byte copy of the original source is needed. If the extraction receipt or source files are lost, rebuilding from scratch will require the same pinned archive again (or a new download). Do not remove `UFPR04/`, `extraction.json`, `partitions.json`, or `experiment/` when only reclaiming archive space.

## Interpretation and next work

Use the measured classified accuracy **together with coverage and error counts**. Low coverage or poor metrics are an experimental finding, not grounds to retune against these test dates. Large per-bay calibration counts do not prove that simple single-reference difference and MOG2 features separate occupancy under changing illumination or camera geometry.

A later, separately designed experiment could fit camera-position-specific configurations or guarded registration using development data, and compare a parking-specific occupied/vacant classifier. That would need new untouched test data or an explicitly new validation protocol; it must not be reported as an improvement on this already-used holdout. This deliverable preserves the current algorithm and records its limits.

No live camera, indoor accuracy, current parking availability, deployment, or CHAD/overhead accuracy improvement is claimed. No hardware installation, web service, database or Flutter work was performed.


<!-- REFERENCE_PRIORITY_POSTHOC -->
## Post-hoc experimental Reference priority comparison

Added 22 September 2026. **Opt-in comparison; primary Final is unchanged and remains the GUI default.** This policy was specified after inspecting the original test report. It is a post-hoc re-derivation of saved predictions, not a new preregistered held-out experiment. No inference, fitting, profile selection or freeze update was performed. The pre-test selected `aerial` profile is retained.

A valid calibrated Reference occupied **or vacant** decision takes priority; otherwise the existing Final rule applies. Confirmation is `reference_only_experimental`. Missing YOLO detection never establishes vacancy. This policy can override a YOLO occupied confirmation; the errors below include those conflicts.

| Partition / policy | Labelled observations | Classified | Coverage % | Classified accuracy % | Correct vacant | False-vacant | False-occupied | Conditional false-vacant % | False-vacant / all occupied % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| calibrate / Primary Final | 19,817 | 2,468 | 12.4540 | 100.0000 | 0 | 0 | 0 | 0.0000 | 0.0000 |
| calibrate / EXP: Reference priority | 19,817 | 7,643 | 38.5679 | 94.0076 | 4,620 | 155 | 303 | 5.6985 | 2.2235 |
| test / Primary Final | 20,673 | 5,222 | 25.2600 | 100.0000 | 0 | 0 | 0 | 0.0000 | 0.0000 |
| test / EXP: Reference priority | 20,673 | 6,030 | 29.1685 | 98.1426 | 210 | 106 | 6 | 1.8232 | 0.7012 |

Conditional false-vacant = FN / (TP + FN), with occupied as positive. For Reference alone the original value is 106 / 3,914 = **2.7082%**. The alternate keeps those 106 errors but gains additional occupied confirmations through fallback, giving 106 / 5,814 = **1.8232%**. Both yield **0.7012%** over all 15,118 occupied test labels. A lower conditional percentage here does not mean fewer false-vacant errors.

On test, the alternate changes **84 correct primary YOLO occupied confirmations into false-vacant**, resolves 232 uncertain observations to vacant and 576 to occupied. Of its 316 predicted-vacant observations, 210 are correct and 106 wrong (**33.54% of its vacancy predictions are wrong**). On calibration, 152 YOLO occupied confirmations are overridden to vacant, with 155 total false-vacant and 303 false-occupied results. The calibration/test contrast is reported without retuning.

Full alternate test matrix:

| Truth / predicted | Occupied | Vacant | Uncertain | Unknown |
|---|---:|---:|---:|---:|
| occupied | 5,708 | 106 | 375 | 8,929 |
| vacant | 6 | 210 | 102 | 5,237 |

The [MOG2 diagnostic](runs/verification/reference-priority/mog2-contribution.json) used only existing logs for the six jointly calibrated CHAD/overhead bays. It found 101/101 agreement among overlapping definite decisions, 10/147 MOG2-only definite observations (6.80%), and 22/147 Reference-only definite (14.97%). The 101 primary classic confirmations have no other confirming route in recorded evidence; YOLO was skipped, so hypothetical unrun YOLO outcomes are unknown. This is an agreement/coverage diagnostic, not accuracy or proof of causal necessity.

On those selected bays, CHAD coverage changes 88.03% → 93.16% and overhead 50.00% → 60.00%, with seven more vacant and two more occupied observations in total. **CHAD/overhead have no independent labels beyond the calibration set; accuracy and false-vacant rate remain unmeasured.**

Run `.\.venv\Scripts\python.exe checks/compare_reference_priority.py` to reproduce this opt-in table data without inference. Combined primary/alternate observations are in [JSONL](runs/verification/reference-priority/pklot-observations.jsonl) and [CSV](runs/verification/reference-priority/pklot-observations.csv); full metrics and input hashes are in [pklot-reference-priority.json](runs/verification/reference-priority/pklot-reference-priority.json). The [independent audit](runs/verification/reference-priority/delivery-check.json) checked all 40,490 selected-profile calibration/test observations and 927 protected files.

**Frozen-source compatibility:** adding provenance/optional exports changed `comparison.py`, which the old freeze fingerprints as a whole file. The original matching code was archived [before editing](runs/verification/reference-priority/frozen-source/); the freeze and original predictions are unchanged. The original strict `evaluate_pklot.py` and `check_pklot_results.py` commands reject the modified current tree. Use this new post-hoc command or the saved report for historical results; do not replace frozen hashes or remove the test lock.

GUI instructions and exact export semantics: [REFERENCE_PRIORITY.md](REFERENCE_PRIORITY.md). Questions, preserved consultation reasoning, completed status and factual corrections: [AI_CONSULTATION_LOG.md](AI_CONSULTATION_LOG.md). Implementation/testing record: [WORK_LOG.md](WORK_LOG.md).
