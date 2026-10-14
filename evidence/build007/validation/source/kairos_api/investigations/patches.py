"""Validate and apply source-only unified patches in disposable directories."""
from pathlib import Path, PurePosixPath
import re
import subprocess


def source_path(root, prefix, name):
    path = PurePosixPath(name)
    if (not name.startswith(prefix) or path.is_absolute() or '..' in path.parts or
        any(part.startswith('.') or part in {'tests', '__pycache__', 'node_modules'} for part in path.parts) or
        '\\' in name or not name.endswith('.py') or Path(name).name.startswith('test_')):
        raise ValueError('Path is outside approved source files')
    candidate = root.joinpath(*path.parts)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError('Source path escapes snapshot')
    current = candidate
    while current != root:
        if current.is_symlink():
            raise ValueError('Symlink source paths are forbidden')
        current = current.parent
    return candidate


def apply_patch(root, prefix, patch):
    if len(patch.encode()) > 24000 or '\x00' in patch:
        raise ValueError('Patch exceeds capture budget')
    if re.search(r'^(?:rename |copy |old mode |new mode |new file mode (?!100644)|deleted file mode|GIT binary|Binary files)', patch, re.M):
        raise ValueError('Only ordinary source text patches are accepted')
    headers = re.findall(r'^(?:---|\+\+\+) (.+)$', patch, re.M)
    if not headers or len(headers) % 2:
        raise ValueError('Unified diff headers required')
    for name in headers:
        if name == '/dev/null':
            continue
        if not re.fullmatch(r'[ab]/[A-Za-z0-9_./-]+', name):
            raise ValueError('Invalid patch path')
        source_path(root, prefix, name[2:])
    stat = subprocess.run(['git', 'apply', '--numstat', '-'], cwd=root, input=patch, text=True, capture_output=True, timeout=5)
    if stat.returncode:
        raise ValueError('Malformed unified diff: '+stat.stderr[:500])
    rows = [line.split('\t') for line in stat.stdout.splitlines()]
    if not rows or len(rows)>3 or any(len(row)!=3 or not row[0].isdigit() or not row[1].isdigit() for row in rows):
        raise ValueError('Patch must change one to three text files')
    if sum(int(r[0])+int(r[1]) for r in rows)>200:
        raise ValueError('Patch exceeds 200 changed lines')
    for row in rows:
        source_path(root, prefix, row[2])
    for command in [['git','apply','--check','-'],['git','apply','-']]:
        result = subprocess.run(command,cwd=root,input=patch,text=True,capture_output=True,timeout=5)
        if result.returncode:
            raise ValueError('Patch does not apply to original snapshot: '+result.stderr[:700])
    return {'files':[r[2] for r in rows], 'added':sum(int(r[0]) for r in rows), 'removed':sum(int(r[1]) for r in rows)}
