"""F025 scoring: the recorded patch is never trusted; the reply is re-applied to the pinned source."""
import difflib
import hashlib
import json
import sys
import types
from contextlib import nullcontext

import pytest

import scripts.f025_score as score
import scripts.qualify014 as q
from scripts.f024_colab import digest

CASE_ID = 'd-1'
CHAIN = f'dev/{CASE_ID}/oracle'
SRC_FILE = 'a.py'
ORIGINAL = 'x = 1\n'
REPLY = f'{SRC_FILE}\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n'
PATCH = ''.join(difflib.unified_diff(ORIGINAL.splitlines(True), ['x = 2\n'], fromfile='a/' + SRC_FILE, tofile='b/' + SRC_FILE))
REGIONS = [{'path': SRC_FILE, 'start_line': 1, 'end_line': 1}]


def tree_hash(root):
    return hashlib.sha256(b''.join(p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file())).hexdigest()


class FakeRegistry:
    def __init__(self, path, base):
        self.base = base

    def directory(self, case):
        return self.base / 'cases' / case['id']


def chain(chain_id=CHAIN, status='accepted', reply=REPLY, patch=PATCH, regions=REGIONS, receipts=b''):
    record = {'chain_id': chain_id, 'status': status, 'calls': 1, 'final_reply': reply, 'patch': patch,
              'regions': regions, 'receipts_sha256': hashlib.sha256(receipts).hexdigest()}
    return {**record, 'record_sha256': digest(record)}


