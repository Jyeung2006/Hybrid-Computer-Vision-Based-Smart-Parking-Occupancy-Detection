"""Create a portable Spotlens website/API package from reviewed local inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from parking_probe.catalog import CLIPS
from parking_probe.areas import OVERHEAD
from parking_probe.opencv_first import DECISION_POLICY


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    dest = ROOT / 'spotlens'
    if dest.exists():
        raise SystemExit('spotlens already exists; preserve/review that package before rebuilding.')
    if not (ROOT / 'apps/parking_web/build/web/index.html').is_file():
        raise SystemExit('Build Flutter web before packaging.')
    dest.mkdir()
    copied = []

    def copy_file(relative, target=None):
        source = ROOT / relative
        out = dest / (target or relative)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, out)
        copied.append((relative, out.relative_to(dest).as_posix()))

    def tree(relative, target=None, excludes=()):
        for p in sorted((ROOT / relative).rglob('*')):
            if p.is_file() and not set(p.relative_to(ROOT / relative).parts).intersection(excludes):
                copy_file(p.relative_to(ROOT).as_posix(),
                    str(Path(target or relative) / p.relative_to(ROOT / relative)))

    tree('src/parking_probe', excludes=('__pycache__',))
    tree('presets')
    tree('assets/models')
    tree('data/models/mobilenet-ssd')
    tree('apps/parking_web', excludes=('build', '.dart_tool', '.idea', 'parking_web.iml', 'run-web.ps1'))
    tree('apps/parking_web/build/web', 'public')
    tree('third_party')
    copy_file('pyproject.toml')
    # Carry the same two authoritative documents as the full checkout.
    copy_file('README.md')
    copy_file('PROJECT_DOCUMENTATION.md')
    for clip in (*CLIPS, OVERHEAD):
        path = f'data/{"other-parking" if clip == OVERHEAD else "chad"}/{clip.member}'
        if (ROOT / path).stat().st_size != clip.size or digest(ROOT / path) != clip.sha256:
            raise ValueError(f'Video integrity failed: {path}')
        copy_file(path)

    # Include just the two active caches. References are relative to each cache,
    # and runtime preparation checks the same signature before reusing it.
    import cv2
    caches = []
    for preset, clips, directory in (
        ('chad-camera-1-expanded.json', CLIPS, 'data/chad-mapped/Camera-1'),
        ('overhead-all-bays.json', (OVERHEAD,), 'data/overhead-all')):
        recipe_path = ROOT / 'presets' / preset
        recipe = json.loads(recipe_path.read_text(encoding='utf-8'))
        required = {recipe['setup'][0]}
        for slot in recipe['slots']:
            if slot.get('reference'):
                required.add(slot['reference'][0])
            required.update(item[0] for item in slot.get('vehicle_empty_references', []))
            for state in ('vacant', 'occupied'):
                required.add(slot[state]['clip'])
                required.update(group['clip'] for group in slot.get('additional_samples', {}).get(state, []))
        signature = hashlib.sha256(recipe_path.read_bytes() + cv2.__version__.encode() +
            ''.join(c.sha256 for c in clips if c.id in required).encode()).hexdigest()[:16]
        relative = f'{directory}/preset-{signature}'
        if not (ROOT / relative / 'ready.json').exists():
            raise ValueError(f'Active cache missing: {relative}')
        tree(relative)
        caches.append(relative)

    # Preserve source run IDs/times rather than presenting old results as new.
    histories, selected = set(), []
    for site, ids in (('chad', [c.id for c in CLIPS]), ('overhead', [OVERHEAD.id])):
        for clip_id in ids:
            for run in sorted((ROOT / 'runs/areas').glob('*'), reverse=True):
                history = run / site / 'history.jsonl'
                if not history.is_file():
                    continue
                found = False
                with history.open(encoding='utf-8') as f:
                    for line in f:
                        if not line.endswith('\n'):
                            continue
                        try:
                            batch = json.loads(line)
                            found |= any(p.get('recording_id') == clip_id and
                                p.get('final', {}).get('decision_policy') == DECISION_POLICY
                                for p in batch.get('recordings', []))
                        except (ValueError, TypeError):
                            continue
                if found:
                    histories.add(history.relative_to(ROOT).as_posix())
                    selected.append({'recording': clip_id, 'original_run_id': run.name})
                    break
            else:
                raise ValueError(f'No saved OpenCV-first result for {clip_id}')
    for history in sorted(histories):
        copy_file(history)
    for p in sorted((ROOT / 'scripts/spotlens').rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            copy_file(p.relative_to(ROOT).as_posix(),
                p.relative_to(ROOT / 'scripts/spotlens').as_posix())
    (dest / '.gitignore').write_text('.venv/\n.env\n__pycache__/\nverification-results.json\n', encoding='utf-8')
    manifest = {'schema_version': 1, 'packaged_at': datetime.now(timezone.utc).isoformat(),
        'source': str(ROOT), 'python_version': sys.version.split()[0], 'opencv_version': cv2.__version__,
        'decision_policy': DECISION_POLICY, 'live_availability': False,
        'prepared_caches': caches, 'historical_results': selected, 'files': []}
    for p in sorted(dest.rglob('*')):
        if p.is_file():
            manifest['files'].append({'path': p.relative_to(dest).as_posix(),
                'bytes': p.stat().st_size, 'sha256': digest(p)})
    manifest['total_bytes'] = sum(p['bytes'] for p in manifest['files'])
    (dest / 'package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'folder': str(dest), 'files': len(manifest['files']),
        'bytes': manifest['total_bytes'], 'caches': caches, 'historical_results': selected}, indent=2))


if __name__ == '__main__':
    main()
