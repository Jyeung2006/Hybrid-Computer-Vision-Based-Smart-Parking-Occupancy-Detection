"""Render saved PKLot measurements as Markdown; never runs/tunes a model."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from parking_probe.config import atomic_json


def number(value):
    return 'undefined' if value is None else f'{value:.4f}'


def render():
    path = ROOT/'runs/verification/pklot-evaluation.json'
    r = json.loads(path.read_text())
    selected = r['selected_profile']
    phases = r['partition_summary']
    final = r['test']['methods']['final_'+selected]['all']
    fitted = r['calibration']['boundaries']
    fitted_counts = {k: sum(b['status']=='calibrated' for b in values.values()) for k,values in fitted.items()}
    lines = ['# External validation: PKLot UFPR04', '',
        'Measured 22 September 2026. This is a separate, reproducible validation of the existing production Reference, MOG2 and selective YOLOv8s branches.', '',
        '**Scope:** outdoor UFPR04 only. These results do not establish, change or improve CHAD/overhead accuracy, their missing calibration, or performance on any indoor/live camera. This experiment can reveal failures; adequate example counts do not guarantee separable scores.', '',
        f'**Measured outcome:** the selected `{selected}` pipeline achieved **{number(final["accuracy_on_classified_pct"])}% accuracy on classified decisions**, at **{number(final["decision_coverage_pct"])}% coverage**. Fitting calibrated **{fitted_counts["reference"]}/28 Reference** bays and **{fitted_counts["mog2"]}/28 MOG2** bays. Final confirmed **{final["confusion"]["true_vacant"]+final["confusion"]["false_vacant"]} vacant observations**. These results do not demonstrate a generally accurate, complete parking-occupancy system.', '',
        '## Run it', '',
        'From the project folder in the VS Code PowerShell terminal:', '',
        '```powershell', r'.\.venv\Scripts\python.exe checks/evaluate_pklot.py', '```', '',
        'The delivered test is already complete: this command checks the frozen experiment and displays its saved measurements rather than fitting or testing it again. It does not open or change the parking interface. Normal `main.py` behavior is unchanged.', '',
        'On a fresh checkout, the same command downloads the 4.90 GB archive, verifies it, extracts UFPR04, prepares the day split, fits thresholds, compares profiles on calibration data, freezes settings and evaluates both profiles on the test days. No API key, GPU or new dependency is required; use the existing Python environment. Allow about 7 GB of disk space for the archive, extracted data and results.', '',
        'Optional staged commands on an **unopened experiment**:', '',
        '```powershell', r'.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase prepare',
        r'.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase fit',
        r'.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase calibrate',
        r'.\.venv\Scripts\python.exe checks/evaluate_pklot.py --phase test', '```', '',
        'Once `test-started.json` exists, fitting/calibration are locked. Implementation, runtime, references, thresholds, model manifest and partition hashes must match the freeze. Completed test days are reused from checkpoints. A process interrupted inside a day may repeat that unfinished day under the identical freeze; it cannot retune parameters. Do not delete the lock and reuse these test days for model selection.', '',
        '## Verified production interfaces and proposal scope', '',
        'Before changes, read the current `catalog.py`, `areas.py`, `view_presets.py`, `comparison.py`, `yolo.py`, `mog2.py`, `mog2_calibration.py`, `monitor.py`, `evaluation.py` and `output.py`. Also checked the proposal sections 3.7–3.8, configuration, vision, source and registration code.', '',
        '- `prepare_preset`, `prepare_mog2` and `run_comparison` expect video files/frame indexes, not XML snapshot sequences. The closest equivalent is `SnapshotRecording`: it supplies chronological real `Frame` objects to the unchanged `Analyzer.analyze`, `MOG2Branch.analyze`, `YOLOBranch.analyze` and `yolo.final_decision` algorithms. It uses the existing classic `consensus` function as an OpenCV-only baseline.',
        '- Recipes/configurations use string `id` values, integer-coordinate `polygon` entries and individual `reference_image` files. Reference calibration carries setup/reference/polygon/preprocessing hashes. MOG2 calibration carries a model signature. The new converter and fitter produce these existing formats.',
        '- Existing evaluation supported multiple labelled slots but computed single-branch metrics inline. `ClassificationMetrics` is now shared by both evaluators; `reference_boundaries` shares the existing percentile fitting and metadata. No duplicate Reference or MOG2 classifier was introduced.',
        '- The proposal also describes probability fusion, fine-tuning, a full-frame YOLO-only comparator, temporal confirmation, Brier score, deployment and operational experiments. This scoped addition measures the currently implemented selective pipeline. Its YOLO rows are **selective verification**, not a YOLO-only whole-dataset classifier; appearance scores are not occupancy probabilities. Those broader proposal stages remain separate.', '',
        '## Dataset, license and integrity', '',
        'Dataset: [PKLot](https://web.inf.ufpr.br/vri/databases/parking-lot-database/), Almeida et al., *Expert Systems with Applications* 42(11):4937–4949 (2015), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [local attribution](third_party/PKLOT-LICENSE.md). UFPR04 and UFPR05 are two views of one UFPR car park; PUCPR is another car park. Only UFPR04 is used here.', '',
        'The university domain did not resolve locally. The [pinned original-archive mirror](https://huggingface.co/datasets/teenygrad/pklot/tree/9604b05ad6dfd5ab5817b5fa6600d375754562fb) supplied the original JPEG/XML archive. This is not a resized/reshuffled Roboflow export.', '',
        f'- Archive size: **4,898,276,304 bytes**; SHA-256 `{r["archive_sha256"]}`.',
        '- The downloaded bytes matched the mirror’s published Git LFS hash. No independent university-side checksum was available. Source revision is pinned in code; extracted member hashes are recorded and checked.',
        '- Extracted **3,791 original 1280×720 images and 3,791 XML files**, with 28 stable slot IDs. The parser accepts original `<point>` and `<Point>` spelling. Unknown/missing occupancy annotations are excluded from binary ground truth, not silently labelled vacant.',
        f'- Labelled slot observations: **{sum(p["labelled_observations"] for p in phases.values()):,}**; unlabelled slot/frame pairs: **{sum(p["unlabelled_observations"] for p in phases.values()):,}**.',
        '- Frames retain their filename capture timestamp with an unspecified dataset timezone. Historical capture time is separate from local decode/processing time, so old dataset dates do not trigger the live stale-frame guard.', '',
        '## Fixed day split', '',
        f'Random seed **{r["seed"]}**, sorted unique dates shuffled with Python `random.Random`, largest-remainder 60/20/20 allocation. Weather folders do not define sessions: the same date always remains in one partition. No image sampling was used. Byte-content duplication is rejected during partitioning; decoded-content overlap/duplication is rejected during analysis.', '',
        '| Partition | Days | Frames | Labelled bays | Occupied truth | Vacant truth | Unlabelled | Sunny / cloudy / rainy frames |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for name, p in phases.items():
        w = p['weather_frames']
        lines.append(f'| {name} | {len(p["days"])} | {p["frames"]} | {p["labelled_observations"]} | {p["truth"].get("occupied",0)} | {p["truth"].get("vacant",0)} | {p["unlabelled_observations"]} | {w.get("sunny",0)} / {w.get("cloudy",0)} / {w.get("rainy",0)} |')
    for name, p in phases.items():
        lines.extend(['', f'**{name} dates:** ' + ', '.join(p['days']) + '.'])
    lines.extend(['', 'These are 60/20/20 percentages of days, not necessarily of frames. The class mix differs materially across partitions; this is reported rather than balanced using test labels. The authors’ original split protocol differs; this experiment uses the user-requested proposal split.', '',
        '## Fitting data and geometry', '',
        f'All **{len(r["calibration"]["references"])} / 28** references come from XML-labelled vacant fitting frames that passed the production alignment check. The first complete fitting frame supplies the fixed setup geometry. A reference may be shared across bays when all those bays are labelled empty; every frame used as any reference is excluded from threshold-fitting scores for every bay. Other images pass unchanged at original resolution.', '',
        'The fitting set contains three distinct polygon/camera arrangements. Fitting-image inspection confirmed that the camera moved between periods. A fixed first-fit setup is deliberately retained: the production eight-pixel alignment guard rejects displaced views. No test geometry is used to move a polygon or create a new reference. Consequently this is a test of a fixed-configuration pipeline on the whole UFPR04 sequence, including its changed-view failure handling, not a claim that every dataset image has a calibrated camera configuration.', '',
        'Reviewed fitting-only geometry examples:', '',
        '![Initial fitting camera position](runs/verification/pklot-fit-geometry-0.png)', '',
        '![Second fitting camera position](runs/verification/pklot-fit-geometry-1.png)', '',
        '![Third fitting camera position](runs/verification/pklot-fit-geometry-2.png)', '',
        'The existing fitter uses the 95th percentile of vacant scores and 5th percentile of occupied scores. At least five examples of each state are necessary, but overlapping distributions remain uncalibrated regardless of sample count. There is no threshold lowering or automatic empty override.', '',
        '![Fitting score distributions for three representative bays](runs/verification/pklot-fit-score-distributions.png)', '',
        '| Bay | Reference vacant / occupied | Reference status | MOG2 vacant / occupied | MOG2 status |',
        '|---|---:|---|---:|---|'])
    bounds = r['calibration']['boundaries']
    for key, ref in bounds['reference'].items():
        mog = bounds['mog2'][key]
        def status(value):
            return value['status'] + (': '+value['reason'] if value.get('reason') else '')
        lines.append(f'| {key} | {ref["vacant_count"]} / {ref["occupied_count"]} | {status(ref)} | {mog["vacant_count"]} / {mog["occupied_count"]} | {status(mog)} |')
    lines.extend(['', 'Skipped fitting frames (scores excluded; invalid images never update MOG2): `' + json.dumps(r['calibration']['skipped_frames'], sort_keys=True) + '`.', '',
        'Exact percentile boundaries, reference frame identities, per-slot sample hashes and per-day MOG2 counts are in the JSON report and `data/pklot/experiment/fit.json`. All fitting scores are retained in `fit-scores.json`.', '',
        'For scale comparison only, the original CHAD B01/B02/B03 MOG2 calibration used vacant/occupied counts **10/25, 21/11 and 26/6** (see [FINAL_RESULTS.md](FINAL_RESULTS.md) and its stored calibration). Those are different cameras/data and are not combined here. Example quantity alone cannot be compared as accuracy.', '',
        '## Calibration and frozen profile selection', '',
        'Both fixed **YOLOv8s (small)** profiles use OpenCV DNN, 640×640 full-frame input, a 0.80 qualifying vehicle score and the existing unique-bay overlap/anchor association. COCO uses the existing 0.82 vertical anchor; aerial uses 0.50. Weights, cutoffs, classic thresholds and final-decision policy are unchanged during calibration and testing.', '',
        'Calibration chooses the profile with the largest fraction of all labelled observations decided correctly; ties prefer fewer false-vacant errors, then COCO. This penalizes abstention rather than rewarding 100% accuracy on very few decisions. No thresholds or neural weights are fitted using calibration/test labels.', '',
        f'**Selected before test: `{selected}`.** This is the empirically better operating profile under these fixed settings, not an isolated proof that anchor geometry alone caused the difference.', '',
        '| Profile | Calibration accuracy on classified % | Coverage % | Correct / all truth % | False vacant | False occupied |',
        '|---|---:|---:|---:|---:|---:|'])
    for p in ('coco','aerial'):
        m = r['calibrate']['methods']['final_'+p]['all']
        lines.append(f'| {p} | {number(m["accuracy_on_classified_pct"])} | {number(m["decision_coverage_pct"])} | {number(m["correct_decisions_all_truth_pct"])} | {m["confusion"]["false_vacant"]} | {m["confusion"]["false_occupied"]} |')
    lines.extend(['', f'Freeze SHA-256: `{r["frozen_sha256"]}`. Both test profiles below were specified in advance; the primary profile is not reselected by test performance.', '',
        '## Held-out test metrics', '',
        '**Definitions:** occupied is positive. Accuracy, precision, recall and F1 below are computed on definite occupied/vacant predictions. Coverage is definite predictions divided by all labelled observations. The full 2×4 matrix retains uncertain and unknown predictions. “Correct / all” also penalizes abstentions. Undefined means the denominator is zero, not an unmeasured placeholder.', '',
        'False-vacant (FV) = true occupied predicted vacant; false-occupied (FO) = true vacant predicted occupied. Rates labelled “all” use **all** occupied/vacant ground truth respectively; conditional rates use only the corresponding classified ground truth. A zero FV rate with low coverage is not proof of safe vacancy detection.', '',
        '| Method | Accuracy % | Precision % | Recall % | F1 % | Coverage % | Correct / all % |',
        '|---|---:|---:|---:|---:|---:|---:|'])
    methods = ('reference','mog2','opencv_consensus','yolo_coco','yolo_aerial','final_coco','final_aerial')
    for method in methods:
        m = r['test']['methods'][method]['all']
        keys = ('accuracy_on_classified_pct','precision_on_classified_pct','recall_on_classified_pct','f1_on_classified_pct','decision_coverage_pct','correct_decisions_all_truth_pct')
        lines.append('| '+method+' | '+' | '.join(number(m[k]) for k in keys)+' |')
    lines.extend(['', '**Abstention-sensitive occupied detection:** conditional recall/F1 can be 100% when the system only confirms a few cars and never decides vacant. The following recall counts unresolved occupied observations as missed positives. Its F1 combines that recall with occupied precision; unresolved observations remain unknown/uncertain in the confusion matrix and are not relabelled vacant.', '',
        '| Method | Occupied precision % | Occupied recall over all true occupied % | F1 including missed occupied observations % |',
        '|---|---:|---:|---:|'])
    derived = {}
    for method in methods:
        m = r['test']['methods'][method]['all']; c = m['confusion']
        tp, fp, positives = c['true_occupied'], c['false_occupied'], m['ground_truth_counts']['occupied']
        f1 = 200*tp/(tp+fp+positives) if tp+fp+positives else None
        derived[method] = {'precision_pct': m['precision_on_classified_pct'],
            'occupied_recall_all_truth_pct': m['occupied_recall_all_truth_pct'],
            'f1_including_unresolved_occupied_as_missed_pct': f1}
        lines.append(f'| {method} | {number(m["precision_on_classified_pct"])} | {number(m["occupied_recall_all_truth_pct"])} | {number(f1)} |')
    atomic_json(ROOT/'runs/verification/pklot-abstention-metrics.json', {
        'basis': 'algebraic postprocessing of frozen test confusion counts; no new inference or tuning',
        'frozen_sha256': r['frozen_sha256'], 'methods': derived})
    lines.extend(['', 'These additional values are saved in [pklot-abstention-metrics.json](runs/verification/pklot-abstention-metrics.json). The primary report retains the original conditional metrics and full confusion matrices.'])
    lines.extend(['', '| Method | TP | TN | FV | FO | FV/all occupied % | FO/all vacant % | Conditional FV % | Conditional FO % |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
    for method in methods:
        m = r['test']['methods'][method]['all']; c = m['confusion']
        vals = [str(c[k]) for k in ('true_occupied','true_vacant','false_vacant','false_occupied')]
        vals += [number(m[k]) for k in ('false_vacant_rate_all_occupied_pct','false_occupied_rate_all_vacant_pct','false_vacant_rate_on_classified_occupied_pct','false_occupied_rate_on_classified_vacant_pct')]
        lines.append('| '+method+' | '+' | '.join(vals)+' |')
    lines.extend(['', 'The YOLO rows include all labelled bays; `not_requested_opencv_agreement` appears as unknown for that branch and is not a failed inference. Requested-only measurements are also reported in JSON:', '',
        '| Selective verifier | Requested labelled observations | Classified | Accuracy % | Coverage within requests % |', '|---|---:|---:|---:|---:|'])
    for p in ('coco','aerial'):
        m = r['test']['methods'].get('yolo_'+p+'_requested_only',{}).get('all')
        if m:
            lines.append(f'| {p} | {m["binary_observations"]} | {m["classified_observations"]} | {number(m["accuracy_on_classified_pct"])} | {number(m["decision_coverage_pct"])} |')
    lines.extend(['', '### Full confusion matrices', '', '| Method | Truth | Predicted occupied | Predicted vacant | Uncertain | Unknown |', '|---|---|---:|---:|---:|---:|'])
    for method in methods:
        for truth, cells in r['test']['methods'][method]['all']['confusion_matrix'].items():
            lines.append('| '+method+' | '+truth+' | '+' | '.join(str(cells[k]) for k in ('occupied','vacant','uncertain','unknown'))+' |')
    lines.extend(['', '### Weather-stratified test metrics', '',
        '| Method | Weather | N | Accuracy % | Precision % | Recall % | F1 % | Coverage % | FV / FO | FV/all occupied % | FO/all vacant % |',
        '|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|'])
    for method in methods:
        for weather in ('sunny','cloudy','rainy'):
            m = r['test']['methods'][method][weather]
            vals = [number(m[k]) for k in ('accuracy_on_classified_pct','precision_on_classified_pct','recall_on_classified_pct','f1_on_classified_pct','decision_coverage_pct')]
            c = m['confusion']
            lines.append(f'| {method} | {weather} | {m["binary_observations"]} | '+ ' | '.join(vals)+f' | {c["false_vacant"]} / {c["false_occupied"]} | {number(m["false_vacant_rate_all_occupied_pct"])} | {number(m["false_occupied_rate_all_vacant_pct"])} |')
    lines.extend(['', 'The JSON contains each weather stratum’s complete confusion matrix and conditional/unconditional error rates. Rainy test coverage is based on only 34 snapshots; do not infer broad weather robustness from this small subset. Adjacent observations remain correlated within days.', '',
        '## Alignment, abstentions and MOG2 cadence', '',
        '| Partition | Frames | Alignment failures | MOG2 updates | MOG2 gap resets |', '|---|---:|---|---:|---:|'])
    for phase in ('calibrate','test'):
        p = r[phase]
        lines.append(f'| {phase} | {p["frames"]} | `{json.dumps(p["alignment_failures"],sort_keys=True)}` | {p["mog2_updates"]} | {p["mog2_gap_resets"]} |')
    lines.extend(['', f'Selected final profile `{selected}`, stratified by the **unchanged** alignment guard:', '',
        '| Alignment | Labelled observations | Accuracy % | Coverage % | Correct / all % |', '|---|---:|---:|---:|---:|'])
    for group in ('alignment_accepted','alignment_rejected'):
        m = r['test']['methods']['final_'+selected].get(group)
        if m:
            lines.append(f'| {group} | {m["binary_observations"]} | {number(m["accuracy_on_classified_pct"])} | {number(m["decision_coverage_pct"])} | {number(m["correct_decisions_all_truth_pct"])} |')
    lines.extend(['', '- Reference score distributions can overlap because of lighting, reflections, shadows and different vehicle appearances. An occupied score below the empty distribution cannot be repaired merely by collecting more copies of the same states.',
        '- Reference calibration is unknown when invalid/overlapping; MOG2 is uncertain when uncalibrated. YOLO is requested for any unresolved or conflicting pair, but frame alignment failure prevents inference. A qualifying vehicle can confirm occupied. No detection remains uncertain and cannot establish vacancy. Definite classic agreement is retained exactly.',
        '- `MOG2Branch(..., expected_sample_interval=300)` resets after a gap **greater than 1,500 seconds** (five expected intervals). Omitting this new keyword preserves the previous 15-second video limit and existing calibration signatures, including other replay sampling intervals. CHAD/overhead settings/assets are unchanged.',
        '- Every dataset day starts a fresh model seeded from **fitting-only** empty reference patches. Updates follow the chronological snapshots, including unlabelled bays, at the existing 0.001 per-observation learning rate. The model adapts unsupervised during a held-out day; labels never enter its updates. No model state crosses days or partitions.',
        '- Five minutes of unseen movement occur between snapshots. At this cadence, 500 samples span roughly 41.7 hours rather than 25 minutes at three seconds. MOG2 does not store a literal 500-image buffer: the explicit 0.001 learning rate controls adaptation and is not rescaled to wall time. Do not present this as continuous-video motion performance. Two observations after a gap reset retain the existing restabilizing behavior.',
        '- The legacy 15-second limit would reset at ordinary 300-second intervals. Regression tests verify zero such resets at 300-second spacing and a reset only beyond the new limit; actual counts above also include real larger gaps and gaps caused by unusable images. This is a cadence behavior check, not a measured continuous-video accuracy comparison.', '',
        '## Processing latency', '',
        'Milliseconds on this Windows computer with the existing Python/OpenCV environment, CPU DNN and two OpenCV threads. Per-profile pipeline sums include image decoding/checksum, Reference, MOG2 and that selective verifier. Both profiles were executed sequentially for this experiment; this is not a dedicated production throughput benchmark. File reporting and UI rendering are excluded. Failures/skipped inference can make unconditional latency look faster.', '',
        '| Stage | Samples | Median ms | P95 ms | Maximum ms |', '|---|---:|---:|---:|---:|'])
    for name, value in r['test']['latency_ms'].items():
        lines.append(f'| {name} | {value["samples"]} | {number(value["median"])} | {number(value["p95"])} | {number(value["maximum"])} |')
    lines.extend(['', 'Test YOLO error/skip reasons: `'+json.dumps(r['test']['yolo_errors'],sort_keys=True)+'`. Alignment-rejection reasons are propagated by the verifier and mean inference was blocked by the source/view guard, not that ONNX inference crashed.', '',
        '## Artifacts and reproducibility', '',
        '- [`checks/evaluate_pklot.py`](checks/evaluate_pklot.py): staged/runnable check, independent of the app.',
        '- [`runs/verification/pklot-evaluation.json`](runs/verification/pklot-evaluation.json): complete measured report, exact unrounded metrics and per-bay counts.',
        '- [`data/pklot/partitions.json`](data/pklot/partitions.json): immutable split, original image/XML hashes, truth labels and original polygons. Individual phase manifests are under `data/pklot/manifests/`.',
        '- [`data/pklot/experiment/`](data/pklot/experiment/): derived recipe, setup, reference copies, config, fit scores and MOG2 calibration. No examples are added to existing cameras.',
        '- [`runs/verification/pklot/frozen.json`](runs/verification/pklot/frozen.json): exact selected profile, code/runtime/model/artifact fingerprints and calibration measurements.',
        '- [`runs/verification/pklot/test-started.json`](runs/verification/pklot/test-started.json): test-opening receipt. `calibrate/` and `test/` retain per-day, per-frame, per-bay predictions, branch reasons, scores and timing.',
        '- [`checks/render_pklot_report.py`](checks/render_pklot_report.py): regenerate this document from saved measurements without inference.',
        '- [`checks/plot_pklot_fit.py`](checks/plot_pklot_fit.py): regenerate the fitting-only geometry views and score histograms. This optional plotting command needs Matplotlib (already installed here); evaluation itself needs only the existing core dependencies.',
        '- [`checks/check_pklot_results.py`](checks/check_pklot_results.py): independently audit saved label identities, decision routing, confusion counts, ratios, freeze and protected files without inference.',
        '- [`tests/test_pklot.py`](tests/test_pklot.py): XML formats, day leakage, metric denominators, gap behavior/signature compatibility, snapshot chronology, profile selection, test locks and real-branch adapter/checkpoint integration.', '',
        'Verification: **254 tests passed in 64.16 seconds**; [test report](runs/verification/pklot-tests-final.xml). The [saved-result audit](runs/verification/pklot-delivery-check.json) checks all calibration/test observations against original labels, branch routing, matrix arithmetic, disjoint dates/content and the freeze. It confirms **636 protected existing files unchanged**. [Legacy signature checks](runs/verification/pklot-legacy-signatures.json) also confirm existing current-camera MOG2 calibration signatures still match. The application UI was not relaunched for this checks-only addition.', '',
        'Model manifest: [`assets/models/yolov8s-manifest.json`](assets/models/yolov8s-manifest.json). No fine-tuning occurred. The existing COCO/VisDrone pretrained weights are used as supplied; this experiment does not audit their complete upstream training provenance.', '',
        '## Interpretation and next work', '',
        'Use the measured classified accuracy **together with coverage and error counts**. Low coverage or poor metrics are an experimental finding, not grounds to retune against these test dates. Large per-bay calibration counts do not prove that simple single-reference difference and MOG2 features separate occupancy under changing illumination or camera geometry.', '',
        'A later, separately designed experiment could fit camera-position-specific configurations or guarded registration using development data, and compare a parking-specific occupied/vacant classifier. That would need new untouched test data or an explicitly new validation protocol; it must not be reported as an improvement on this already-used holdout. This deliverable preserves the current algorithm and records its limits.', '',
        'No live camera, indoor accuracy, current parking availability, deployment, or CHAD/overhead accuracy improvement is claimed. No hardware installation, web service, database or Flutter work was performed.'])
    output = ROOT/'EXTERNAL_VALIDATION.md'
    # Preserve the separately labelled, post-hoc section when regenerating the
    # original frozen report. It is not part of that experiment's freeze.
    marker = '<!-- REFERENCE_PRIORITY_POSTHOC -->'
    previous = output.read_text(encoding='utf-8') if output.exists() else ''
    appendix = '\n\n' + marker + previous.split(marker, 1)[1] if marker in previous else ''
    if appendix:
        lines[2:2] = ['**22 September comparison update:** the original frozen results below are retained. '
            'The current source tree adds an opt-in alternate policy, so the old strict frozen-run commands reject its changed whole-file hash. '
            'For the saved-data comparison, run `checks/compare_reference_priority.py`; see the '
            '[post-hoc section](#post-hoc-experimental-reference-priority-comparison) and '
            '[consultation verification notes](AI_CONSULTATION_LOG.md#verification-notes-added-22-september-2026).', '']
    output.write_text('\n'.join(lines)+'\n'+appendix, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    render()
