"""Offline end-to-end acceptance: v8 job, ranked localization, scripted model, mocked checks."""
import json

import pytest

from kairos_api.investigations.model import LocalInvestigator
from test_study012 import study  # noqa: F401  (fixture)
from test_context_v5 import MemoryRepository, tokenizer  # noqa: F401  (fixture)
from test_unresolved_registry010 import registered  # noqa: F401  (fixture)
from test_retrieval_admission012 import job
from test_worker_localization024 import workspace_for, RankedWorkspace024


class Checked(RankedWorkspace024):
    """Checks are mocked: the verdict is scripted, the candidate tree is recorded."""
    verdicts = []
    seen = []

    def checks(self, timeout=120):
        passed = Checked.verdicts.pop(0) if Checked.verdicts else False
        Checked.seen.append((self.root / 'package/more.py').read_text())
        return {'passed': passed, 'returncode': 0 if passed else 1, 'environment_error': False}


def reply(action):
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(action)}}]}


class Scripted(LocalInvestigator):
    """Deterministic model: each script entry maps the decoded context to an action."""
    def __init__(self, script):
        super().__init__()
        self.script, self.calls = list(script), 0

    def verify_profile(self, *args):  # no live runtime offline
        pass

    def __call__(self, request, seconds):
        self.calls += 1
        return reply(self.script.pop(0)(json.loads(request['messages'][1]['content'])))


def edit(new):
    def action(context):
        block = next(b for b in context['source_blocks'] if 'helper_rare_name' in b['numbered_original_source'])
        line = int(next(t for t in block['numbered_original_source'].splitlines() if 'return 1' in t).split(':')[0])
        return {'action': 'propose_patch', 'edits': [{'source_id': block['source_id'], 'start_line': line,
                                                      'end_line': line, 'new': new}]}
    return action


FINAL = lambda context: {'action': 'final_result', 'summary': 'done'}  # noqa: E731


@pytest.fixture
def ws(registered):
    # The localization helper mutates the pinned tree after init, so one workspace serves a whole test.
    workspace = workspace_for(registered)
    workspace.__class__ = Checked
    yield workspace
    workspace.close()


def run(study, ws, repository, provider, verdicts, **budgets):
    Checked.verdicts, Checked.seen = list(verdicts), []
    spec = job()
    spec['config_snapshot']['budgets'].update(budgets)
    return study.UsageAwareWorker012(repository, provider, Checked)._run(spec, ws)


def test_happy_path_step_order(study, registered, ws, tokenizer):
    repository = MemoryRepository(registered.registry)
    provider = Scripted([edit('    return 2')])
    result = run(study, ws, repository, provider, [True])
    names = [s['name'] for s in result['steps']]
    assert result['outcome'] == 'verified_repair', result.get('summary')
    n = names.count('initial_source')
    assert n >= 2 and names[:n] == ['initial_source'] * n
    assert names[n:] == ['selection', 'dispatch', 'propose_patch', 'run_checks']
    assert all(s['state'] == 'captured' for s in result['steps'])
    assert (result['model_calls'], result['patch_count'], result['check_count']) == (1, 1, 1)


SEARCH = lambda context: {'action': 'search', 'query': 'helper_rare_name'}  # noqa: E731


def test_check_budget_stops_after_failed_candidate(study, registered, ws, tokenizer):
    provider = Scripted([edit('    return 3')])
    result = run(study, ws, MemoryRepository(registered.registry), provider, [False], max_checks=1)
    assert result['outcome'] == 'failed_checks' and result['summary'] == 'Candidate verification budget reached'
    assert (provider.calls, result['check_count']) == (1, 1) and len(Checked.seen) == 1


def test_patch_budget_stops_after_failed_candidate(study, registered, ws, tokenizer):
    provider = Scripted([edit('    return 3')])
    result = run(study, ws, MemoryRepository(registered.registry), provider, [False], max_patches=1)
    assert result['outcome'] == 'failed_checks' and provider.calls == 1 and result['patch_count'] == 1


def test_model_call_budget_stops_without_extra_dispatch(study, registered, ws, tokenizer):
    provider = Scripted([SEARCH, edit('    return 3')])
    result = run(study, ws, MemoryRepository(registered.registry), provider, [False], max_calls=2)
    assert result['outcome'] == 'failed_checks' and result['summary'] == 'Model call budget reached'
    assert (provider.calls, result['model_calls'], result['check_count']) == (2, 2, 1)


def test_failed_check_feeds_second_candidate(study, registered, ws, tokenizer):
    provider = Scripted([edit('    return 3'), edit('    return 2')])
    result = run(study, ws, MemoryRepository(registered.registry), provider, [False, True])
    assert result['outcome'] == 'verified_repair' and provider.calls == 2
    assert (result['model_calls'], result['patch_count'], result['check_count']) == (2, 2, 2)
    assert [s['name'] for s in result['steps'] if s['kind'] != 'context' and s['name'] != 'initial_source'] == [
        'dispatch', 'propose_patch', 'run_checks', 'dispatch', 'propose_patch', 'run_checks']


class Crash(Exception):
    pass


class FaultyRepository(MemoryRepository):
    """Real begin semantics: a pending model dispatch blocks every later step; optional crash point."""
    crash_on = None

    def begin(self, job, kind, name, request):
        if any(s['state'] == 'pending' and s['kind'] == 'model' for s in self.record['steps']):
            raise RuntimeError('Unknown model dispatch cannot be repeated')
        if name == self.crash_on:
            self.crash_on = None
            raise Crash('simulated worker loss')
        return super().begin(job, kind, name, request)