def write(results, record, receipts=None):
    path = results / 'chains' / (record['chain_id'] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))
    if receipts is not None:
        path = results / 'receipts' / (record['chain_id'] + '.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(receipts)


def bind(records, shipped_regions=None):
    """Bind records to the package they claim; a record whose hash was already wrong stays wrong."""
    package = {'chains': [{'chain_id': r['chain_id'], 'regions': shipped_regions or r['regions']} for r, _ in records]}
    for record, _ in records:
        valid = digest({k: v for k, v in record.items() if k != 'record_sha256'}) == record['record_sha256']
        record['binding'] = digest(package)
        if valid:
            record['record_sha256'] = digest({k: v for k, v in record.items() if k != 'record_sha256'})
    return package


def setup_main(tmp_path, monkeypatch, records, execute=True, qualified=True, shipped_regions=None):
    pq = pytest.importorskip('pyarrow.parquet', reason='pyarrow is research tooling, not in requirements-reviewer.lock')
    row = {'instance_id': CASE_ID, 'repo': 'r/r', 'patch': 'P', 'test_patch': 'T', 'base_commit': 'c',
           'FAIL_TO_PASS': ['x'], 'PASS_TO_PASS': []}
    state = {'pinned': 0, 'checks': 0}
    case = {'id': CASE_ID, 'approved_prefix': '', 'source_digest': hashlib.sha256(ORIGINAL.encode()).hexdigest(),
            'verification_digest': hashlib.sha256(b'TSCRIPT').hexdigest()}
    qualifier = types.SimpleNamespace(verifier=lambda r, s: ('SCRIPT', None))
    monkeypatch.setattr(pq, 'read_table', lambda p: types.SimpleNamespace(to_pylist=lambda: [row]))
    monkeypatch.setattr(q, 'dependencies', lambda project: (qualifier, FakeRegistry, tree_hash, None))
    monkeypatch.setattr(q, 'inspect_images', lambda repos: {})

    def pinned_source(r, directory, roots, allow, th):
        state['pinned'] += 1
        (directory / 'source').mkdir()
        (directory / 'source' / SRC_FILE).write_text(ORIGINAL)
        return directory / 'source', {}
    monkeypatch.setattr(q, 'pinned_source', pinned_source)
    monkeypatch.setattr(q, 'captured_check', lambda path, stage, run, *a: run())
    monkeypatch.setattr(q, 'check_qualified', lambda b, c, qual: {'qualified': qualified, 'status': 'fails'})
    monkeypatch.setattr(q, 'load', lambda p: {'result': {}})
    monkeypatch.setattr(q, 'counted_temporary', lambda root: nullcontext())

    class FakeWorkspace:
        def __init__(self, registry, c):
            self.registry, self.case, self.root = registry, c, tmp_path / 'wsroot'
            self.root.mkdir(exist_ok=True)

        def propose(self, patch):
            state['proposed'] = patch

        def checks(self, timeout):
            state['checks'] += 1
            return {'passed': True}

        def close(self):
            pass
    import kairos_api.investigations.sandbox as sandbox
    monkeypatch.setattr(sandbox, 'Workspace', FakeWorkspace)
    package = bind(records, shipped_regions)
    (tmp_path / 'package.json').write_text(json.dumps(package))
    results = tmp_path / 'res'
    results.mkdir()
    for record, receipts in records:
        write(results, record, b'' if receipts is None else receipts)
    qual = tmp_path / 'qual'
    qual.mkdir()
    (qual / 'binding.json').write_text(json.dumps({'binding': {'b': 1}}))
    roots = tmp_path / 'roots.json'
    roots.write_text(json.dumps({'roots': []}))
    adm = tmp_path / 'adm.py'
    adm.write_text(f"def admit_receipt(qual, ident, binding, qualifier):\n    return {{'case': {case!r}}}\n")
    out = tmp_path / 'out'
    argv = ['f025_score', '--results', str(results), '--package', str(tmp_path / 'package.json'), '--qualification', str(qual), '--parquet', str(tmp_path / 'p.parquet'),
            '--storage-roots', str(roots), '--output', str(out), '--admission-module', str(adm)] + (['--execute'] if execute else [])
    monkeypatch.setattr(sys, 'argv', argv)
    return out, state


def scored(out):
    scores = json.loads((out / 'scores.json').read_text())
    return scores, {r['chain_id']: r for r in scores['results']}


def test_happy_path_reaches_verified_repair_and_skips_synthetic(tmp_path, monkeypatch):
    out, state = setup_main(tmp_path, monkeypatch, [(chain(receipts=b'{"kind": "accepted"}\n'), b'{"kind": "accepted"}\n'), (chain('synthetic/t-1'), None)])
    score.main()
    scores, got = scored(out)
    assert got[CHAIN]['outcome'] == 'verified_repair' and got[CHAIN]['verified_repair']
    assert scores == {**scores, 'model_calls': 0, 'verified_repairs': 1, 'attempts': 1, 'skipped_synthetic': ['synthetic/t-1']}
    assert state['proposed'] == PATCH and state['checks'] == 1 and state['pinned'] == 1


def test_unqualified_check_keeps_its_status(tmp_path, monkeypatch):
    out, _ = setup_main(tmp_path, monkeypatch, [(chain(), None)], qualified=False)
    score.main()
    assert scored(out)[1][CHAIN] == {**scored(out)[1][CHAIN], 'outcome': 'fails', 'verified_repair': False}


@pytest.mark.parametrize('status', ['exhausted', 'repeated', 'envelope'])
def test_non_accepted_chain_is_a_loop_outcome_without_docker(tmp_path, monkeypatch, status):
    out, state = setup_main(tmp_path, monkeypatch, [(chain(status=status, patch=None), None)])
    score.main()
    assert scored(out)[1][CHAIN]['outcome'] == 'loop_' + status and state['checks'] == 0


def test_reply_rejected_on_real_source_is_revalidation_rejected(tmp_path, monkeypatch):
    reply = REPLY.replace('x = 1\n=', 'y = 9\n=')  # SEARCH no longer matches the pinned source
    out, state = setup_main(tmp_path, monkeypatch, [(chain(reply=reply), None)])
    score.main()
    result = scored(out)[1][CHAIN]
    assert result['outcome'] == 'revalidation_rejected' and 'exactly once' in result['reason'] and state['checks'] == 0


def test_reply_outside_recorded_regions_is_rejected(tmp_path, monkeypatch):
    out, _ = setup_main(tmp_path, monkeypatch, [(chain(regions=[{'path': SRC_FILE, 'start_line': 5, 'end_line': 9}]), None)])
    score.main()
    assert 'outside the captured regions' in scored(out)[1][CHAIN]['reason']


def test_recorded_patch_differing_from_rederived_is_patch_mismatch(tmp_path, monkeypatch):
    out, state = setup_main(tmp_path, monkeypatch, [(chain(patch=PATCH.replace('x = 2', 'x = 3')), None)])
    score.main()
    assert scored(out)[1][CHAIN]['outcome'] == 'patch_mismatch' and not scored(out)[1][CHAIN]['verified_repair'] and state['checks'] == 0


def test_tampered_record_is_refused(tmp_path, monkeypatch):
    record = {**chain(), 'status': 'accepted', 'patch': 'forged'}
    record['final_reply'] += ' '
    setup_main(tmp_path, monkeypatch, [(record, None)])
    with pytest.raises(ValueError, match='record_sha256'):
        score.main()


def test_tampered_receipts_are_refused(tmp_path, monkeypatch):
    setup_main(tmp_path, monkeypatch, [(chain(receipts=b'{"kind": "accepted"}\n'), b'edited\n')])
    with pytest.raises(ValueError, match='receipts_sha256'):
        score.main()


def test_without_execute_only_the_plan_is_printed(tmp_path, monkeypatch, capsys):
    out, state = setup_main(tmp_path, monkeypatch, [(chain(), None), (chain('synthetic/t-1'), None)], execute=False)
    score.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan == {'status': 'prepared_not_executed', 'chains': {CHAIN: 'accepted'}, 'skipped_synthetic': ['synthetic/t-1']}
    assert not out.exists() and state['pinned'] == 0


def test_regions_differing_from_the_shipped_package_are_refused(tmp_path, monkeypatch):
    wide = [{'path': SRC_FILE, 'start_line': 1, 'end_line': 9}]
    setup_main(tmp_path, monkeypatch, [(chain(), None)], shipped_regions=wide)
    with pytest.raises(ValueError, match='shipped package'):
        score.main()


def test_record_from_another_package_is_refused(tmp_path, monkeypatch):
    record = chain()
    setup_main(tmp_path, monkeypatch, [(record, None)])
    record['binding'] = '0' * 64
    record['record_sha256'] = digest({k: v for k, v in record.items() if k != 'record_sha256'})
    write(tmp_path / 'res', record)
    with pytest.raises(ValueError, match='shipped package'):
        score.main()


def test_driver_output_loads_in_the_scorer(tmp_path):
    from scripts.f025_colab import build_package, run_chains
    from scripts.f025_tasks import TASKS
    package = build_package(TASKS)
    by_issue = {t['issue']: t['reference'] for t in TASKS}  # author fixes: infrastructure control, not model output
    generate = lambda messages, index, sampling=None: {'text': next(r for i, r in by_issue.items() if i in messages[1]['content'])}
    summary = run_chains(package, tmp_path / 'out', generate, count_tokens=lambda m: 0, host_checks=True)
    chains, synthetic = score.load_chains([tmp_path / 'out'], package)
    assert summary['synthetic_check_passed'] == 6 and summary['calls'] == 6
    assert chains == {} and synthetic == sorted('synthetic/' + t['task_id'] for t in TASKS)


def test_edit_in_a_read_widened_region_is_scored(tmp_path, monkeypatch):
    record = chain(regions=[{'path': SRC_FILE, 'start_line': 5, 'end_line': 9}])
    record['read_regions'] = REGIONS
    record['record_sha256'] = digest({k: v for k, v in record.items() if k != 'record_sha256'})
    out, state = setup_main(tmp_path, monkeypatch, [(record, None)])
    score.main()
    assert scored(out)[1][CHAIN]['outcome'] == 'verified_repair' and state['checks'] == 1


def test_missing_receipts_are_refused(tmp_path, monkeypatch):
    setup_main(tmp_path, monkeypatch, [(chain(), None)])
    (tmp_path / 'res' / 'receipts' / (CHAIN + '.jsonl')).unlink()
    with pytest.raises(ValueError, match='receipts_sha256'):
        score.main()


def test_dev_chain_without_a_record_counts_as_not_run():
    package = {'chains': [{'chain_id': CHAIN, 'regions': REGIONS}]}
    chains, _ = score.load_chains([], package)
    assert chains == {CHAIN: {'chain_id': CHAIN, 'status': 'not_run'}}


def test_pass_at_2_and_fair_pick():
    s0, s1 = 'dev/d-1/oracle-s0', 'dev/d-1/oracle-s1'
    results = [{'chain_id': s0, 'verified_repair': False}, {'chain_id': s1, 'verified_repair': True}]
    chains = {s0: {'status': 'accepted', 'last_run_exit': 0}, s1: {'status': 'accepted', 'last_run_exit': 0}}
    summary = score.summarize(results, chains)
    assert summary['pass_at_2'] == 1 and summary['pass_at_2_label'] == 'oracle_selection'
    assert summary['fair_pick'] == {'d-1': {'sample': 0, 'verified': False}} and summary['fair_pick_verified'] == 0


def test_fair_pick_skips_samples_whose_repro_failed():
    s0, s1 = 'dev/d-1/oracle-s0', 'dev/d-1/oracle-s1'
    results = [{'chain_id': s0, 'verified_repair': False}, {'chain_id': s1, 'verified_repair': True}]
    chains = {s0: {'status': 'accepted', 'last_run_exit': 1}, s1: {'status': 'accepted', 'last_run_exit': None}}
    assert score.summarize(results, chains)['fair_pick'] == {'d-1': {'sample': 1, 'verified': True}}


def test_missing_sample_counts_not_run():
    package = {'chains': [{'chain_id': 'dev/d-1/oracle-s0', 'regions': REGIONS}, {'chain_id': 'dev/d-1/oracle-s1', 'regions': REGIONS}]}
    chains, _ = score.load_chains([], package)
    assert {k: v['status'] for k, v in chains.items()} == {'dev/d-1/oracle-s0': 'not_run', 'dev/d-1/oracle-s1': 'not_run'}


def test_last_run_exit_is_read_from_receipts(tmp_path):
    receipts = b'{"kind": "run", "feedback": "RUN exit 3:\\nboom"}\n{"kind": "accepted", "feedback": null}\n'
    record = chain(receipts=receipts)
    package = bind([(record, None)])
    write(tmp_path, record, receipts)
    chains, _ = score.load_chains([tmp_path], package)
    assert chains[CHAIN]['last_run_exit'] == 3


def test_timed_out_repro_is_not_treated_as_no_repro(tmp_path):
    receipts = (json.dumps({'kind': 'run', 'feedback': 'RUN timed out after 30s:\n'}) + '\n' + json.dumps({'kind': 'accepted', 'feedback': None}) + '\n').encode()
    record = chain(receipts=receipts)
    package = bind([(record, None)])
    write(tmp_path, record, receipts)
    chains, _ = score.load_chains([tmp_path], package)
    assert chains[CHAIN]['last_run_exit'] == 'no_exit'
    s0, s1 = 'dev/d-1/oracle-s0', 'dev/d-1/oracle-s1'
    picked = score.summarize([], {s0: {'status': 'accepted', 'last_run_exit': 'no_exit'}, s1: {'status': 'accepted', 'last_run_exit': 0}})
    assert picked['fair_pick'] == {'d-1': {'sample': 1, 'verified': False}}


def test_revalidation_uses_the_reply_that_made_the_patch(tmp_path):
    import hashlib
    from scripts.f025_score import patch_reply
    edit, done = 'django/x.py\n<<<<<<< SEARCH\na\n=======\nb\n>>>>>>> REPLACE\n', 'DONE'
    for n, text in enumerate([edit, done]):
        (tmp_path / 'captures/dev/c/oracle').mkdir(parents=True, exist_ok=True)
        (tmp_path / f'captures/dev/c/oracle/c{n}.json').write_text(json.dumps({'result': {'text': text}}))
    entries = [{'kind': 'self_test'}, {'kind': 'accepted', 'reply_sha256': hashlib.sha256(edit.encode()).hexdigest()}]
    assert patch_reply(tmp_path, 'dev/c/oracle', entries, {'final_reply': done}) == edit
    assert patch_reply(tmp_path, 'dev/c/oracle', [{'kind': 'accepted', 'reply_sha256': 'f' * 64}], {'final_reply': done}) == done
