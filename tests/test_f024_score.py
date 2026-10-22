"""Which capture is scored per (case, context, arm): the last turn, never both."""
from scripts.f024_score import final_attempts


def job(i, ctx, arm, turn):
    return {'job_id': f'{i}/{ctx}/{arm}/t{turn}', 'instance_id': i, 'context': ctx, 'arm': arm, 'turn': turn}


def test_last_turn_is_scored_and_missing_captures_are_reported():
    jobs = [job('d-1', 'issue', 'base', 1), job('d-1', 'issue', 'base', 2), job('d-1', 'issue', 'adapter', 1), job('d-1', 'oracle', 'base', 1)]
    captures = {'d-1/issue/base/t1': {'status': 'captured'}, 'd-1/issue/base/t2': {'status': 'captured'},
                'd-1/issue/adapter/t1': {'status': 'captured'}}
    plan = final_attempts(jobs, captures)
    assert plan == {('d-1', 'issue', 'base'): ('d-1/issue/base/t2', 'captured'),
                    ('d-1', 'issue', 'adapter'): ('d-1/issue/adapter/t1', 'captured'),
                    ('d-1', 'oracle', 'base'): ('d-1/oracle/base/t1', 'not_captured')}


# ---- main(--execute) end to end, offline: qualify014/Docker/Workspace/validator stubbed ----
import hashlib
import json
import sys
import types

import pytest

import scripts.f024_score as score
import scripts.qualify014 as q

CASE_ID = 'd-1'
SRC_FILE = 'a.py'


def tree_hash(root):
    return hashlib.sha256(b''.join(p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file())).hexdigest()


class FakeRegistry:
    def __init__(self, path, base):
        self.base = base


def setup_main(tmp_path, monkeypatch, texts, bad_case=False, mutate=False, qualified=True):
    """texts: job_id -> capture dict. Returns (argv-run callable, state)."""
    # Research-only dependency (SWE-bench parquet); absent from the locked reviewer environment.
    pq = pytest.importorskip('pyarrow.parquet', reason='pyarrow is research tooling, not in requirements-reviewer.lock')
    row = {'instance_id': CASE_ID, 'repo': 'r/r', 'patch': 'P', 'test_patch': 'T', 'base_commit': 'c',
           'FAIL_TO_PASS': ['x'], 'PASS_TO_PASS': []}
    state = {'pinned': 0, 'mutate': mutate}
    src_digest = hashlib.sha256(b'orig').hexdigest()
    case = {'id': CASE_ID, 'source_digest': src_digest,
            'verification_digest': hashlib.sha256(b'TSCRIPT').hexdigest()}
    qualifier = types.SimpleNamespace(verifier=lambda r, s: ('SCRIPT', None))
    monkeypatch.setattr(pq, 'read_table', lambda p: types.SimpleNamespace(to_pylist=lambda: [row]))
    monkeypatch.setattr(q, 'dependencies', lambda project: (qualifier, FakeRegistry, tree_hash, None))
    monkeypatch.setattr(q, 'inspect_images', lambda repos: {})

    def pinned_source(r, directory, roots, allow, th):
        state['pinned'] += 1
        (directory / 'source').mkdir()
        (directory / 'source' / SRC_FILE).write_bytes(b'orig')
        return directory / 'source', {}
    monkeypatch.setattr(q, 'pinned_source', pinned_source)
    monkeypatch.setattr(q, 'captured_check', lambda path, stage, run, *a: run())
    monkeypatch.setattr(q, 'check_qualified', lambda b, c, qual: {'qualified': qualified, 'status': 'fails'})
    monkeypatch.setattr(q, 'load', lambda p: {'result': {}})
    from contextlib import nullcontext
    monkeypatch.setattr(q, 'counted_temporary', lambda root: nullcontext())

    class FakeWorkspace:
        def __init__(self, registry, c):
            self.registry, self.root = registry, tmp_path / 'wsroot'
            self.root.mkdir(exist_ok=True)

        def read_original(self, path, start, end):
            return {'path': path}

        def checks(self, timeout):
            if state['mutate']:
                (self.registry.base / 'cases' / CASE_ID / 'source' / SRC_FILE).write_bytes(b'mutated')
            return {'passed': True}

        def close(self):
            pass
    import kairos_api.investigations.sandbox as sandbox
    import scripts.feedback_turn021 as fb
    monkeypatch.setattr(sandbox, 'Workspace', FakeWorkspace)

    def validate(ws, text, regions):
        if text == 'ok':
            return {'accepted': True, 'action': {}}
        if text == 'bad':
            return {'accepted': False, 'stage': 'parse', 'reason': 'no edit block'}
        return {'accepted': False, 'stage': 'validate', 'reason': 'syntax rejected: indent'}
    monkeypatch.setattr(fb, 'validate021', validate)

    def job(ctx, arm, turn):
        return {'job_id': f'{CASE_ID}/{ctx}/{arm}/t{turn}', 'instance_id': CASE_ID, 'context': ctx, 'arm': arm, 'turn': turn,
                'messages': [{}, {'content': json.dumps({'original_source': [{'path': SRC_FILE, 'start_line': 1, 'end_line': 1}]})}]}
    jobs = [job('issue', 'base', 1), job('issue', 'base', 2), job('issue', 'adapter', 1), job('oracle', 'base', 1),
            job('oracle', 'adapter', 1), job('issue', 'adapter', 2)]
    package = tmp_path / 'pkg.json'
    package.write_text(json.dumps({'jobs': jobs}))
    results = tmp_path / 'res'
    (results / 'captures').mkdir(parents=True)
    for job_id, cap in texts.items():
        (results / 'captures' / (job_id.replace('/', '__') + '.json')).write_text(json.dumps({'job_id': job_id, **cap}))
    qual = tmp_path / 'qual'
    qual.mkdir()
    (qual / 'binding.json').write_text(json.dumps({'binding': {'b': 1}}))
    roots = tmp_path / 'roots.json'
    roots.write_text(json.dumps({'roots': []}))
    adm = tmp_path / 'adm.py'
    adm.write_text('def admit_receipt(qual, ident, binding, qualifier):\n'
                   + ("    raise ValueError('hash mismatch')\n" if bad_case else f"    return {{'case': {case!r}}}\n"))
    out = tmp_path / 'out'
    argv = ['f024_score', '--package', str(package), '--results', str(results), '--qualification', str(qual),
            '--parquet', str(tmp_path / 'p.parquet'), '--storage-roots', str(roots), '--output', str(out),
            '--admission-module', str(adm), '--execute']
    monkeypatch.setattr(sys, 'argv', argv)
    return out, state


