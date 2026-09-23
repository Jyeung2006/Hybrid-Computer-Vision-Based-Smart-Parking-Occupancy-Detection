# AI Consultation Log

22 September 2026. This file preserves the **user-supplied synthesized consultation** below. Its reasoning text is retained verbatim; only the requested results/status placeholders are completed. Historical phrases such as “implementation in progress” in the supplied narrative describe the discussion before completion. They do not describe the delivered status above Q1 and under Q5.

**Verification warning:** several supplied claims do not match the repository. In particular, uncalibrated bays can still be confirmed occupied by YOLO; Reference did predict vacant on PKLot; and the occupied example range was 592–881. These statements remain in the supplied text as requested. Read the [verification notes](#verification-notes-added-22-september-2026) before citing them. The new alternate prioritizes both occupied and vacant Reference decisions.

Implementation: [WORK_LOG.md](WORK_LOG.md). Measured results: [EXTERNAL_VALIDATION.md](EXTERNAL_VALIDATION.md) and [REFERENCE_PRIORITY.md](REFERENCE_PRIORITY.md). The supplied questions are the user's recollection of an AI-assisted consultation; this file does not claim to reproduce an independently retrieved conversation transcript.


## Current state (read this first)
- CHAD/overhead: only 3/9 Camera-1 bays and 3/69 overhead bays are fully
  two-state calibrated. The remaining bays are structurally unable to reach a
  definite Final state under the current AND-gate rule. This is expected
  behavior, not a bug (Q1).
- An out-of-domain but fully-labelled validation (PKLot UFPR04, see
  EXTERNAL_VALIDATION.md) confirmed: Reference works reasonably well when
  calibrated (97.29% accuracy on classified decisions), and YOLO has zero false
  positives in this test. But MOG2 failed to calibrate on all 28 bays despite
  abundant data, and the combined Final policy produced zero vacant
  confirmations across the entire test set, because Final requires
  Reference+MOG2 agreement and YOLO cannot emit vacant (Q4).
- Decision in progress: keep MOG2 (its PKLot failure looks cadence/domain
  specific, and it has real evidence of separating classes on CHAD itself). Do
  not treat "no YOLO detection" as vacant (quantifiably risks false-vacant
  errors). Instead, test a Reference-alone opt-in vacant path with a disclosed
  false-vacant trade-off (Q5, implementation in progress in this same task).
- Completed 22 September 2026: on the selected calibrated bays, MOG2 alone was
  definite in 7/117 CHAD observations (5.98%) and 3/30 overhead observations
  (10.00%); Reference alone was definite in 18/117 (15.38%) and 4/30 (13.33%).
  Overlapping definite decisions agreed in 89/89 CHAD and 12/12 overhead cases.
  There were 101 classic confirmations without another confirming route in the
  recorded evidence; YOLO was skipped, so its hypothetical output is unknown.
  Experimental Reference priority changes calibrated-subset coverage from
  88.03% to 93.16% on CHAD and 50.00% to 60.00% overhead, resolving seven more
  vacant and two more occupied observations overall. CHAD/overhead have no
  independent labels beyond the calibration set; their accuracy and false-vacant
  rate remain unmeasured, not zero. See the [measured diagnostic](runs/verification/reference-priority/mog2-contribution.json).

## Q1 (22 Sept) — Why do bays that never change stay "uncertain" instead of
"vacant", and why did results get worse after adding the OpenCV vehicle
detector and YOLOv8s?

**Asked because:** results looked acceptable with Reference+MOG2 alone; adding
the pretrained detector and YOLOv8s made nearly all non-changing bays uncertain.

**Evidence:** MAPPING_CALIBRATION_AUDIT.md coverage table (3/9 CHAD-1, 0/5
Camera 2, 0/4 Camera 3, 0/3 Camera 4, 3/69 overhead fully two-state
calibrated); DECISION_FIX.md's removal of the 21 Sept empty-image override and
its before/after audit (245 observations flipped from vacant to uncertain with
zero underlying Reference/MOG2/YOLO state change).

**Reasoning:** Reference and MOG2 calibration both require at least 5 examples
of each state per bay with separable score distributions. A bay that never
shows a car in the available footage structurally cannot supply an occupied
example, so it can never calibrate, regardless of clip length. YOLOv8 (and the
earlier MobileNet-SSD) can only supply positive evidence of occupied, a
qualifying detection. It has no vacant class, so absence of a detection is not
evidence of vacancy. The Final rule requires Reference AND MOG2 to
independently agree vacant, or a qualifying YOLO detection, before committing
to a definite state. An uncalibratable bay with no qualifying detection is
therefore permanently uncertain by construction. A prior version (21 Sept)
worked around this with an appearance-match heuristic that let Final claim
vacant without genuine two-branch support. It was removed on 22 Sept because it
produced unsupported confidence. The "it got worse" experience is the intended
consequence of that correctness fix, not a regression from adding the
detector/YOLO themselves.

**Conclusion:** four options presented: accept uncertain as honest, obtain real
two-state footage, reintroduce a disclosed separate heuristic, or train a
dedicated classifier.

**Status:** Partially superseded by Q5, where the AND-gate structure itself,
not only missing calibration data, was shown to independently cap vacant
coverage even with abundant calibration data.

## Q2 (22 Sept) — Can AI-generated synthetic empty/full images supply missing
calibration examples? Can indoor parking video sources be found?

**Reasoning (synthetic images):** Reference and MOG2 are pixel-difference
methods, not semantic ones. A usable calibration example needs to match the
exact camera's noise, compression artifacts, lighting and shadow behavior, with
only the vehicle differing. AI-generated images are very unlikely to match this
closely enough, and a threshold fit on them would likely not transfer to real
frames. Using generated images as real camera evidence would also conflict with
this project's own documented standard of never inventing references or
converting predictions into ground truth (see WORK_LOG.md, multiple entries).

**Reasoning (indoor sources):** searched public datasets. Confirmed PKLot (all
three lots) and CNRPark are outdoor. Found only static-image, not continuous
video, indoor datasets, which could not feed MOG2's need for a continuous frame
stream. This matched the project's own prior research (WORK_LOG.md, 15 Sept
entry: MEVA, VIRAT, CNRPark, Pexels, a Toronto webcam already investigated and
rejected).

