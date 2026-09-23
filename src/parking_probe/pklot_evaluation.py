"""Independent UFPR04 experiment orchestrating the production CV branches.

No classification algorithm lives here: Analyzer, MOG2Branch, YOLOBranch and
final_decision are the same implementations used by the application's replay.
"""
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import platform
import shutil
import time

import cv2
import numpy as np

from .catalog import PROJECT_ROOT
from .comparison import consensus
from .config import Config, ConfigError, atomic_json
from .evaluation import ClassificationMetrics, reference_boundaries
from .mog2 import MOG2Branch
from .pklot import (ARCHIVE_SHA256, ARCHIVE_URL, CACHE, REVISION, SEED,
                    acquire, inventory, partition, partition_summary, sha256)
from .sources import Frame, read_image, utcnow
from .vision import Analyzer, pixel_hash, thresholds
from .yolo import DECISION_POLICY, YOLOBranch, YOLODetector, VerificationService, final_decision

EXPECTED_INTERVAL = 300
PROFILES = ('coco', 'aerial')
PROTOCOL = {
    'version': 1, 'seed': SEED, 'split': [0.6, 0.2, 0.2], 'group': 'whole_calendar_day_across_weather',
    'reference_selection': 'first_aligned_fit_vacancy_per_bay; entire_reference_frames_excluded_from_threshold_fit',
    'thresholds': 'fit_partition_only: vacant_95th_and_occupied_5th_percentiles; overlapping_bounds_rejected',
    'profile_selection': 'highest_calibrate_final_correct_decisions_all_truth; then fewer_false_vacant; then coco',
    'profiles': list(PROFILES), 'expected_sample_interval_seconds': EXPECTED_INTERVAL,
    'mog2_gap_reset_seconds': EXPECTED_INTERVAL * 5, 'mog2_sessions': 'fresh_fit_reference_seed_each_day',
    'test': 'both_frozen_profiles; selected_profile_chosen_before_test; completed_days_never_reinferred',
    'decision_policy': DECISION_POLICY, 'opencv_threads': 2,
}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def code_fingerprint():
    names = ['pklot.py', 'pklot_evaluation.py', 'evaluation.py', 'vision.py', 'mog2.py',
             'yolo.py', 'config.py', 'sources.py', 'comparison.py']
    return {name: sha256(Path(__file__).parent / name) for name in names}


def forbid_after_test(output):
    if (output / 'test-started.json').exists():
        raise ConfigError('Test already opened: fitting, calibration and profile selection are now locked.')


def prepare(directory=CACHE, progress=print):
    directory = Path(directory)
    source = acquire(directory, progress)
    groups = partition(inventory(source))
    manifest = {'schema_version': 1, 'dataset': 'PKLot UFPR04', 'archive_url': ARCHIVE_URL,
        'archive_sha256': ARCHIVE_SHA256, 'mirror_revision': REVISION, 'seed': SEED,
        'split': 'whole dates; largest-remainder 60/20/20', 'summary': partition_summary(groups),
        'partitions': groups}
    path = directory / 'partitions.json'
    if path.exists() and load(path) != manifest:
        raise ConfigError('Saved PKLot partition manifest differs; refusing to reshuffle.')
    if not path.exists():
        atomic_json(path, manifest)
        for name, rows in groups.items():
            atomic_json(directory / f'manifests/{name}.json', rows)
    for name, item in manifest['summary'].items():
        progress(f'{name:9s}: {len(item["days"]):2d} days | {item["frames"]:4d} frames | '
                 f'{item["labelled_observations"]:6d} labelled bays')
    return manifest


class SnapshotRecording:
    """Original-size timestamped frames, with a separate historical time axis."""
    def __init__(self, directory, rows):
        self.directory = Path(directory)
        self.rows = sorted(rows, key=lambda row: row['captured_local'])
        if len({r['day'] for r in rows}) != 1:
            raise ConfigError('A PKLot pseudo-recording must contain exactly one day.')
        if len({r['captured_local'] for r in rows}) != len(rows):
            raise ConfigError('Duplicate snapshot timestamps.')
        self.origin = datetime.fromisoformat(self.rows[0]['captured_local'])

    def __iter__(self):
        for row in self.rows:
            started = time.perf_counter()
            path = self.directory / row['image']
            if sha256(path) != row['sha256']:
                raise ConfigError('Snapshot checksum changed after partition freeze.')
            image = read_image(path)
            if image.shape != (720, 1280, 3):
                raise ConfigError('UFPR04 snapshot resolution changed.')
            # Old dataset time is not live freshness. Preserve it separately;
            # the production stale guard applies to local decoding time only.
            frame = Frame(image, utcnow(), frame_id=row['frame_id'])
            position = (datetime.fromisoformat(row['captured_local'])-self.origin).total_seconds()
            yield row, frame, position, (time.perf_counter()-started)*1000


