"""Read and update migrated report sections in the single project handbook."""
from pathlib import Path
import re

MANUAL_NAME = 'PROJECT_DOCUMENTATION.md'


def document_anchor(name):
    return 'doc-' + re.sub(r'[^a-z0-9]+', '-', name.rsplit('.', 1)[0].lower()).strip('-')


def heading_slug(text):
    text = re.sub(r'<[^>]+>', '', text).lower().replace('`', '')
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'\s', '-', text.strip())


def decorate_section(contents, name):
    """Add unique, stable GitHub anchors; keep fenced code untouched."""
    prefix = document_anchor(name)
    result, counts, fence = [], {}, None
    for line in contents.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            kind = marker[1][0]
            if fence is None:
                fence = kind
            elif fence == kind:
                fence = None
            result.append(line)
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)', line) if fence is None else None
        if heading:
            slug = heading_slug(heading[2])
            count = counts.get(slug, 0)
            counts[slug] = count + 1
            suffix = f'-{count}' if count else ''
            result.append(f'<a id="{prefix}--{slug}{suffix}"></a>')
            line = '#' * min(6, len(heading[1]) + 2) + ' ' + heading[2]
        result.append(line)
    return '\n'.join(result) + '\n'


def undecorate_section(contents, name):
    prefix = document_anchor(name)
    result, fence = [], None
    for line in contents.splitlines():
        if line.startswith(f'<a id="{prefix}--') and line.endswith('</a>'):
            continue
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            kind = marker[1][0]
            if fence is None:
                fence = kind
            elif fence == kind:
                fence = None
            result.append(line)
            continue
        heading = re.match(r'^(#{3,6})\s+(.+)', line) if fence is None else None
        if heading:
            line = '#' * (len(heading[1]) - 2) + ' ' + heading[2]
        result.append(line)
    return '\n'.join(result).strip('\n') + '\n'


def read_document(root, name):
    manual = (Path(root) / MANUAL_NAME).read_text(encoding='utf-8')
    start, end = f'<!-- BEGIN DOCUMENT: {name} -->', f'<!-- END DOCUMENT: {name} -->'
    if manual.count(start) != 1 or manual.count(end) != 1:
        raise ValueError(f'Missing or duplicate handbook section: {name}')
    section = manual.split(start, 1)[1].split(end, 1)[0].strip('\n')
    return undecorate_section(section, name)


def replace_document(root, name, contents):
    path = Path(root) / MANUAL_NAME
    manual = path.read_text(encoding='utf-8')
    start, end = f'<!-- BEGIN DOCUMENT: {name} -->', f'<!-- END DOCUMENT: {name} -->'
    if manual.count(start) != 1 or manual.count(end) != 1:
        raise ValueError(f'Missing or duplicate handbook section: {name}')
    before, remaining = manual.split(start, 1)
    _, after = remaining.split(end, 1)
    path.write_text(before + start + '\n' + decorate_section(contents, name) + end + after,
                    encoding='utf-8')
    return path