**Conclusion:** recommended recording real indoor footage if access exists, and
otherwise using PKLot/CNRPark as an algorithm-level, not indoor-specific,
validation track, since they carry full two-state ground truth CHAD/overhead
lack.

**Status:** Resolved. Led to Q3.

## Q3 (22 Sept) — "I don't care indoor vs outdoor, I want to prove OpenCV and
YOLOv8 are working. Give me a prompt for this, with reasoning."

**Reasoning:** PKLot chosen because it supplies the accuracy, precision,
recall, F1, false-vacant, false-occupied and coverage metrics required by
NgJiYeung_23026479_proposal.docx Section 3.8, which CHAD/overhead have never
been able to produce due to Q1's calibration gap. Designed as an additive,
separate validation track. Flagged in advance that MOG2's gap-reset logic,
built for continuous video, would misfire against PKLot's roughly 5-minute
sampling cadence unless generalized. Scoped to one lot, UFPR04, first.

**Conclusion:** full engineering prompt provided: verify real code first, use a
day-based 60/20/20 split with no leakage, freeze before testing, reuse real
production Reference/MOG2/YOLO code unmodified, do not touch CHAD/overhead
files, report real measured numbers only.

**Status:** Resolved, implemented. Results reviewed in Q4.

## Q4 (22 Sept) — Is terminal-only output correct? Why didn't the interactive
review interface appear? Are the PKLot results valid and useful?

