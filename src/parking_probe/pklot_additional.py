"""Selective, attributed PKLot UFPR05/PUCPR originals for external evaluation.

This module deliberately does not modify the frozen UFPR04 experiment code.
"""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import xml.etree.ElementTree as ET

from .config import ConfigError, atomic_json, validate_polygon
from .pklot import (ARCHIVE_SHA256, ARCHIVE_SIZE, ARCHIVE_URL, CACHE,
                    OFFICIAL_URL, REVISION, WEATHER, fetch_archive, partition, sha256)
from .sources import SourceError

VIEWS = {'UFPR05': 40, 'PUCPR': 100}
LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'


def original_member(name, selected=VIEWS):
    parts = PurePosixPath(name).parts
    if len(parts) != 6 or parts[:2] != ('PKLot', 'PKLot') or parts[2] not in selected:
        return None
    _, _, view, weather, day, filename = parts
    if weather not in WEATHER or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        return None
    if not re.fullmatch(re.escape(day) + r'_\d{2}_\d{2}_\d{2}\.(jpg|xml)', filename):
        return None
    return Path(view, weather, day, filename)


def extract(directory=CACHE, selected=VIEWS, progress=print):
    directory = Path(directory)
    chosen = tuple(selected)
    if not chosen or any(v not in VIEWS for v in chosen):
        raise ValueError('Choose UFPR05 and/or PUCPR')
    receipt = directory / ('additional-' + '-'.join(chosen) + '-extraction.json')
    if receipt.exists():
        saved = json.loads(receipt.read_text(encoding='utf-8'))
        if saved.get('archive_sha256') != ARCHIVE_SHA256:
            raise SourceError('pklot_additional_receipt_mismatch')
        for index, (relative, digest) in enumerate(saved['members'].items(), 1):
            path = (directory / relative).resolve()
            if not path.is_relative_to(directory.resolve()) or not path.is_file() or sha256(path) != digest:
                raise SourceError('pklot_additional_file_integrity_failed')
            if index % 2000 == 0:
                progress(f'Verified {index} original PKLot files.')
        return saved
    archive = fetch_archive(directory, progress)
    members = {}
    progress(f'Extracting original full frames and XML for {", ".join(chosen)}…')
    with tarfile.open(archive, 'r|gz') as handle:
        for member in handle:
            relative = original_member(member.name, chosen)
            if relative is None:
                continue
            if not member.isfile() or not 0 < member.size <= 10 * 1024 * 1024:
                raise SourceError('pklot_additional_invalid_member')
            key = relative.as_posix()
            if key in members:
                raise SourceError('pklot_additional_duplicate_member')
            data = handle.extractfile(member).read(member.size + 1)
            if len(data) != member.size:
                raise SourceError('pklot_additional_truncated_member')
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            members[key] = hashlib.sha256(data).hexdigest()
            if len(members) % 2000 == 0:
                progress(f'Extracted {len(members)} original files.')
    if not members:
        raise SourceError('pklot_additional_no_originals')
    saved = {'schema_version': 1, 'archive_url': ARCHIVE_URL,
        'archive_sha256': ARCHIVE_SHA256, 'archive_size': ARCHIVE_SIZE,
        'revision': REVISION, 'official_source': OFFICIAL_URL,
        'license': LICENSE_URL, 'selected_views': list(chosen), 'members': members}
    atomic_json(receipt, saved)
    return saved


def annotation(path, view):
    maximum = VIEWS[view]
    raw = Path(path).read_bytes()
    if len(raw) > 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ConfigError('Unsafe PKLot XML')
    root = ET.fromstring(raw)
    slots, labels, seen = [], {}, set()
    for space in root.findall('space'):
        number = int(space.attrib['id'])
        if not 1 <= number <= maximum or number in seen:
            raise ConfigError(f'{view} needs unique numeric IDs in 1..{maximum}')
        seen.add(number)
        key = f'{view}-P{number:03d}'
        contour = space.find('contour')
        points = [[int(p.attrib['x']), int(p.attrib['y'])] for p in contour
                  if p.tag.lower() == 'point'] if contour is not None else []
        validate_polygon(points, 1280, 720)
        slots.append({'id': key, 'bay_id': key, 'polygon': points})
        label = space.attrib.get('occupied')
        if label not in (None, '', '0', '1'):
            raise ConfigError('Unexpected occupancy label')
        if label in ('0', '1'):
            labels[key] = 'occupied' if label == '1' else 'vacant'
    if not slots:
        raise ConfigError('No annotated bays')
    return sorted(slots, key=lambda s: s['id']), labels


def inventory(directory, view, members):
    directory = Path(directory)
    rows, orphans, seen_times = [], [], set()
    for relative in sorted(members):
        path = Path(relative)
        if path.parts[0] != view or path.suffix != '.xml':
            continue
        weather, day = path.parts[1:3]
        stamp = datetime.strptime(path.stem, '%Y-%m-%d_%H_%M_%S')
        if stamp.date().isoformat() != day or weather not in WEATHER:
            raise ConfigError('PKLot date/weather mismatch')
        if stamp in seen_times:
            raise ConfigError('Repeated view timestamp')
        seen_times.add(stamp)
        image = path.with_suffix('.jpg')
        if image.as_posix() not in members:
            orphans.append(relative)
            continue
        slots, labels = annotation(directory / path, view)
        rows.append({'view': view, 'frame_id': path.stem, 'image': image.as_posix(),
            'xml': path.as_posix(), 'day': day, 'weather': WEATHER[weather],
            'captured_local': stamp.isoformat(), 'timezone': 'unspecified_by_dataset',
            'labels': labels, 'slots': slots, 'sha256': members[image.as_posix()],
            'xml_sha256': members[relative]})
    paired = {r['image'] for r in rows}
    orphans += [relative for relative in members if relative.startswith(view + '/')
                and relative.endswith('.jpg') and relative not in paired]
    return sorted(rows, key=lambda r: r['captured_local']), sorted(orphans)


def prepare(directory=CACHE, selected=VIEWS, progress=print):
    receipt = extract(directory, selected, progress)
    result = {'schema_version': 1, 'source': OFFICIAL_URL, 'archive_url': ARCHIVE_URL,
        'archive_sha256': ARCHIVE_SHA256, 'license': LICENSE_URL,
        'use': 'external_evaluation_not_chad_accuracy', 'views': {}}
    for view in selected:
        rows, orphans = inventory(directory, view, receipt['members'])
        if not rows:
            raise ConfigError(f'{view} has no paired originals')
        groups = partition(rows)
        # The partition function checks duplicate image hashes; check day ownership explicitly.
        owners = {}
        for name, group in groups.items():
            for row in group:
                previous = owners.setdefault(row['day'], name)
                if previous != name:
                    raise ConfigError('Day crossed dataset partitions')
        view_manifest = {'view': view, 'bay_id_limit': VIEWS[view], 'orphan_members': orphans,
            'partitions': {name: {'days': sorted({r['day'] for r in group}),
                'frames': len(group), 'labelled_observations': sum(len(r['labels']) for r in group),
                'truth': dict(Counter(v for r in group for v in r['labels'].values())),
                'rows': group} for name, group in groups.items()}}
        atomic_json(Path(directory) / f'{view.lower()}-split.json', view_manifest)
        result['views'][view] = {k: v for k, v in view_manifest.items() if k != 'partitions'}
        result['views'][view]['partitions'] = {k: {f: value for f, value in p.items() if f != 'rows'}
            for k, p in view_manifest['partitions'].items()}
    atomic_json(Path(directory) / 'additional-summary.json', result)
    return result
