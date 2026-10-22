"""A crash between localization captures must not silently truncate the source set."""
import pytest

from test_study012 import study  # noqa: F401  (fixture)
from test_context_v5 import MemoryRepository
from test_unresolved_registry010 import registered  # noqa: F401  (fixture)
from test_retrieval_admission012 import NoDispatch, job
from test_coding_context_v3_014 import extra
from scripts.ranked_workspace024 import RankedWorkspace024


class Crash(Exception):
    pass


class CrashingRepository(MemoryRepository):
    """Fail before the n-th initial_source begin, after earlier captures are durable."""
    def __init__(self, registry, crash_at):
        super().__init__(registry)
        self.crash_at = crash_at

    def begin(self, job, kind, name, request):
        if name == 'initial_source' and sum(s['name'] == 'initial_source' for s in self.record['steps']) + 1 == self.crash_at:
            self.crash_at = None
            raise Crash('simulated worker loss')
        return super().begin(job, kind, name, request)


def workspace_for(registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'value(3) and helper_rare_name() and other_rare_name() return unexpected values.'
    workspace = RankedWorkspace024(registered.registry, case)
    extra(workspace, case['approved_prefix'] + 'more.py', 'def helper_rare_name():\n    return 1\n\n\n\n\n\n\n\n\ndef other_rare_name():\n    return 2\n')
    return workspace


def sources(repository):
    return [s for s in repository.record['steps'] if s['name'] == 'initial_source']


def test_recovery_completes_partial_localization_with_identical_prefix(study, registered):
    workspace = workspace_for(registered)
    reference = MemoryRepository(registered.registry)
    repository = CrashingRepository(registered.registry, crash_at=2)
    try:
        study.UsageAwareWorker012(reference, NoDispatch(), RankedWorkspace024)._state(job(), workspace)
        expected = [s['result']['body'] for s in sources(reference)]
        assert len(expected) >= 2
        worker = study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)
        with pytest.raises(Crash):
            worker._state(job(), workspace)
        assert len(sources(repository)) == 1
        worker._state(job(), workspace)
        assert [s['result']['body'] for s in sources(repository)] == expected
        assert [s['request']['body']['index'] for s in sources(repository)] == list(range(len(expected)))
    finally:
        workspace.close()


def test_changed_reselection_fails_closed(study, registered):
    workspace = workspace_for(registered)
    repository = CrashingRepository(registered.registry, crash_at=2)
    try:
        worker = study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)
        with pytest.raises(Crash):
            worker._state(job(), workspace)
        original = workspace.initial_sources012
        workspace.initial_sources012 = lambda: list(reversed(original()))
        with pytest.raises(ValueError, match='Partial localization'):
            worker._state(job(), workspace)
    finally:
        workspace.close()


def test_legacy_records_without_count_stay_complete(study, registered):
    workspace = workspace_for(registered)
    repository = MemoryRepository(registered.registry)
    try:
        worker = study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)
        worker._state(job(), workspace)
        for step in sources(repository):
            step['request']['body'] = {'origin': 'public-issue-symbol-ast-v1'}
        del repository.record['steps'][1:]
        workspace.initial_sources012 = lambda: pytest.fail('Legacy captured localization must not be reselected')
        worker._state(job(), workspace)
    finally:
        workspace.close()


def test_shorter_reselection_fails_closed(study, registered):
    workspace = workspace_for(registered)
    repository = CrashingRepository(registered.registry, crash_at=2)
    try:
        worker = study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)
        with pytest.raises(Crash):
            worker._state(job(), workspace)
        original = workspace.initial_sources012
        workspace.initial_sources012 = lambda: original()[:1]
        with pytest.raises(ValueError, match='Partial localization'):
            worker._state(job(), workspace)
    finally:
        workspace.close()


class PendingAwareRepository(MemoryRepository):
    """Model repository.begin: an identical pending step resumes, a different one is refused."""
    def begin(self, job, kind, name, request):
        pending = [s for s in self.record['steps'] if s['state'] == 'pending']
        if pending:
            if (pending[-1]['kind'], pending[-1]['name'], pending[-1]['request']['body']) == (kind, name, request):
                return pending[-1]['seq']
            raise RuntimeError('Pending step requires recovery')
        return super().begin(job, kind, name, request)


def test_inflight_legacy_pending_step_resumes_with_legacy_shape(study, registered):
    workspace = workspace_for(registered)
    repository = PendingAwareRepository(registered.registry)
    repository.record['steps'].append({'seq': 1, 'kind': 'tool', 'name': 'initial_source', 'state': 'pending',
                                       'request': {'body': {'origin': 'public-issue-symbol-ast-v1'}}, 'result': None})
    try:
        study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)._state(job(), workspace)
        assert all(s['state'] == 'captured' for s in repository.record['steps'])
        assert all(s['request']['body'] == {'origin': 'public-issue-symbol-ast-v1'} for s in sources(repository))
    finally:
        workspace.close()