def cap(text, status='captured'):
    return {'status': status, 'result': {'text': text}}


def test_execute_scores_last_turn_only_with_expected_classes(tmp_path, monkeypatch):
    out, state = setup_main(tmp_path, monkeypatch, {
        'd-1/issue/base/t1': cap('ok'), 'd-1/issue/base/t2': cap('bad'),       # t1 ok must be ignored
        'd-1/issue/adapter/t1': cap('x'), 'd-1/issue/adapter/t2': cap('ok'),
        'd-1/oracle/base/t1': cap('', 'generation_error')})                    # oracle adapter not captured
    score.main()
    scores = json.loads((out / 'scores.json').read_text())
    got = {r['job_id']: r for r in scores['results']}
    assert set(got) == {'d-1/issue/base/t2', 'd-1/issue/adapter/t2', 'd-1/oracle/base/t1', 'd-1/oracle/adapter/t1'}
    assert got['d-1/issue/base/t2']['outcome'] == 'parse'
    assert got['d-1/issue/adapter/t2']['outcome'] == 'verified_repair' and got['d-1/issue/adapter/t2']['verified_repair']
    assert got['d-1/oracle/base/t1']['outcome'] == 'generation_error'
    assert got['d-1/oracle/adapter/t1']['outcome'] == 'not_captured'
    assert scores['verified_repairs'] == 1 and scores['attempts'] == 4 and scores['model_calls'] == 0
    assert state['pinned'] == 1  # one download per case, shared by attempts


def test_execute_rejected_validator_class_and_unqualified_status(tmp_path, monkeypatch):
    out, _ = setup_main(tmp_path, monkeypatch, {'d-1/issue/base/t2': cap('x'), 'd-1/issue/adapter/t2': cap('ok')}, qualified=False)
    score.main()
    got = {r['job_id']: r for r in json.loads((out / 'scores.json').read_text())['results']}
    assert got['d-1/issue/base/t2']['outcome'] == 'syntax_indentation'
    assert got['d-1/issue/adapter/t2'] == {**got['d-1/issue/adapter/t2'], 'outcome': 'fails', 'verified_repair': False}


def test_execute_unqualified_case_scores_nothing_and_never_downloads(tmp_path, monkeypatch):
    out, state = setup_main(tmp_path, monkeypatch, {'d-1/issue/base/t2': cap('ok')}, bad_case=True)
    score.main()
    results = json.loads((out / 'scores.json').read_text())['results']
    assert {r['outcome'] for r in results} == {'case_not_qualified'} and all(r['reason'] == 'hash mismatch' for r in results)
    assert state['pinned'] == 0


def test_scores_json_is_immutable_on_rerun(tmp_path, monkeypatch):
    out, _ = setup_main(tmp_path, monkeypatch, {'d-1/issue/base/t2': cap('ok')})
    score.main()
    before = (out / 'scores.json').read_bytes()
    with pytest.raises(FileExistsError):  # work/<case> already exists: refuses to rescore into the same output
        score.main()
    assert (out / 'scores.json').read_bytes() == before


def test_source_mutation_during_scoring_raises(tmp_path, monkeypatch):
    out, _ = setup_main(tmp_path, monkeypatch, {'d-1/issue/base/t2': cap('ok')}, mutate=True)
    with pytest.raises(ValueError, match='Original source changed'):
        score.main()
    assert not (out / 'scores.json').exists()
