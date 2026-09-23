"""Pinned, checks-only PKLot acquisition and original XML conversion.

The mirror distributes the original archive, including original XML; it is not
the resized Roboflow export. No dataset code is downloaded or executed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import re
import tarfile
import time
import xml.etree.ElementTree as ET

import requests

from .catalog import PROJECT_ROOT
from .config import ConfigError, atomic_json, validate_polygon
from .sources import SourceError

REVISION = '9604b05ad6dfd5ab5817b5fa6600d375754562fb'
ARCHIVE_URL = f'https://huggingface.co/datasets/teenygrad/pklot/resolve/{REVISION}/PKLot.tar.gz'
ARCHIVE_SHA256 = 'e89bbc1dc735298c478688d50c7a682fb3b0076a87b6634923132709f2d2fa9b'
ARCHIVE_SIZE = 4898276304
OFFICIAL_URL = 'https://web.inf.ufpr.br/vri/databases/parking-lot-database/'
CACHE = PROJECT_ROOT / 'data/pklot'
SEED = 20260922
WEATHER = {'Sunny': 'sunny', 'Cloudy': 'cloudy', 'Rainy': 'rainy'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fetch_archive(directory=CACHE, progress=print):
    """Three bounded attempts, resumable bytes, mandatory final size + SHA-256."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'PKLot.tar.gz'
    if target.exists():
        if target.stat().st_size == ARCHIVE_SIZE and sha256(target) == ARCHIVE_SHA256:
            progress('PKLot archive cache verified.')
            return target
        raise SourceError('pklot_cached_archive_integrity_failed')
    partial = target.with_suffix('.gz.part')
    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > ARCHIVE_SIZE:
            raise SourceError('pklot_partial_file_oversized')
        try:
            if offset < ARCHIVE_SIZE:
                headers = {'Accept-Encoding': 'identity'}
                if offset:
                    headers['Range'] = f'bytes={offset}-'
                with requests.get(ARCHIVE_URL, headers=headers, stream=True, timeout=(10, 30)) as response:
                    response.raise_for_status()
                    if response.status_code == 206:
                        if response.headers.get('Content-Range') != f'bytes {offset}-{ARCHIVE_SIZE-1}/{ARCHIVE_SIZE}':
                            raise SourceError('pklot_invalid_content_range')
                    elif response.status_code == 200:
                        offset = 0
                    else:
                        raise SourceError('pklot_unexpected_download_status')
                    size = offset
                    last = time.monotonic()
                    deadline = last + 3600
                    with partial.open('ab' if offset else 'wb') as handle:
                        for block in response.iter_content(1024 * 1024):
                            size += len(block)
                            if size > ARCHIVE_SIZE or time.monotonic() > deadline:
                                raise SourceError('pklot_download_bound_exceeded')
                            handle.write(block)
                            if time.monotonic() - last >= 10:
                                progress(f'PKLot download {size / ARCHIVE_SIZE:.1%} ({size / 1e9:.2f} GB).')
                                last = time.monotonic()
            if partial.stat().st_size != ARCHIVE_SIZE:
                raise SourceError('pklot_download_truncated')
            progress('Verifying PKLot archive SHA-256...')
            if sha256(partial) != ARCHIVE_SHA256:
                partial.unlink()  # Only this downloader's known partial file.
                raise SourceError('pklot_archive_checksum_mismatch')
            partial.replace(target)
            return target
        except (requests.RequestException, SourceError) as exc:
            progress(f'PKLot attempt {attempt+1}/3 failed: {type(exc).__name__}.')
            if attempt == 2:
                raise SourceError('pklot_download_failed_after_three_attempts') from exc
    raise AssertionError('unreachable')


def ufpr04_member(name):
    """Allowlist original full frames/XML only; never extract archive paths blindly."""
    parts = PurePosixPath(name).parts
    if len(parts) != 6 or parts[:3] != ('PKLot', 'PKLot', 'UFPR04'):
        return None
    _, _, _, weather, day, filename = parts
    if weather not in WEATHER or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        return None
    if not re.fullmatch(re.escape(day) + r'_\d{2}_\d{2}_\d{2}\.(jpg|xml)', filename):
        return None
    return Path('UFPR04', weather, day, filename)