class NeverDispatch(LocalInvestigator):
    def __init__(self):
        super().__init__()

    def prepare(self, *args, **kwargs):
        raise AssertionError('Recovery must not prepare a new request')

    def __call__(self, *args, **kwargs):
        raise AssertionError('Recovery must not redispatch')


def test_recovery_replays_captured_response_without_redispatch(study, registered, ws, tokenizer):
    repository = FaultyRepository(registered.registry)
    repository.crash_on = 'propose_patch'
    with pytest.raises(Crash):
        run(study, ws, repository, Scripted([edit('    return 2')]), [True])
    before = [(s['seq'], s['name']) for s in repository.record['steps']]
    assert before[-1][1] == 'dispatch' and repository.record['steps'][-1]['state'] == 'captured'
    result = run(study, ws, repository, NeverDispatch(), [True])
    assert result['outcome'] == 'verified_repair' and result['model_calls'] == 1
    assert [(s['seq'], s['name']) for s in result['steps'][:len(before)]] == before
    assert [s['name'] for s in result['steps'][len(before):]] == ['propose_patch', 'run_checks']


def test_recovery_after_checks_does_not_recheck_or_redispatch(study, registered, ws, tokenizer):
    repository = FaultyRepository(registered.registry)
    run(study, ws, repository, Scripted([edit('    return 2')]), [True])
    repository.record.pop('outcome')
    result = run(study, ws, repository, NeverDispatch(), [])
    assert result['outcome'] == 'verified_repair' and (result['model_calls'], result['check_count']) == (1, 1)
    assert Checked.seen == []


def test_unknown_dispatch_is_preserved_and_never_repeated(study, registered, ws, tokenizer):
    class Lost(Scripted):
        def __call__(self, request, seconds):
            raise ConnectionError('socket closed mid-response')
    repository = FaultyRepository(registered.registry)
    result = run(study, ws, repository, Lost([]), [])
    assert result['outcome'] == 'unknown_dispatch'
    pending = [s for s in result['steps'] if s['state'] == 'pending']
    assert [(s['kind'], s['name']) for s in pending] == [('model', 'dispatch')] and result['model_calls'] == 1
    snapshot = json.dumps(repository.record['steps'], sort_keys=True)
    with pytest.raises(RuntimeError, match='cannot be repeated'):
        run(study, ws, repository, Scripted([edit('    return 2')]), [True])
    assert json.dumps(repository.record['steps'], sort_keys=True) == snapshot


def test_duplicate_candidate_is_rejected_from_cache_then_stops(study, registered, ws, tokenizer):
    provider = Scripted([edit('    return 3')] * 3)
    result = run(study, ws, MemoryRepository(registered.registry), provider, [False])
    patches = [s['result']['body'] for s in result['steps'] if s['name'] == 'propose_patch']
    assert [('error' in p) for p in patches] == [False, True, True]
    assert patches[1]['duplicate_candidate'] and patches[1]['cached_verification']['passed'] is False
    assert result['outcome'] == 'failed_checks' and result['summary'].startswith('Two identical rejected')
    assert (provider.calls, result['check_count'], len(Checked.seen)) == (3, 1, 1)


def test_two_identical_rejected_edits_stop_without_checks(study, registered, ws, tokenizer):
    def bad(context):
        block = context['source_blocks'][0]
        return {'action': 'propose_patch', 'edits': [{'source_id': block['source_id'], 'start_line': 900,
                                                      'end_line': 900, 'new': 'x'}]}
    provider = Scripted([bad, bad, bad])
    result = run(study, ws, MemoryRepository(registered.registry), provider, [])
    assert result['outcome'] == 'invalid_patch' and result['summary'].startswith('Two identical rejected')
    assert (provider.calls, result['check_count'], result['patch_count']) == (2, 0, 0) and Checked.seen == []


def test_exhausted_deadline_raises_before_any_dispatch(study, registered, ws, tokenizer):
    class Expired(MemoryRepository):
        def remaining(self, job): return 0
    provider = Scripted([edit('    return 2')])
    with pytest.raises(TimeoutError):
        run(study, ws, Expired(registered.registry), provider, [True])
    assert provider.calls == 0 and Checked.seen == []


def test_run_once_maps_deadline_to_timeout_outcome(study, registered, ws, tokenizer):
    class Expired(MemoryRepository):
        def claim(self, owner): return {**job(), 'id': 'fixture', 'tenant_id': 'tenant', 'task_id': 'x', 'task_digest': 'x'}
        def remaining(self, job): return 0
    repository = Expired(registered.registry)
    repository.registry = type('R', (), {'get': lambda s, i: ws.case, 'fingerprint': lambda s, c: 'x'})()
    repository._model_digest = lambda: 'm'
    spec_snapshot = job()['config_snapshot']; spec_snapshot['model_manifest_digest'] = 'm'
    repository.claim = lambda owner: {**job(), 'config_snapshot': spec_snapshot, 'task_id': 'x', 'task_digest': 'x'}
    provider = Scripted([edit('    return 2')])
    worker = study.UsageAwareWorker012(repository, provider, lambda registry, case: ws)
    result = worker.run_once()
    assert result['outcome'] == 'timeout' and provider.calls == 0, result['summary']