def day_groups(rows):
    result = defaultdict(list)
    for row in rows:
        result[row['day']].append(row)
    return sorted(result.items())


def make_branch(analyzer, calibration=None):
    return MOG2Branch(analyzer, calibration, interval=EXPECTED_INTERVAL,
                      expected_sample_interval=EXPECTED_INTERVAL)


def make_fit_config(directory, rows, progress):
    """Only fitting pixels and fitting XML labels can select a reference."""
    full = next((r for r in rows if len(r['slots']) == 28), None)
    if full is None:
        raise ConfigError('No fitting frame contains all 28 UFPR04 polygons.')
    target = directory / 'experiment'
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(directory / full['image'], target / 'setup.jpg')
    slots = [{k: v for k, v in s.items() if k in ('id', 'bay_id', 'polygon')} for s in full['slots']]
    recipe = {'version': 1, 'source_id': 'PKLot-UFPR04', 'source_resolution': [1280, 720],
        'analysis_resolution': [1280, 720], 'setup_frame_id': full['frame_id'], 'slots': slots}
    atomic_json(target / 'recipe.json', recipe)
    atomic_json(target / 'config.json', {'version': 1, 'source_id': 'PKLot-UFPR04',
        'source': {'type': 'recorded_video'}, 'interval_seconds': EXPECTED_INTERVAL,
        'stale_after_seconds': 15, 'setup_image': 'setup.jpg', 'slots': slots})
    config = Config(target / 'config.json')
    analyzer = Analyzer(config)
    references = {}
    for row in rows:
        candidates = [s for s in config.data['slots']
                      if s['id'] not in references and row['labels'].get(s['id']) == 'vacant']
        if not candidates:
            continue
        image = read_image(directory / row['image'])
        if not analyzer.alignment(image)['ok']:
            continue
        for slot in candidates:
            reference = target / 'references' / (slot['id'] + '.jpg')
            reference.parent.mkdir(exist_ok=True)
            shutil.copyfile(directory / row['image'], reference)
            slot['reference_image'] = config.relative(reference)
            references[slot['id']] = {'frame_id': row['frame_id'], 'day': row['day'],
                'weather': row['weather'], 'label': 'vacant', 'pixel_hash': pixel_hash(image),
                'source_image': row['image'], 'label_author': 'original PKLot annotation'}
        if len(references) == 28:
            break
    config.save()
    atomic_json(target / 'references.json', references)
    progress(f'Fitting-only empty references: {len(references)}/28 bays.')
    return config, references


