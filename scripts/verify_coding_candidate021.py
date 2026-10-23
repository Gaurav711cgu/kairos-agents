"""Independently verify one development supervision target; never invoke a model.

Reference equivalence is checked before source acquisition or Docker inspection.
Checks use the existing fenced-output sandbox and durable unknown-dispatch guard.
The command never starts Docker, pulls images or expands evaluation access.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil

from scripts import qualify014 as q, qualify006
from scripts.coding_public100014 import dataset_rows
from scripts.coding_qualify014 import image_identity
from scripts.coding_candidate_policy021 import SOURCE_PREFIXES, CANDIDATE_ENVIRONMENTS
from scripts.coding_target_completeness021 import audit_row
from scripts.coding_data014 import patch_scope
from scripts.coding_verifier014 import qualifies
from scripts.coding_verifier021 import verifier
from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.sandbox import Workspace

VERSION = 'coding-development-candidates021-v1'


def selected(corpus, rows, identifier):
    if corpus.get('version') != VERSION or corpus.get('training_ready') is not False:
        raise ValueError('A separately versioned, non-training development candidate corpus is required')
    matches = [row for row in corpus.get('development', []) if row.get('instance_id') == identifier]
    if len(matches) != 1 or any(row.get('instance_id') == identifier for row in corpus.get('train', [])):
        raise ValueError('Select exactly one development candidate, never training/evaluation')
    candidate = matches[0]; raw = rows.get(identifier)
    if raw is None or (candidate['repository'], candidate['source_commit'], candidate['input']['issue']) != (raw['repo'], raw['base_commit'], raw['problem_statement']):
        raise ValueError('Development candidate differs from the pinned dataset')
    if not audit_row(candidate, raw['patch'])['complete_reference_equivalence']:
        raise ValueError('Candidate target differs from the complete reference transformation')
    patch_scope(raw['patch'])
    environment = CANDIDATE_ENVIRONMENTS.get((raw['repo'], raw['version']))
    if environment is None or raw['repo'] not in SOURCE_PREFIXES:
        raise ValueError('No reviewed environment for ' + raw['repo'] + ' version ' + raw['version'])
    return candidate, raw, environment


def captured_sources(workspace, candidate):
    sources = {}
    for block in candidate['input']['original_source']:
        capture = workspace.read_original(block['path'], block['start_line'], block['end_line'])
        if capture['text'] != block['numbered_original_source']:
            raise ValueError('Candidate excerpt differs from original-source bytes')
        # Historical source handles are bound to the exact digest-based excerpt.
        if block['source_id'] != 'S' + capture['reference']['excerpt_id'][:12]:
            raise ValueError('Candidate source handle differs from original authority')
        sources[block['source_id']] = capture['reference']
    return sources


def replay_completed(output, binding):
    final = output / 'receipt.json'
    if not final.exists(): return None
    receipt = q.load(final)
    if receipt.get('binding') != binding or receipt.get('model_calls') != 0:
        raise ValueError('Completed verification binding differs')
    captures = {}
    for stage in ('baseline', 'reference', 'candidate'):
        if q.sha(output / (stage + '.json')) != receipt['checks_sha256'][stage]:
            raise ValueError('Completed capture hash differs')
        captured = q.load(output / (stage + '.json'))
        if captured.get('binding') != binding or captured.get('stage') != stage:
            raise ValueError('Completed capture identity differs')
        captures[stage] = captured['result']
    if receipt['qualified'] != qualifies(captures['baseline'], captures['reference']) or receipt['candidate_verified'] != qualifies(captures['baseline'], captures['candidate']):
        raise ValueError('Completed qualification verdict differs')
    if q.sha(output / 'source-preservation.json') != receipt['source_preservation_sha256']:
        raise ValueError('Source preservation capture differs')
    return receipt


def execute(args):
    roots = q.budget_paths(args.budget_root); output = q.no_symlinks(args.output)
    if not q.covered(output, roots): raise ValueError('Output must belong to declared aggregate storage roots')
    corpus = q.load(args.corpus)
    candidate, raw, environment = selected(corpus, dataset_rows(args.dataset), args.task_id)
    image_doc = q.load(args.image_receipt)
    review = args.image_receipt.parent / 'review.json'
    if q.load(review).get('repository_version') != environment or image_doc.get('review_sha256') != q.sha(review):
        raise ValueError('Reviewed environment version differs before Docker access')
    identity = {'version': 'coding-candidate-verification021-v1', 'instance_id': args.task_id,
                'corpus_sha256': q.sha(args.corpus), 'dataset_sha256': q.sha(args.dataset),
                'image_receipt_sha256': q.sha(args.image_receipt), 'review_sha256': q.sha(review),
                'runner_sha256': q.sha(__file__), 'candidate_sha256': q.digest(candidate),
                'policy_sha256': q.sha(Path(__file__).with_name('coding_candidate_policy021.py')),
                'verifier_sha256': q.sha(Path(__file__).with_name('coding_verifier021.py')),
                'base_verifier_sha256': q.sha(Path(__file__).with_name('coding_verifier014.py')),
                'sandbox_sha256': q.sha(Path(__file__).resolve().parents[1] / 'kairos_api/investigations/sandbox.py'),
                'model_calls': 0}
    binding = q.digest(identity)
    previous = replay_completed(output, binding)
    if previous is not None: return previous
    q.storage_guard(roots)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    q.immutable(output / 'binding.json', identity)
    # Refuse an unresolved prior dispatch before downloading source or invoking Docker.
    for stage in ('baseline', 'reference', 'candidate'):
        if (output / (stage + '.started.json')).exists() and not (output / (stage + '.json')).exists():
            raise RuntimeError('Prior ' + stage + ' check has unknown dispatch; no automatic redispatch')
    image = image_identity(args.image_receipt, environment)
    original = dict(q.PREFIXES)
    try:
        q.PREFIXES.update(SOURCE_PREFIXES)
        source, source_receipt = q.pinned_source(raw, output, roots, args.allow_source_download, tree_hash)
    finally:
        q.PREFIXES.clear(); q.PREFIXES.update(original)
    if source_receipt['source_digest'] != candidate['source_digest']:
        raise ValueError('Candidate original source digest differs')
    size = q.tree_bytes(source)
    case_dir = output / 'registry/cases' / args.task_id
    case_dir.mkdir(parents=True, exist_ok=True)
    if source != case_dir / 'source': source.rename(case_dir / 'source')
    source = case_dir / 'source'
    archive = output / 'source.tar.gz'
    if archive.exists():
        if q.sha(archive) != source_receipt['archive_sha256']: raise ValueError('Source archive changed')
        archive.unlink()
    q.storage_guard(roots, size * 2 + q.CHECK_RESERVATION)
    script, scope = verifier(raw)
    case = {'id': args.task_id, 'dataset_instance_id': args.task_id, 'repository': raw['repo'],
            'revision': raw['base_commit'], 'issue': raw['problem_statement'], 'split': 'development',
            'qualified': False, 'approved_prefix': SOURCE_PREFIXES[raw['repo']],
            'entry_lines': patch_scope(raw['patch'])['paths'], 'command': ['python', '/verification/verify.py'],
            'image': image['id'], 'source_digest': source_receipt['source_digest'],
            'reference_digest': hashlib.sha256(raw['patch'].encode()).hexdigest(),
            'verification_digest': hashlib.sha256((raw['test_patch'] + script).encode()).hexdigest()}
    for name, value in [('reference.patch', raw['patch']), ('test.patch', raw['test_patch']), ('verify.py', script)]:
        path = case_dir / name
        if path.exists():
            if path.read_text() != value: raise ValueError('Private verifier material changed')
        else:
            with path.open('x') as stream: stream.write(value)
    q.immutable(output / 'registry.json', {'version': 'repository-cases-v1', 'cases': [case]})
    q.immutable(output / 'scope.json', scope)
    registry = CaseRegistry(output / 'registry.json', output / 'registry'); registry.verify(case)
    workspace = None; captures = {}
    with q.counted_temporary(output / 'temporary'):
        try:
            workspace = Workspace(registry, case)
            sources = captured_sources(workspace, candidate)
            captures['baseline'] = q.captured_check(output / 'baseline.json', 'baseline', lambda: workspace.checks(timeout=120), binding, roots, size)
            workspace.propose(raw['patch'])
            captures['reference'] = q.captured_check(output / 'reference.json', 'reference', lambda: workspace.checks(timeout=120), binding, roots, size)
            patch = workspace.propose_line_edits(candidate['assistant_target']['edits'], sources)
            q.immutable(output / 'candidate.patch.json', patch)
            captures['candidate'] = q.captured_check(output / 'candidate.json', 'candidate', lambda: workspace.checks(timeout=120), binding, roots, size)
        finally:
            if workspace is not None: workspace.close()
    registry.verify(case)
    preservation = {'source': source_receipt, 'source_unchanged': tree_hash(source) == candidate['source_digest'],
                    'original_tree_digest': candidate['source_digest'], 'scope': 'Owned reconstructed source only; verified before removal'}
    if not preservation['source_unchanged']: raise ValueError('Original source changed; preserve for inspection')
    q.immutable(output / 'source-preservation.json', preservation)
    receipt = {'version': identity['version'], 'instance_id': args.task_id, 'binding': binding, 'model_calls': 0,
               'qualified': qualifies(captures['baseline'], captures['reference']),
               'candidate_verified': qualifies(captures['baseline'], captures['candidate']), 'training_admitted': False,
               'image': image['id'], 'environment': environment,
               'checks_sha256': {stage: q.sha(output / (stage + '.json')) for stage in captures},
               'summaries': {stage: qualify006.summary(value) for stage, value in captures.items()},
               'source_preservation_sha256': q.sha(output / 'source-preservation.json')}
    q.immutable(output / 'receipt.json', receipt)
    shutil.rmtree(source)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True); parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--task-id', required=True); parser.add_argument('--image-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--budget-root', type=Path, action='append', required=True)
    parser.add_argument('--allow-source-download', action='store_true'); args = parser.parse_args()
    # One verifier owns this output; no shared global runtime or Docker lifecycle.
    output = q.no_symlinks(args.output)
    if not q.covered(output, args.budget_root): raise ValueError('Output must be inside declared storage roots')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (output / 'verifier.lock').open('a+b') as lock:
        try: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another verifier owns this output') from None
        print(json.dumps(execute(args), indent=2))

if __name__ == '__main__': main()