**Evidence:** user-provided EXTERNAL_VALIDATION.md and WORK_LOG.md, full
held-out test tables, confusion matrices, MOG2/alignment/cadence sections.

**Reasoning:** terminal-only output is correct and intended. checks/
evaluate_pklot.py was built as a standalone, checks-only script per the Q3
prompt, confirmed unchanged (636 protected files hash-verified identical,
main.py behavior unchanged). PKLot is roughly 3,791 discrete JPEG snapshots
about 5 minutes apart across many days, not continuous video, so there is no
timeline for a periodic-review interface to display. CHAD/overhead's existing
review interface is untouched.

Verified engineering rigor: genuine day-based split, a real freeze-before-test
lock, 254 passing tests, an 80,980-check independent result audit, and
hand-verified confusion-matrix arithmetic (Reference: (3808+210)/(3808+106+6+210)
= 97.2881%, matching the report).

Central finding: MOG2 calibrated 0 of 28 bays despite 693 to 978 examples per
state per bay, a genuine separability failure, not a data shortage or a bug
(MOG2's own counters show it ran correctly: 1,576 updates, 9 gap resets under
the generalized 300-second cadence). Reference calibrated 19 of 28 bays at
97.29% accuracy on classified observations, but only about 20% coverage,
explained by the PKLot camera having physically moved partway through its
roughly two-month collection, and the project's fixed single-setup alignment
guard correctly rejecting about 68.5% of test frames as camera_view_changed or
alignment-failed rather than mis-scoring them. YOLO showed 100% precision,
accuracy, recall and F1 on the narrow slice of observations it committed to
(0.68% coverage for coco, 25.26% for aerial), but the full confusion matrices
show zero predicted-vacant observations across the entire 5,555-observation
true-vacant test set, for every method including Final. This is because
Final's classic-agreement route is mathematically unreachable whenever MOG2
never resolves, and YOLO structurally cannot emit vacant, so final_aerial and
final_coco are byte-identical to yolo_aerial and yolo_coco across every
reported number.

**Conclusion:** individual branches validate reasonably well in isolation on
this out-of-domain but fully-labelled dataset. The fused Final policy has a
structural AND-gate coverage bottleneck, demonstrated here with abundant
calibration data. This is stronger evidence than the original CHAD
data-scarcity framing from Q1: the ceiling is not only missing examples but
also the decision rule's requirement that two branches agree before any vacant
result is allowed.

**Status:** Resolved as diagnosis. Led to Q5.

## Q5 (22 Sept) — Should MOG2 be removed, given proposal implications? Can "no
YOLO detection" be treated as vacant?

**Reasoning (MOG2 removal):** recommended against it. The PKLot failure
occurred in a domain MOG2 was never built for, under a cadence, 5-minute
snapshots with a fresh model reset per day, fundamentally unlike the continuous
video it was previously validated against. On the project's actual target
domain, MOG2 has already shown real class separation: MOG2.md documents clean
separation for CHAD-P001/P002/P003, and the original all-CHAD comparison run
measured 82.05% MOG2 decision coverage. A genuine, citable limitation
regardless of the removal decision: MOG2 shares Reference's same minimum
five-examples-per-state requirement, and PKLot demonstrates abundant examples
do not guarantee separability, so collecting more data is not a guaranteed
fix. Also noted: removing MOG2 is not standalone, since it is currently the
only co-signer that lets Final ever emit vacant. Removing it without also
changing the vacant rule would make Final's vacant path impossible for every
bay, permanently. Recommended running a new diagnostic directly on the
project's own calibrated bays, measuring MOG2's real-world agreement rate with
Reference and its independent marginal decisive contribution, as a more
on-target basis for this decision than the out-of-domain PKLot result.