def fit(directory, manifest, output, progress=print):
    forbid_after_test(output)
    fit_path = directory / 'experiment/fit.json'
    if fit_path.exists():
        saved = load(fit_path)
        if saved['partition_sha256'] != sha256(directory / 'partitions.json'):
            raise ConfigError('Fitted partition fingerprint changed.')
        progress('Using saved PKLot fit thresholds (no refitting).')
        return saved
    rows = manifest['partitions']['fit']
    config, references = make_fit_config(directory, rows, progress)
    analyzer = Analyzer(config)
    forbidden = set(analyzer.reference_hashes.values())
    groups = {method: defaultdict(lambda: {'vacant': [], 'occupied': [], 'hashes': set(), 'days': set()})
              for method in ('reference', 'mog2')}
    skipped = Counter()
    pixels = set()
    day_stats, observations = [], []
    canonical = {s['id']: s['polygon'] for s in analyzer.slot_config}
    geometry_differences = Counter()
    for day, day_rows in day_groups(rows):
        cv2.setRNGSeed(SEED)
        branch = make_branch(analyzer)
        for row, frame, position, decode_ms in SnapshotRecording(directory, day_rows):
            value = pixel_hash(frame.image)
            if value in pixels:
                raise ConfigError('Repeated decoded fitting image cannot count as independent data.')
            pixels.add(value)
            for slot in row['slots']:
                if canonical[slot['id']] != slot['polygon']:
                    geometry_differences[slot['id']] += 1
            reference = analyzer.analyze(frame)
            mog = branch.analyze(frame, position, reference)
            if value in forbidden:
                skipped['reference_source_frames'] += 1
                continue
            if reference['analysis_status'] != 'estimated':
                skipped[reference['error']] += 1
                continue
            for method, result, score_field in (('reference', reference, 'difference_score'),
                                                 ('mog2', mog, 'foreground_ratio')):
                for slot in result['slots']:
                    key = slot['slot_id']
                    truth = row['labels'].get(key)
                    score = slot[score_field]
                    if truth is None or score is None:
                        continue
                    group = groups[method][key]
                    group[truth].append(score)
                    group['hashes'].add(value)
                    group['days'].add(day)
                    observations.append({'frame_id': row['frame_id'], 'day': day, 'weather': row['weather'],
                        'slot_id': key, 'truth': truth, 'method': method, 'score': score})
        day_stats.append({'day': day, 'frames': len(day_rows), 'updates': branch.update_count,
                          'gap_resets': branch.reset_count})
        progress(f'Fit {day}: {len(day_rows)} snapshots, {branch.update_count} MOG2 updates, {branch.reset_count} gap resets.')
    boundaries = {'reference': {}, 'mog2': {}}
    for slot in config.data['slots']:
        key = slot['id']
        group = groups['reference'][key]
        decision = reference_boundaries(analyzer, slot, group['vacant'], group['occupied'], group['hashes'], group['days'])
        slot['calibration'] = decision
        boundaries['reference'][key] = decision
        group = groups['mog2'][key]
        boundaries['mog2'][key] = {**thresholds(group['vacant'], group['occupied']),
            'vacant_count': len(group['vacant']), 'occupied_count': len(group['occupied'])}
    config.save()
    branch = make_branch(Analyzer(config))
    atomic_json(directory / 'experiment/mog2-calibration.json', {'model_signature': branch.signature,
        'parameters': branch.parameters, 'sample_interval_seconds': EXPECTED_INTERVAL,
        'slots': boundaries['mog2'], 'source_sessions': sorted({r['day'] for r in rows})})
    report = {'created_at': utcnow().isoformat(), 'partition_sha256': sha256(directory / 'partitions.json'),
        'references': references, 'boundaries': boundaries, 'skipped_frames': dict(skipped),
        'fit_pixel_hashes': sorted(pixels), 'mog2_days': day_stats,
        'geometry_differences_from_fit_setup': dict(geometry_differences),
        'geometry_policy': 'one fixed setup polygon per physical bay; never use test geometry to move polygons'}
    atomic_json(directory / 'experiment/fit-scores.json', observations)
    atomic_json(fit_path, report)
    return report


def latency(values):
    values = [v for v in values if v is not None]
    return {'samples': len(values), 'median': float(np.median(values)) if values else None,
            'p95': float(np.percentile(values, 95)) if values else None,
            'maximum': float(max(values)) if values else None}


def summarize_days(days):
    metrics = defaultdict(ClassificationMetrics)
    times = defaultdict(list)
    reasons = defaultdict(Counter)
    frame_errors, requested, yolo_errors = Counter(), Counter(), Counter()
    frame_count = labels = 0
    for day in days:
        for frame in day['frames']:
            frame_count += 1
            if frame['alignment_error']:
                frame_errors[frame['alignment_error']] += 1
            for name, value in frame['latency_ms'].items():
                times[name].append(value)
            for profile in PROFILES:
                requested[profile] += frame['requests'][profile]
                if frame['yolo_errors'][profile]:
                    yolo_errors[f'{profile}:{frame["yolo_errors"][profile]}'] += 1
            for row in frame['observations']:
                labels += 1
                for name, state in row['states'].items():
                    alignment_group = 'alignment_rejected' if frame['alignment_error'] else 'alignment_accepted'
                    for stratum in ('all', frame['weather'], row['slot_id'], alignment_group):
                        metrics[(name, stratum)].add(row['truth'], state)
                    reasons[name][row['reasons'][name] or 'definite_decision'] += 1
                for profile in PROFILES:
                    if row['requested'][profile]:
                        metrics[(f'yolo_{profile}_requested_only', 'all')].add(row['truth'], row['states'][f'yolo_{profile}'])
    methods = sorted({k[0] for k in metrics})
    return {'frames': frame_count, 'labelled_observations': labels,
        'methods': {name: {stratum: metrics[name, stratum].result()
                          for method, stratum in sorted(list(metrics)) if method == name} for name in methods},
        'latency_ms': {name: latency(values) for name, values in times.items()},
        'state_reasons': {name: dict(counts) for name, counts in reasons.items()},
        'alignment_failures': dict(frame_errors), 'requested_bay_observations': dict(requested),
        'yolo_errors': dict(yolo_errors),
        'mog2_updates': sum(d['mog2_updates'] for d in days),
        'mog2_gap_resets': sum(d['mog2_gap_resets'] for d in days),
        'days': [d['day'] for d in days],
        'metric_note': 'Occupied positive. Accuracy/P/R/F1 condition on classified observations; coverage and 2x4 matrices include abstentions. YOLO not-requested = unknown, reported separately from requested-only metrics.'}


