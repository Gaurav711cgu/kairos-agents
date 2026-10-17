"""Zero-hit and issue-only localization never receive maintainer entry hints."""
from copy import deepcopy
import subprocess
import sys

import pytest

from test_study012 import study
from test_context_v5 import MemoryRepository
from test_unresolved_registry010 import registered
from kairos_api.investigations.contracts import CONFIGURATIONS
from scripts.retrieval011 import build_index


def job():
    return {'id': 'fixture', 'tenant_id': 'tenant', 'configuration': 'loop-v8',
            'config_snapshot': {'budgets': dict(CONFIGURATIONS['loop-v8'])}}


class NoDispatch:
    def prepare(self, *args, **kwargs):
        raise AssertionError('No model preparation without actionable source')

    def __call__(self, *args, **kwargs):
        raise AssertionError('No model dispatch without actionable source')


def test_zero_hit_lexical_selection_stops_and_recovers_without_hints(study, registered, tmp_path):
    module = sys.modules['scripts.repair012.retrieval_loop012']
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'unrelatedidentifierwithoutsourceoverlap'
    index = build_index(registered.directory / 'source', case['approved_prefix'],
                        case['revision'], tmp_path / 'index')
    cls = module.workspace_class012(tmp_path / 'index', index.index_id, None, 'lexical')
    repository = MemoryRepository(registered.registry)
    workspace = cls(registered.registry, case)
    worker = module.RetrievalWorker012(repository, NoDispatch(), cls)
    try:
        with pytest.raises(module.NoSourceEvidence012):
            worker._state(job(), workspace)
        selection = repository.record['steps']
        assert len(selection) == 1 and selection[0]['name'] == 'retrieval_selection012'
        assert selection[0]['result']['body']['audit']['returned'] == 0
        assert selection[0]['result']['body']['observations'] == []
        assert not any(step['name'] == 'initial_source' for step in selection)
        before = deepcopy(selection)
        workspace.initial_retrieval012 = lambda: pytest.fail('Captured retrieval must not be queried again')
        result = worker._run(job(), workspace)
        assert result['outcome'] == 'no_patch' and result['model_calls'] == 0
        assert result['steps'] == before
        assert workspace.case['entry_files'] == case['entry_files']
        assert workspace.case['entry_lines'] == case['entry_lines']
    finally:
        workspace.close()


def test_ast_ignores_entry_hints_without_invalidating_registered_case(study, registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'value(3) returns an unexpected value for an input.'
    original = deepcopy(case)
    workspace = study.UnassistedWorkspace012(registered.registry, case)
    try:
        results = workspace.initial_sources012()
        assert results and 'def value(x)' in results[0]['text']
        assert workspace.case == original
        assert registered.registry.directory(workspace.case) == registered.directory
    finally:
        workspace.close()


def test_ast_no_symbol_match_stops_without_registered_file_fallback(study, registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'unrelatedidentifierwithoutsourceoverlap'
    workspace = study.UnassistedWorkspace012(registered.registry, case)
    repository = MemoryRepository(registered.registry)
    worker = study.UsageAwareWorker012(repository, NoDispatch(), study.UnassistedWorkspace012)
    try:
        result = worker._run(job(), workspace)
        assert result['outcome'] == 'no_patch'
        assert result['model_calls'] == 0 and result['steps'] == []
    finally:
        workspace.close()


def test_v8_worker_captures_unassisted_ast_regions(study, registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'value(3) returns an unexpected value.'
    workspace = study.UnassistedWorkspace012(registered.registry, case)
    repository = MemoryRepository(registered.registry)
    worker = study.UsageAwareWorker012(repository, NoDispatch(), study.UnassistedWorkspace012)
    try:
        record, observations, _, _, _ = worker._state(job(), workspace)
        assert len(observations) == 1 and observations[0]['result']['reference']
        assert record['steps'][0]['name'] == 'initial_source'
        assert 'Public issue function ranking' in observations[0]['result']['selection_reason']
        assert workspace.case['entry_lines'] == case['entry_lines']
    finally:
        workspace.close()


def test_v7_worker_does_not_use_v8_localization_hook(study, registered):
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'unrelatedidentifierwithoutsourceoverlap'
    workspace = study.UnassistedWorkspace012(registered.registry, case)
    workspace.initial_sources012 = lambda: pytest.fail('Historical worker must not use the v8 hook')
    repository = MemoryRepository(registered.registry)
    worker = study.UsageAwareWorker012(repository, NoDispatch(), study.UnassistedWorkspace012)
    current = {**job(), 'configuration': 'loop-v7'}
    try:
        _, observations, _, _, _ = worker._state(current, workspace)
        assert observations[0]['result']['selection_reason'].startswith('Registered original-source fallback')
    finally:
        workspace.close()


def test_ast_preserves_completed_verification_requirement(study, registered, monkeypatch):
    case = registered.registry.get(registered.task['id'])
    workspace = study.UnassistedWorkspace012(registered.registry, case)
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0))
    try:
        result = workspace.checks()
        assert result['returncode'] == 0 and not result['passed']
        assert result['verification_incomplete'] and result['verification_complete'] is False
    finally:
        workspace.close()


def test_default_ast_localization_keeps_historical_entry_fallback(study, registered):
    from kairos_api.investigations.context_v7 import initial_sources
    from kairos_api.investigations.sandbox import Workspace
    case = registered.registry.get(registered.task['id'])
    case['issue'] = 'unrelatedidentifierwithoutsourceoverlap'
    workspace = Workspace(registered.registry, case)
    try:
        result = initial_sources(workspace)
        assert result and result[0]['selection_reason'].startswith('Registered original-source fallback')
        assert initial_sources(workspace, use_entry_hints=False) == []
    finally:
        workspace.close()
