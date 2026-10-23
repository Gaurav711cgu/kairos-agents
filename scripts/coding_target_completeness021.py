"""Completeness gates for source-edit supervision; no repository execution or training.

Reconstruct only original lines captured in reference hunks and source excerpts.
Unique placeholders stand for unseen unchanged lines. Apply both proposals to the
same sparse original and require identical resulting lines. This proves complete
reference-equivalent transformation, not that the reference repairs the defect.
When an original snapshot is available, audit_workspace uses the production
renderer and complete tree equality to handle legitimate Git hunk offsets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def safe_name(name):
    if not isinstance(name, str) or '\\' in name or PurePosixPath(name).is_absolute() or any(x in {'', '.', '..'} for x in name.split('/')):
        raise ValueError('Unsafe source path')
    return name


def parse_patch(patch):
    files = {}; path = None; lines = patch.splitlines(keepends=True); i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('--- a/'):
            path = safe_name(line[6:].rstrip('\r\n')); files.setdefault(path, [])
        elif line.startswith('@@ '):
            if path is None: raise ValueError('Hunk without source path')
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not match: raise ValueError('Malformed hunk')
            start, count, _, new_count = match.groups(); count = int(count or 1); new_count = int(new_count or 1)
            before = []; after = []; i += 1
            while i < len(lines) and not lines[i].startswith(('@@ ', 'diff --git ', '--- a/')):
                part = lines[i]
                if part.startswith('\\ No newline'):
                    previous = lines[i - 1][:1]
                    if previous in {' ', '-'} and before: before[-1] = before[-1].removesuffix('\n')
                    if previous in {' ', '+'} and after: after[-1] = after[-1].removesuffix('\n')
                elif part.startswith(' '): before.append(part[1:]); after.append(part[1:])
                elif part.startswith('-'): before.append(part[1:])
                elif part.startswith('+'): after.append(part[1:])
                else: break
                i += 1
            if (len(before), len(after)) != (count, new_count): raise ValueError('Hunk counts differ')
            # A zero-length hunk inserts after the stated original line.
            offset = int(start) if count == 0 else int(start) - 1
            files[path].append((offset, before, after)); continue
        elif line.startswith(('GIT binary patch', 'Binary files ', '--- /dev/null', 'rename from ')):
            raise ValueError('Unsupported source transformation')
        i += 1
    if not files or not any(files.values()): raise ValueError('Missing source hunks')
    return files


def apply(original, edits):
    cursor = 0; output = []
    for start, before, after in sorted(edits, key=lambda e: e[0]):
        if start < cursor or start < 0 or original[start:start + len(before)] != before:
            raise ValueError('Overlapping edit or original-source mismatch')
        output.extend(original[cursor:start]); output.extend(after); cursor = start + len(before)
    output.extend(original[cursor:]); return output


def audit_row(row, reference_patch):
    reference = parse_patch(reference_patch); blocks = {}; known = {}; changes = {}
    def bind(path, start, values):
        if start < 0: raise ValueError('Invalid source bounds')
        for offset, value in enumerate(values, start):
            key = (path, offset)
            if key in known and known[key] != value: raise ValueError('Conflicting original-source bytes')
            known[key] = value
    for block in row['input']['original_source']:
        path = safe_name(block['path']); start = block['start_line']; end = block['end_line']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end: raise ValueError('Invalid excerpt bounds')
        content = block['numbered_original_source'].splitlines(keepends=True)
        if len(content) != end - start + 1: raise ValueError('Excerpt length differs')
        values = []
        for number, line in enumerate(content, start):
            prefix = f'{number}: '
            if not line.startswith(prefix): raise ValueError('Numbered source differs')
            values.append(line[len(prefix):])
        handle = block['source_id']
        if handle in blocks: raise ValueError('Duplicate handle')
        blocks[handle] = (path, start, end); bind(path, start - 1, values)
    action = row['assistant_target']
    if set(action) != {'action', 'edits'} or action['action'] != 'propose_patch' or not action['edits']: raise ValueError('Invalid action')
    for edit in action['edits']:
        if set(edit) != {'source_id', 'start_line', 'end_line', 'new'}: raise ValueError('Invalid edit fields')
        if edit['source_id'] not in blocks: raise ValueError('Unknown source handle')
        path, low, high = blocks[edit['source_id']]; start = edit['start_line']; end = edit['end_line']
        if type(start) is not int or type(end) is not int or not low <= start <= end <= high or not isinstance(edit['new'], str): raise ValueError('Edit outside captured authority')
        before = [known[path, n] for n in range(start - 1, end)]
        changes.setdefault(path, []).append((start - 1, before, edit['new'].splitlines(keepends=True)))
    for path, hunks in reference.items():
        for start, before, _ in hunks: bind(path, start, before)
    differing = []
    for path in sorted(reference.keys() | changes.keys()):
        length = max([n + 1 for p, n in known if p == path] + [0])
        original = [known.get((path, n), f'\0UNOBSERVED:{path}:{n}\0\n') for n in range(length)]
        expected = apply(original, reference.get(path, [])); actual = apply(original, changes.get(path, []))
        if expected != actual: differing.append(path)
    return {'instance_id': row['instance_id'], 'complete_reference_equivalence': not differing,
            'differing_paths': differing, 'independent_repair_reproduced': False}


def audit_workspace(row, reference_patch, workspace):
    """Compare complete disposable trees when Git legitimately shifts a hunk."""
    from kairos_api.investigations.registry import tree_hash
    from kairos_api.investigations.contracts import ActionV7
    workspace.registry.verify(workspace.case)
    original = workspace.registry.directory(workspace.case) / 'source'
    identity = (workspace.case.get('repository'), workspace.case.get('revision'))
    if identity != (row['repository'], row['source_commit']) or tree_hash(original) != row['source_digest']:
        raise ValueError('Original snapshot identity differs')
    action = row['assistant_target']
    ActionV7.validate_python(action)
    if action.get('action') != 'propose_patch':
        raise ValueError('A source-edit target is required')
    sources = {}
    for block in row['input']['original_source']:
        capture = workspace.read_original(block['path'], block['start_line'], block['end_line'])
        handle = 'S' + capture['reference']['excerpt_id'][:12]
        if capture['text'] != block['numbered_original_source'] or handle != block['source_id'] or handle in sources:
            raise ValueError('Original captured source authority differs')
        sources[handle] = capture['reference']
    try:
        workspace.propose(reference_patch)
        expected = tree_hash(workspace.root)
        workspace.propose_line_edits(action['edits'], sources)
        actual = tree_hash(workspace.root)
        return {'instance_id': row['instance_id'], 'complete_reference_equivalence': expected == actual,
                'method': 'complete-original-snapshot-production-renderer-v1',
                'reference_tree_digest': expected, 'target_tree_digest': actual,
                'independent_repair_reproduced': False}
    finally:
        workspace.registry.verify(workspace.case)
        if tree_hash(original) != row['source_digest']:
            raise ValueError('Original source changed during snapshot audit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-zip', type=Path, required=True); parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    import pyarrow.parquet as pq
    with zipfile.ZipFile(args.input_zip) as archive: corpus = json.loads(archive.read('data/corpus.json'))
    dataset = {row['instance_id']: row['patch'] for row in pq.read_table(args.dataset, columns=['instance_id', 'patch']).to_pylist()}
    results = []
    for split in ('train', 'development'):
        for row in corpus[split]:
            try: result = audit_row(row, dataset[row['instance_id']])
            except (ValueError, KeyError, TypeError) as error:
                result = {'instance_id': row['instance_id'], 'complete_reference_equivalence': False, 'error': str(error)}
            results.append({'split': split, **result})
    report = {'version': 'training-target-completeness020-v1', 'input_zip_sha256': hashlib.file_digest(args.input_zip.open('rb'), 'sha256').hexdigest(),
              'dataset_sha256': hashlib.file_digest(args.dataset.open('rb'), 'sha256').hexdigest(), 'results': results,
              'scope': 'Reference-equivalent edits only. No independent repair execution, training or inference.'}
    report['counts'] = {split: {'total': sum(r['split'] == split for r in results), 'complete': sum(r['split'] == split and r['complete_reference_equivalence'] for r in results)} for split in ('train', 'development')}
    # Exclusive creation preserves earlier audit evidence.
    with args.output.open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report['counts']))
    return 0 if all(r['complete_reference_equivalence'] for r in results) else 1

if __name__ == '__main__': raise SystemExit(main())