def evaluate_partition(directory, rows, output, phase, analyzer, calibration, service,
                       forbidden_pixels, identity, progress=print):
    """Atomic per-day checkpoints: interrupted tests resume without retesting completed days."""
    days = []
    seen_pixels = set(forbidden_pixels)
    for day, day_rows in day_groups(rows):
        day_path = output / phase / f'{day}.json'
        if day_path.exists():
            saved = load(day_path)
            if saved['identity'] != identity or saved['frame_ids'] != [r['frame_id'] for r in day_rows]:
                raise ConfigError('Saved day checkpoint differs from frozen experiment.')
            days.append(saved)
            seen_pixels.update(saved['pixel_hashes'])
            progress(f'{phase} {day}: using completed day checkpoint.')
            continue
        cv2.setRNGSeed(SEED)
        branch = make_branch(analyzer, calibration)
        verifiers = {profile: YOLOBranch(analyzer, service, profile) for profile in PROFILES}
        frames, pixel_hashes = [], []
        for index, (row, frame, position, decode_ms) in enumerate(SnapshotRecording(directory, day_rows)):
            started = time.perf_counter()
            value = pixel_hash(frame.image)
            if value in seen_pixels:
                raise ConfigError('Decoded image leakage or duplicate evaluation content.')
            seen_pixels.add(value)
            pixel_hashes.append(value)
            reference = analyzer.analyze(frame)
            mog = branch.analyze(frame, position, reference)
            refs = {s['slot_id']: s for s in reference['slots']}
            mogs = {s['slot_id']: s for s in mog['slots']}
            ys = {profile: verifier.analyze(frame.image, reference, mog) for profile, verifier in verifiers.items()}
            by_yolo = {profile: {s['slot_id']: s for s in y['slots']} for profile, y in ys.items()}
            observations = []
            for key, truth in row['labels'].items():
                states = {'reference': refs[key]['state'], 'mog2': mogs[key]['state']}
                reasons = {'reference': refs[key]['reason'], 'mog2': mogs[key]['reason']}
                states['opencv_consensus'] = consensus(states['reference'], states['mog2'])
                reasons['opencv_consensus'] = 'agreement' if states['opencv_consensus'] in ('occupied','vacant') else 'unresolved_classic_evidence'
                for profile in PROFILES:
                    y = by_yolo[profile][key]
                    states[f'yolo_{profile}'], reasons[f'yolo_{profile}'] = y['state'], y['reason']
                    states[f'final_{profile}'], reasons[f'final_{profile}'] = final_decision(states['reference'], states['mog2'], y['state'])
                observations.append({'slot_id': key, 'truth': truth, 'states': states, 'reasons': reasons,
                    'reference_difference_score': refs[key]['difference_score'],
                    'mog2_foreground_ratio': mogs[key]['foreground_ratio'],
                    'requested': {p: by_yolo[p][key]['requested'] for p in PROFILES},
                    'yolo_detector_score': {p: by_yolo[p][key]['detector_score'] for p in PROFILES}})
            timing = {'decode': decode_ms, 'reference': reference['processing_duration_ms'], 'mog2': mog['processing_duration_ms']}
            for profile in PROFILES:
                timing[f'yolo_{profile}'] = ys[profile]['processing_duration_ms']
                timing[f'pipeline_{profile}'] = sum((timing[m] or 0) for m in ('decode', 'reference', 'mog2', f'yolo_{profile}'))
            timing['both_profiles_wall'] = (time.perf_counter()-started)*1000 + decode_ms
            frames.append({'frame_id': row['frame_id'], 'source_id': 'PKLot-UFPR04',
                'captured_local': row['captured_local'], 'capture_timezone': 'unspecified_by_dataset',
                'processed_at': utcnow().isoformat(), 'input_mode': 'historical_periodic_snapshots',
                'freshness_basis': 'local_image_decode_not_live_capture', 'weather': row['weather'],
                'alignment_error': reference['error'], 'alignment': reference['alignment'],
                'latency_ms': timing, 'observations': observations,
                'requests': {p: len(ys[p]['requested_slot_ids']) for p in PROFILES},
                'yolo_errors': {p: ys[p]['error'] for p in PROFILES},
                'mog2_reset_count': branch.reset_count,
                'unlabelled_bays_excluded_from_metrics': 28-len(row['labels'])})
            if (index+1) % 25 == 0:
                progress(f'{phase} {day}: {index+1}/{len(day_rows)} frames processed.')
        saved = {'schema_version': 1, 'identity': identity, 'day': day,
            'frame_ids': [r['frame_id'] for r in day_rows], 'pixel_hashes': pixel_hashes,
            'mog2_updates': branch.update_count, 'mog2_gap_resets': branch.reset_count, 'frames': frames}
        atomic_json(day_path, saved)
        days.append(saved)
        progress(f'{phase} {day}: completed {len(frames)} snapshots.')
    return summarize_days(days), sorted(seen_pixels - set(forbidden_pixels))