**Reasoning (no-detection = vacant):** recommended against it. This was already
tried in spirit (the 21 Sept empty-image override) and deliberately reverted on
22 Sept for the same reason. PKLot's confusion matrix quantifies the risk: under
the aerial profile, 967 of 6,189 truly-occupied test observations were left
uncertain rather than confirmed occupied. Roughly one in six real occupied
spaces produced no accepted detection. If uncertain had defaulted to vacant,
all 967 would have been misreported as free. Consistent with the project's own
prior documented YOLO threshold-flicker evidence (MAPPING_CALIBRATION_AUDIT.md:
ML05 scored 0.814/0.794/0.811 across three consecutive samples of a car that
never moved, crossing the 0.80 cutoff from measurement noise alone). Absence of
a YOLO detection and a calibrated Reference vacant score are different
epistemic categories: the latter is a positive measurement against a known
empty appearance, the former is only the absence of a different kind of
positive evidence.

**Conclusion:** recommended allowing Reference alone, when calibrated, to
confirm vacant, as a new, explicitly labeled, opt-in experimental path shown
alongside, never replacing, the existing default Final. Disclosed trade-off
from the frozen PKLot data: Reference-alone had a 2.71% conditional
false-vacant rate among the decisions it made on that test set.

**Status:** Implemented and checked, 22 September 2026. The default-OFF GUI
comparison and separate JSON/CSV exports preserve the primary Final. For CHAD's
117 calibrated-bay observations, counts change from 41 occupied / 62 vacant /
14 unresolved to 41 / 68 / 8; for overhead's 30, from 7 / 8 / 15 to 9 / 9 / 12.
No CHAD/overhead accuracy or false-vacant rate can be calculated without
independent labels. Frozen PKLot test coverage changes from 25.26% to 29.17%,
classified accuracy from 100.00% to 98.14%, with 106 false-vacant and 6
false-occupied observations under the alternate. Its conditional false-vacant
rate is 1.82% (106/5,814); Reference alone remains 2.71% (106/3,914). Of the
106 false-vacant observations, 84 replace correct YOLO occupied confirmations.
This is a post-hoc comparison, with no new inference or freeze changes. See
[REFERENCE_PRIORITY.md](REFERENCE_PRIORITY.md) and the
[PKLot comparison](EXTERNAL_VALIDATION.md#post-hoc-experimental-reference-priority-comparison).

## Verification notes added 22 September 2026

These notes are separate from the preserved consultation text. No inaccurate source claim was silently corrected.

### Discrepancies and limits

1. **Current state / Q1: “structurally unable to reach a definite Final.”** Too broad. Missing two-state calibration blocks classic agreement and its vacant route. A qualifying YOLO detection can still confirm occupied. The [mapping audit](MAPPING_CALIBRATION_AUDIT.md) and [saved run](runs/areas/20260921T161408_115721Z/) include such occupied results. Q1's narrower statement about an uncalibrated bay *without* a qualifying detection is consistent with the code.
2. **Q2: “all three lots.”** The repository records three views of **two physical car parks**: UFPR04 and UFPR05 view the same UFPR site, while PUCPR is another site. [Dataset description](EXTERNAL_VALIDATION.md#dataset-license-and-integrity).
3. **Q2: static images “could not feed MOG2.”** Ordered snapshots can feed the existing MOG2 implementation, as the PKLot adapter demonstrates. They omit intervening motion and differ substantially from continuous video. The record supports cadence limitations, not impossibility. [Cadence implementation and results](EXTERNAL_VALIDATION.md).
4. **Q2 source-search attribution.** The 15 September [work log](WORK_LOG.md#2026-09-15-elevated-camera-sources-vs-code-run-and-a-three-second-display) documents MEVA, VIRAT, CNRPark and Pexels review; the Toronto webcam rejection is in the earlier source-research entry. The repository does not independently establish the complete 22 September search described in the supplied consultation, or an exhaustive absence of usable indoor datasets. Those remain user-supplied recollections; no fresh source search was performed in this task.
5. **Q3: reuse “unmodified.”** The production branch algorithms were reused, but `MOG2Branch` gained an optional `expected_sample_interval` parameter for the PKLot cadence. Its omitted/default behavior remained unchanged. This addition was documented before the freeze. [Original implementation log](WORK_LOG.md#22-september-2026---separate-pklot-ufpr04-external-validation).
6. **Q4: 693–978 examples “per state.”** That range describes **vacant** examples. Occupied examples range from **592 to 881** per bay. Both still exceed the five-per-state minimum. [Exact fitting counts](data/pklot/experiment/fit.json) and [28-bay table](EXTERNAL_VALIDATION.md).
7. **Q4: zero predicted vacant “for every method.”** Incorrect for Reference: it predicted **316 vacant** observations, comprising **210 correct vacant + 106 false-vacant**. On the 5,555 truly vacant observations, Reference predicted 210 vacant, 6 occupied, 19 uncertain and 5,320 unknown. Zero vacant applies to MOG2, classic consensus, the selective YOLO rows and primary Final. [Original evaluation JSON](runs/verification/pklot/evaluation.json).
8. **Q4: Final and YOLO “byte-identical across every reported number.”** Their state counts and classification metrics match in this experiment because MOG2 never supplies classic agreement. Their reason strings, method identifiers and pipeline latency are different. This is not byte identity of the raw records. [Saved test observations](runs/verification/pklot/test/) and [processing latency](EXTERNAL_VALIDATION.md#processing-latency).
9. **Q4 interpretation.** MOG2's update counters verify that updates occurred; they do not prove there is no possible implementation issue. The measured fact is overlapping score distributions on all 28 bays under this protocol. “Individual branches validate reasonably well” should not be read as a successful MOG2 accuracy result: MOG2 classified no test observations, so its classified accuracy is undefined. Alignment rejection is a major coverage limit, alongside uncalibrated bays and between-boundary scores; it is not the sole explanation for Reference abstention. The exact contribution of cadence, lighting and geometry was not experimentally isolated.
10. **Q5: “measurement noise alone.”** ML05's 0.814/0.794/0.811 sequence and crossing of 0.80 are verified. The [audit](MAPPING_CALIBRATION_AUDIT.md) does not isolate measurement noise as the sole cause; compression, changing frame content, scale and viewpoint are plausible contributors. Same-image repeated inference was deterministic in that audit.
11. **Q5 denominator and conflict warning.** 967/6,189 refers to **alignment-accepted occupied** test observations; there were 15,118 occupied labels in the full test set, including 8,929 unknown after rejected alignment. The 967 unresolved cases are not all necessarily zero raw detections: some detections fail confidence or association checks. Also, 2.71% is Reference's conditional false-vacant rate, not the newly measured hybrid alternate's 1.82%. The same 106 errors remain; a larger occupied denominator lowers the percentage. The requested alternate can override YOLO occupied with Reference vacant and does so incorrectly in **84 test observations**.
12. **Historical versus current verification.** The supplied 636 protected-file / 254-test / 80,980-check figures describe the original PKLot delivery and remain intact. This addition passed **259 tests**, audited **40,490** selected-profile PKLot observations and **147** calibrated replay observations, and verified **927** protected files unchanged. The GUI check covered **1,088** saved bay observations across eight recordings. Original `comparison.py` is archived because its additive export support changes the current whole-file hash. The old strict frozen-run commands therefore reject today's source tree; the new read-only post-hoc scripts verify the original archive and frozen inputs. [Current delivery check](runs/verification/reference-priority/delivery-check.json), [tests](runs/verification/reference-priority/tests.xml), [GUI check](runs/verification/reference-priority/interface/result.json).

### Citation and numerical checks

| Source claim | Repository evidence and result |
|---|---|
| 3/9 Camera 1, 0/5 Camera 2, 0/4 Camera 3, 0/3 Camera 4, 3/69 overhead; minimum 5 of each state | Verified against [mapping audit](MAPPING_CALIBRATION_AUDIT.md), saved configs/MOG2 calibrations and the new [inventory diagnostic](runs/verification/reference-priority/mog2-contribution.json). |
| 245 vacant → uncertain, zero Reference/MOG2/YOLO state changes | Verified in [before/after JSON](runs/verification/decision-before-after.json); [DECISION_FIX.md](DECISION_FIX.md) and [UNRESOLVED_CHECK.md](UNRESOLVED_CHECK.md) both exist. These are observations, not unique bays or measured classification errors. |
| 60/20/20 day split; 3,791 UFPR04 frames; about 5 minutes | Verified as 18/6/6 dates and 2,341/709/741 frames in [partitions](data/pklot/partitions.json), with timestamp intervals and gaps documented in [external validation](EXTERNAL_VALIDATION.md). |
| Proposal filename and section 3.8 metrics | [NgJiYeung_23026479_proposal.docx](NgJiYeung_23026479_proposal.docx) exists. Its extracted section 3.8 lists accuracy, precision, recall, F1, confusion matrix, false-vacant, false-occupied and coverage. [Read-only extracted text](runs/verification/proposal-text.txt). Full proposal validation remains broader than this experiment. |
| 636 files, 254 tests, 80,980 checks | Verified in [original delivery audit](runs/verification/pklot-delivery-check.json) and [original test XML](runs/verification/pklot-tests-final.xml); 39,634 calibration + 41,346 test policy checks cover two detector profiles. |
| Reference arithmetic: (3808+210)/(3808+106+6+210) | 4,018/4,130 = 97.2881355932%; coverage 4,130/20,673 = 19.9777487544%. [Original evaluation](runs/verification/pklot/evaluation.json). |
| 19/28 Reference, 0/28 MOG2; 1,576 updates, 9 fitting gap resets; 300-second cadence | Verified against [fit.json](data/pklot/experiment/fit.json), [frozen config](data/pklot/experiment/config.json) and [MOG2 calibration](data/pklot/experiment/mog2-calibration.json). Empty-count range is 693–978; occupied range 592–881, as flagged above. |
| About 68.5% rejected alignment | 508/741 = 68.5560%; reasons are 188 camera_view_changed, 214 background_alignment_failed, 100 background_matches_too_concentrated and 6 insufficient_background_matches. [Original evaluation](runs/verification/pklot/evaluation.json). |
| YOLO 100% classified accuracy/precision/recall/F1; 0.68% COCO, 25.26% aerial coverage; 5,555 vacant truth labels | Verified in the original test metrics: COCO classified 140; aerial 5,222; no false positives in those classified subsets. These conditional metrics do not mean all occupied bays were detected or any vacancy was recognized. |
| MOG2 original CHAD coverage 82.05%; separated P001/P002/P003 fitting distributions | Recomputed 96/117 = 82.0512820513%, comprising 32 occupied, 64 vacant, 21 uncertain in [original observations.csv](runs/comparison/20260917T161258_089149Z/observations.csv). Three positive percentile gaps are documented in [MOG2.md](MOG2.md). This is coverage, not accuracy. |
| 967/6,189 unresolved occupied; 0.814/0.794/0.811; 0.80; 2.71% | Verified against original PKLot confusion matrices and the [mapping audit](MAPPING_CALIBRATION_AUDIT.md). See notes 10–11 for causal/denominator limits. |
| Current completion numbers | [MOG2 contribution](runs/verification/reference-priority/mog2-contribution.json), [PKLot alternate metrics](runs/verification/reference-priority/pklot-reference-priority.json) and [independent arithmetic audit](runs/verification/reference-priority/delivery-check.json). No CHAD/overhead false-vacant rate was invented. |

The title and reasoning of Q1–Q5 above remain the supplied source material; the verification notes are the implementation audit. No additional model training, source research, synthetic calibration or new dataset inference was performed for this task.
