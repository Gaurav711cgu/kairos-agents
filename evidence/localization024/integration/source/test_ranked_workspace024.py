"""The v6 selector reaches the worker only through the explicit v8 hook."""
import pytest

from test_study012 import study  # noqa: F401  (fixture)
from test_context_v5 import MemoryRepository
from test_unresolved_registry010 import registered  # noqa: F401  (fixture)
from test_retrieval_admission012 import NoDispatch, job
from scripts.ranked_workspace024 import RankedWorkspace024


def test_v8_worker_durably_captures_ranked_regions_once(study, registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'value(3) returns an unexpected value.'
    workspace = RankedWorkspace024(registered.registry, case)
    repository = MemoryRepository(registered.registry)
    worker = study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)
    try:
        _, observations, _, _, _ = worker._state(job(), workspace)
        steps = [s for s in repository.record['steps'] if s['name'] == 'initial_source']
        assert steps and len(steps) == len(observations) <= 4
        assert all(o['result']['reference'] and 'hidden_answer' not in o['result']['path'] for o in observations)
        assert 'issue-ranked-source024' in steps[0]['result']['body']['localization']['version']
        workspace.initial_sources012 = lambda: pytest.fail('Captured sources must be replayed, not reselected')
        worker._state(job(), workspace)
        assert [s for s in repository.record['steps'] if s['name'] == 'initial_source'] == steps
    finally:
        workspace.close()


def test_legacy_v7_job_never_uses_ranked_hook(study, registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'value(3) returns an unexpected value.'
    workspace = RankedWorkspace024(registered.registry, case)
    workspace.initial_sources012 = lambda: pytest.fail('v7 must keep context_v7 localization')
    repository = MemoryRepository(registered.registry)
    worker = study.UsageAwareWorker012(repository, NoDispatch(), RankedWorkspace024)
    try:
        worker._state({**job(), 'configuration': 'loop-v7'}, workspace)
    finally:
        workspace.close()