def select_profile(report):
    def rank(profile):
        value = report['methods'][f'final_{profile}']['all']
        return (value['correct_decisions_all_truth_pct'] or 0,
                -value['confusion']['false_vacant'], profile == 'coco')
    return max(PROFILES, key=rank)


def artifact_fingerprints(directory):
    names = ['partitions.json', 'experiment/config.json', 'experiment/recipe.json',
             'experiment/references.json', 'experiment/mog2-calibration.json', 'experiment/fit.json',
             'experiment/setup.jpg']
    names.extend(p.relative_to(directory).as_posix() for p in (directory/'experiment/references').glob('*.jpg'))
    return {name: sha256(directory/name) for name in names}


def freeze(directory, output, calibration_report, cal_pixels, identity):
    forbid_after_test(output)
    result = {'schema_version': 1, 'created_at': utcnow().isoformat(), 'protocol': PROTOCOL,
        'code': code_fingerprint(), 'artifacts': artifact_fingerprints(directory),
        'models_manifest_sha256': sha256(PROJECT_ROOT/'assets/models/yolov8s-manifest.json'),
        'runtime': {'python': platform.python_version(), 'opencv': cv2.__version__, 'numpy': np.__version__},
        'selected_profile': select_profile(calibration_report), 'calibrate_identity': identity,
        'calibrate_pixel_hashes': cal_pixels, 'calibrate_report': calibration_report}
    atomic_json(output/'frozen.json', result)
    return result


def verify_frozen(directory, output):
    frozen = load(output/'frozen.json')
    if frozen['protocol'] != PROTOCOL or frozen['code'] != code_fingerprint():
        raise ConfigError('Frozen protocol/implementation changed; do not retune against this test set.')
    if frozen['artifacts'] != artifact_fingerprints(directory):
        raise ConfigError('Frozen calibration/reference/partition artifact changed.')
    if frozen['runtime'] != {'python': platform.python_version(), 'opencv': cv2.__version__, 'numpy': np.__version__}:
        raise ConfigError('Frozen runtime version changed.')
    if frozen['models_manifest_sha256'] != sha256(PROJECT_ROOT/'assets/models/yolov8s-manifest.json'):
        raise ConfigError('Frozen YOLO model manifest changed.')
    return frozen