def acquire(directory=CACHE, progress=print):
    directory = Path(directory)
    receipt = directory / 'extraction.json'
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved.get('archive_sha256') != ARCHIVE_SHA256:
            raise SourceError('pklot_extraction_version_mismatch')
        for index, (name, digest) in enumerate(saved['members'].items(), 1):
            path = (directory / name).resolve()
            if not path.is_relative_to(directory.resolve()) or not path.is_file() or sha256(path) != digest:
                raise SourceError('pklot_extracted_member_integrity_failed')
            if index % 1000 == 0:
                progress(f'Verified {index}/{len(saved["members"])} cached UFPR04 files.')
        progress(f'PKLot UFPR04 cache verified ({len(saved["members"])} files).')
        return directory / 'UFPR04'
    archive = fetch_archive(directory, progress)
    members = {}
    progress('Extracting only original UFPR04 images and XML...')
    with tarfile.open(archive, 'r|gz') as handle:
        for member in handle:
            relative = ufpr04_member(member.name)
            if relative is None:
                continue
            if not member.isfile() or not 0 < member.size <= 10 * 1024 * 1024:
                raise SourceError('pklot_invalid_archive_member')
            name = relative.as_posix()
            if name in members:
                raise SourceError('pklot_duplicate_archive_member')
            data = handle.extractfile(member).read(member.size + 1)
            if len(data) != member.size:
                raise SourceError('pklot_truncated_archive_member')
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            members[name] = hashlib.sha256(data).hexdigest()
    if len(members) != 2 * 3791:
        raise SourceError(f'pklot_unexpected_ufpr04_file_count:{len(members)}')
    atomic_json(receipt, {'schema_version': 1, 'archive_url': ARCHIVE_URL,
        'archive_sha256': ARCHIVE_SHA256, 'archive_size': ARCHIVE_SIZE, 'revision': REVISION,
        'members': members})
    return directory / 'UFPR04'


def annotation(path):
    """Return production-format integer polygons plus dataset truth separately."""
    raw = Path(path).read_bytes()
    if len(raw) > 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ConfigError('PKLot XML must not contain a DTD/entity or exceed 1 MiB.')
    root = ET.fromstring(raw)
    slots, labels, seen = [], {}, set()
    for space in root.findall('space'):
        number = int(space.attrib['id'])
        if not 1 <= number <= 28 or number in seen:
            raise ConfigError('UFPR04 needs unique numeric slot IDs in 1..28.')
        seen.add(number)
        key = f'UFPR04-P{number:02d}'
        # The original archive uses both <point> and <Point> in its contours.
        contour = space.find('contour')
        points = [[int(p.attrib['x']), int(p.attrib['y'])] for p in contour
                  if p.tag.lower() == 'point'] if contour is not None else []
        validate_polygon(points, 1280, 720)
        slots.append({'id': key, 'bay_id': key, 'polygon': points})
        label = space.attrib.get('occupied')
        if label not in (None, '', '0', '1'):
            raise ConfigError('Unexpected PKLot occupancy label.')
        if label in ('0', '1'):
            labels[key] = 'occupied' if label == '1' else 'vacant'
    return sorted(slots, key=lambda s: s['id']), labels


def inventory(directory):
    """Metadata only: no pixel/model inspection of held-out images."""
    directory = Path(directory)
    rows, seen_time = [], set()
    for path in sorted(directory.glob('*/*/*.xml')):
        weather, day = path.relative_to(directory).parts[:2]
        timestamp = datetime.strptime(path.stem, '%Y-%m-%d_%H_%M_%S')
        if timestamp.date().isoformat() != day or weather not in WEATHER:
            raise ConfigError('PKLot filename/date/weather mismatch.')
        if timestamp in seen_time:
            raise ConfigError('Duplicate PKLot frame timestamp.')
        seen_time.add(timestamp)
        image = path.with_suffix('.jpg')
        if not image.exists():
            raise ConfigError('PKLot XML has no matching image.')
        slots, labels = annotation(path)
        rows.append({'frame_id': path.stem, 'image': image.relative_to(directory.parent).as_posix(),
            'xml': path.relative_to(directory.parent).as_posix(), 'day': day,
            'captured_local': timestamp.isoformat(), 'timezone': 'unspecified_by_dataset',
            'weather': WEATHER[weather], 'labels': labels, 'slots': slots,
            'sha256': sha256(image), 'xml_sha256': sha256(path)})
    return sorted(rows, key=lambda r: r['captured_local'])


def partition(rows, seed=SEED):
    """Shuffle whole dates; largest-remainder 60/20/20, never weather folders."""
    days = sorted({r['day'] for r in rows})
    if len(days) < 5:
        raise ConfigError('At least five independent days required for 60/20/20.')
    random.Random(seed).shuffle(days)
    quotas = [len(days) * value for value in (.6, .2, .2)]
    counts = [int(q) for q in quotas]
    for i in sorted(range(3), key=lambda i: (-(quotas[i] - counts[i]), i))[:len(days)-sum(counts)]:
        counts[i] += 1
    groups, offset = {}, 0
    for name, count in zip(('fit', 'calibrate', 'test'), counts, strict=True):
        selected = set(days[offset:offset+count])
        groups[name] = [r for r in rows if r['day'] in selected]
        offset += count
    owners = {}
    for name, group in groups.items():
        for row in group:
            if row['sha256'] in owners:
                raise ConfigError('Duplicate image bytes: resolve duplicates before partitioning.')
            owners[row['sha256']] = name
    return groups


def partition_summary(groups):
    return {key: {'days': sorted({r['day'] for r in rows}), 'frames': len(rows),
        'labelled_observations': sum(len(r['labels']) for r in rows),
        'unlabelled_observations': sum(28-len(r['labels']) for r in rows),
        'weather_frames': dict(Counter(r['weather'] for r in rows)),
        'truth': dict(Counter(label for r in rows for label in r['labels'].values()))}
        for key, rows in groups.items()}
