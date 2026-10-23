"""Aider-style SEARCH/REPLACE edits rendered as a unified diff through the existing workspace gate.

Alternative to the line-handle protocol, which cannot express an insert. Insert = SEARCH an anchor,
REPLACE with anchor plus new lines. The original snapshot is only read.
"""
import ast
import difflib
import re

from kairos_api.investigations.patches import source_path
from scripts.edit_preflight024 import dangling_removals

_BLOCK = re.compile(r'^(?P<path>[^\n]+)\n<{7} SEARCH\n(?P<s>.*?)^={7}\n(?P<r>.*?)^>{7} REPLACE[ \t]*$', re.S | re.M)


_FENCE = re.compile(r'\A```[\w+-]*\n|^```\n\Z', re.M)


def parse_blocks(text):
    """(path, search, replace) per block; prose and ``` fences around or inside blocks are ignored."""
    return [(m['path'].strip().strip('`').strip(), _FENCE.sub('', m['s']), _FENCE.sub('', m['r'])) for m in _BLOCK.finditer(text)
            if not m['path'].lstrip().startswith(('<<<<<<<', '=======', '>>>>>>>'))]


def _resolve(root, prefix, path, search, replace, spans):
    """A copied `path/to/` placeholder is stripped; a path still outside the captured files maps to the one
    captured file where SEARCH locates exactly once; otherwise it is left to fail validation."""
    path = re.sub(r'^(path/to/)+', '', path)
    paths = {p for p, _, _ in spans or []}
    if spans is None or path in paths:
        return path
    hits = [p for p in sorted(paths) if isinstance(_locate(source_path(root, prefix, p).read_text(), search, replace), tuple)]
    return hits[0] if len(hits) == 1 else path


def _locate(original, search, replace):
    """(start, end, replace) of the single whole-line match, else a reason string.

    Exact whole-line match first; then, like Aider, a match that differs only by one uniform leading-whitespace
    prefix, re-applied to REPLACE (the 14B copies snippets dedented to column 0).
    """
    search, replace = [t if not t or t.endswith('\n') else t + '\n' for t in (search, replace)]
    lines = original.splitlines(True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    part = search.splitlines(True)
    exact = [i for i in range(len(lines) - len(part) + 1) if lines[i:i + len(part)] == part]
    if len(exact) == 1:
        i = exact[0]
        return offsets[i], offsets[i + len(part)], replace
    if exact:
        return 'matches at lines ' + ', '.join(str(i + 1) for i in exact)
    indent = min((len(l) - len(l.lstrip()) for l in part + replace.splitlines(True) if l.strip()), default=0)
    part = [l[indent:] if l.strip() else l for l in part]
    new = [l[indent:] if l.strip() else l for l in replace.splitlines(True)]
    loose = []
    for i in range(len(lines) - len(part) + 1):
        window, lead = lines[i:i + len(part)], None
        for have, want in zip(window, part):
            if not want.strip():
                if have.strip():
                    break
                continue
            if not have.endswith(want) or have[:len(have) - len(want)].strip():
                break
            lead = have[:len(have) - len(want)] if lead is None else lead
            if have != lead + want:
                break
        else:
            loose.append((i, lead or ''))
    if len(loose) == 1:
        i, lead = loose[0]
        return offsets[i], offsets[i + len(part)], ''.join(lead + l if l.strip() else l for l in new)
    if loose:
        return 'matches at lines ' + ', '.join(str(i + 1) for i, _ in loose)
    size = max(len(part), 1)
    best = max(range(max(len(lines) - size + 1, 1)), key=lambda i: difflib.SequenceMatcher(
        None, ''.join(lines[i:i + size]).strip(), ''.join(part).strip()).ratio())
    shown = ''.join(lines[best:best + min(size, 6)])
    return f'no match; closest lines {best + 1}-{best + min(size, 6)}:\n{shown}'



def _span(region):
    region = region.get('reference', region)
    return region['path'], region['start_line'], region['end_line']


def _reject(stage, reason):
    return {'accepted': False, 'stage': stage, 'reason': reason, 'patch': None}


def apply_blocks(workspace, blocks, allowed_regions=None):
    root = workspace.registry.directory(workspace.case) / 'source'
    prefix = workspace.case['approved_prefix']
    spans = [_span(r) for r in allowed_regions] if allowed_regions is not None else None
    texts, spots = {}, []
    try:
        for path, search, replace in blocks:
            if not search.strip():
                return _reject('validate', 'SEARCH block is empty')
            path = _resolve(root, prefix, path, search, replace, spans)
            target = source_path(root, prefix, path)
            if not target.is_file():
                return _reject('validate', f'{path}: file does not exist')
            original = texts.setdefault(path, target.read_text())
            found = _locate(original, search, replace)
            if isinstance(found, str):
                return _reject('validate', f'{path}: SEARCH must match exactly once; {found}')
            start, stop, replace = found
            first, end = original.count('\n', 0, start) + 1, original.count('\n', 0, stop)
            if spans is not None and not any(p == path and a <= first and end <= b for p, a, b in spans):
                return _reject('validate', f'{path}: SEARCH at lines {first}-{end} is outside the captured regions')
            spots.append((path, start, stop, replace))
        patch = ''
        for path, original in texts.items():
            ranges = sorted(s[1:] for s in spots if s[0] == path)
            if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
                return _reject('validate', f'{path}: overlapping SEARCH blocks')
            changed = original
            for start, end, replace in reversed(ranges):
                changed = changed[:start] + replace + changed[end:]
            if changed == original:
                return _reject('validate', f'{path}: edit makes no change')
            try:
                ast.parse(changed, filename=path)
            except SyntaxError as error:
                return _reject('validate', f'{path}: syntax error at line {error.lineno}: {error.msg}')
            dangling = dangling_removals(root, path, original, changed)
            if dangling:
                return _reject('validate', f'{path}: removes names still referenced: ' + ', '.join(dangling))
            patch += ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                                  fromfile='a/' + path, tofile='b/' + path))
        workspace.propose(patch)  # approved prefix and scope gate
    except (ValueError, OSError, SyntaxError) as error:  # SyntaxError: an unparsable original snapshot
        return _reject('validate', type(error).__name__ + ': ' + str(error))
    return {'accepted': True, 'stage': 'validate', 'reason': None, 'patch': patch}