def run(phase='all', directory=CACHE, output=None, progress=print):
    directory = Path(directory)
    output = Path(output or PROJECT_ROOT/'runs/verification/pklot')
    output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(PROTOCOL['opencv_threads'])
    cv2.setRNGSeed(SEED)
    if phase in ('all', 'prepare') and not (output/'test-started.json').exists():
        manifest = prepare(directory, progress)
    else:
        manifest = load(directory/'partitions.json')
    if phase == 'prepare':
        return manifest
    if phase in ('all', 'fit') and not (output/'test-started.json').exists():
        fitted = fit(directory, manifest, output, progress)
    else:
        fitted = load(directory/'experiment/fit.json')
    if phase == 'fit':
        forbid_after_test(output)
        return fitted
    analyzer = Analyzer(Config(directory/'experiment/config.json'))
    calibration = load(directory/'experiment/mog2-calibration.json')
    detector = YOLODetector()  # Verifies both ONNX files, also on cached-report reads.
    service = VerificationService(detector)
    try:
        if phase in ('all', 'calibrate') and not (output/'test-started.json').exists():
            identity = digest({'code': code_fingerprint(), 'protocol': PROTOCOL,
                               'artifacts': artifact_fingerprints(directory)})
            measured, pixels = evaluate_partition(directory, manifest['partitions']['calibrate'], output,
                'calibrate', analyzer, calibration, service, fitted['fit_pixel_hashes'], identity, progress)
            frozen = freeze(directory, output, measured, pixels, identity)
            progress('Frozen profile selected using calibration only: ' + frozen['selected_profile'])
        else:
            if phase == 'calibrate':
                forbid_after_test(output)
            frozen = verify_frozen(directory, output)
        if phase == 'calibrate':
            return frozen
        frozen = verify_frozen(directory, output)
        identity = sha256(output/'frozen.json')
        started = output/'test-started.json'
        if started.exists():
            if load(started)['frozen_sha256'] != identity:
                raise ConfigError('Test freeze changed after opening the test partition.')
        else:
            atomic_json(started, {'started_at': utcnow().isoformat(), 'frozen_sha256': identity})
        complete = output/'evaluation.json'
        if complete.exists():
            report = load(complete)
            if report['frozen_sha256'] != identity:
                raise ConfigError('Completed evaluation belongs to a different freeze.')
            progress('Returning saved test measurements; completed test is not rerun.')
            return report
        test_report, _ = evaluate_partition(directory, manifest['partitions']['test'], output, 'test',
            analyzer, calibration, service, fitted['fit_pixel_hashes'] + frozen['calibrate_pixel_hashes'], identity, progress)
        report = {'schema_version': 1, 'evaluation_type': 'external_labelled_periodic_snapshots',
            'dataset': 'PKLot UFPR04', 'created_at': utcnow().isoformat(), 'frozen_sha256': identity,
            'archive_sha256': ARCHIVE_SHA256, 'archive_url': ARCHIVE_URL, 'seed': SEED,
            'protocol': PROTOCOL, 'partition_summary': manifest['summary'],
            'calibration': fitted, 'selected_profile': frozen['selected_profile'],
            'calibrate': frozen['calibrate_report'], 'test': test_report,
            'domain_note': 'Different outdoor UFPR04 camera only. No CHAD/overhead/indoor accuracy claim or calibration change.',
            'mog2_note': 'Five-minute snapshots, fresh empty-seeded background each day, gap reset above 25 minutes. Learning rate is per snapshot; intervening motion is unobserved. Not equivalent to continuous video.',
            'live_camera_validation': 'not_performed'}
        atomic_json(complete, report)
        atomic_json(output.parent/'pklot-evaluation.json', report)
        return report
    finally:
        service.close()


def console_summary(report):
    if 'test' not in report:
        return
    print('\nPKLot UFPR04 | HELD-OUT TEST | selected before test: ' + report['selected_profile'])
    print('Method          Accuracy Precision Recall     F1 Coverage | false vacant / occupied')
    def number(value):
        return '   n/a' if value is None else f'{value:6.2f}'
    for method in ('reference', 'mog2', 'yolo_coco', 'yolo_aerial', 'final_coco', 'final_aerial'):
        m = report['test']['methods'][method]['all']
        values = ' '.join(number(m[key]) for key in ('accuracy_on_classified_pct', 'precision_on_classified_pct',
            'recall_on_classified_pct', 'f1_on_classified_pct', 'decision_coverage_pct'))
        print(f'{method:<15} {values} | {m["confusion"]["false_vacant"]:6d} / {m["confusion"]["false_occupied"]:6d}')
    print('Percentages; accuracy/P/R/F1 on classified decisions. Read coverage alongside them.')
    print('Outdoor external-domain results only; CHAD/overhead calibration is unchanged.')
