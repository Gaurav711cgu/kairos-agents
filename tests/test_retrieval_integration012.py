"""Real DB/container journeys; explicitly mechanical provider and encoder fixtures."""
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kairos_api.investigations.routes import create_investigation_router

from scripts.retrieval011 import build_index
from scripts.repair012.retrieval_loop012 import RetrievalWorker012, workspace_class012
from test_unresolved_integration010 import integration, MechanicalFixtureProvider, FIXTURE_SOURCE
from test_investigations import expire


class MechanicalEncoder012:
    dimension = 3
    identity = {'software_fixture_only': True, 'kind': 'constant-vectors-for-integration'}

    def __init__(self):
        self.queries = 0
        self.last_metadata = {'software_fixture_only': True}

    def encode(self, texts):
        return np.ones((len(texts), 3), dtype=np.float32)

    def encode_queries(self, texts):
        self.queries += 1
        return self.encode(texts)


def prepared(integration, tmp_path):
    task = integration['task']
    encoder = MechanicalEncoder012()
    index = build_index(integration['directory'] / 'source', task['approved_prefix'],
        task['revision'], tmp_path / 'index', encoder)
    cls = workspace_class012(tmp_path / 'index', index.index_id, encoder, 'hybrid')
    return encoder, index, cls


def test_retrieval_loop_captures_source_checks_patch_and_replays_without_execution(integration, tmp_path):
    repository, task = integration['repository'], integration['task']
    encoder, index, cls = prepared(integration, tmp_path)
    row = repository.enqueue('fixture-tenant', 'retrieval-v8', task['id'], 'loop-v8')
    provider = MechanicalFixtureProvider()
    record = RetrievalWorker012(repository, provider, cls).run_once()
    assert record['outcome'] == 'verified_repair' and provider.calls == 1
    assert encoder.queries == 1
    assert (record['patch_count'], record['check_count']) == (1, 1)
    selections = [step for step in record['steps'] if step['name'] == 'retrieval_selection012']
    assert len(selections) == 1 and selections[0]['result']['body']['audit']['index_id'] == index.index_id
    assert selections[0]['seq'] < next(step['seq'] for step in record['steps'] if step['kind'] == 'model')
    assert (integration['directory'] / 'source/package/logic.py').read_text() == FIXTURE_SOURCE
    app = FastAPI()
    app.include_router(create_investigation_router(
        lambda: 'fixture-tenant', lambda: 'fixture-command', lambda: 'fixture-tenant', lambda: repository))
    replay = TestClient(app).get('/api/investigations/' + str(row['id']) + '/replay')
    assert replay.status_code == 200
    assert replay.json()['tool_executions'] == replay.json()['network_calls'] == 0
    assert provider.calls == 1 and encoder.queries == 1


def test_recovery_finishes_captured_retrieval_without_reencoding(integration, tmp_path):
    repository, task = integration['repository'], integration['task']
    encoder, index, cls = prepared(integration, tmp_path)
    row = repository.enqueue('fixture-tenant', 'recover-retrieval', task['id'], 'loop-v8')
    job = repository.claim('interrupted-worker')
    workspace = cls(integration['registry'], task)
    try:
        observations, audit = workspace.initial_retrieval012()
        seq = repository.begin(job, 'context', 'retrieval_selection012', {'index_id': index.index_id})
        repository.capture(job, seq, {'observations': observations, 'audit': audit})
        result = observations[0]['result']
        repository.begin(job, 'tool', 'initial_source',
                         {'origin': 'retrieval012', 'chunk_id': result['retrieval011']['chunk_id']})
    finally:
        workspace.close()
    assert encoder.queries == 1
    expire(repository, row['id'])
    provider = MechanicalFixtureProvider()
    record = RetrievalWorker012(repository, provider, cls).run_once()
    assert record['outcome'] == 'verified_repair' and provider.calls == 1 and encoder.queries == 1
    assert all(step['state'] == 'captured' for step in record['steps'])


@pytest.mark.parametrize('configuration', ['baseline-v8', 'loop-v8'])
@pytest.mark.parametrize('retrieval_mode', ['hybrid', 'ast'])
def test_versioned_runner_preserves_frozen_policy_and_reports_without_redispatch(integration, tmp_path, monkeypatch, configuration, retrieval_mode):
    """Actual owned PostgreSQL/container checks with explicit fixture model actions."""
    import argparse
    import hashlib
    import json
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    import scripts.study010 as study010
    from scripts.repair012.retrieval_loop012 import VERSION, RuntimePolicy012

    if not shutil.which('initdb') or not shutil.which('pg_ctl'):
        pytest.skip('Owned native PostgreSQL tools are required')
    encoder, index, workspace = prepared(integration, tmp_path)
    if retrieval_mode == 'ast':
        from scripts.study012 import UnassistedWorkspace012
        from scripts.repair012.retrieval_loop012 import UsageAwareWorker012
        workspace, worker = UnassistedWorkspace012, UsageAwareWorker012
    else:
        worker = RetrievalWorker012
    providers = []

    class RunnerFixture(MechanicalFixtureProvider):
        def __init__(self, *values, **settings):
            super().__init__()
            assert settings == {'model_id': study010.REQUESTED_MODEL}
            providers.append(self)

    monkeypatch.setattr(study010, 'cli_identity010', lambda _: (Path(sys.executable), {
        'cli_version': 'mechanical-software-fixture-no-model',
        'cli_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        'requested_model': study010.REQUESTED_MODEL, 'resolved_model': None}))
    runtime = tmp_path / ('versioned runner ' + configuration)
    policy = RuntimePolicy012(VERSION, configuration, {'fixture_only': True},
        {'retrieval': {'index_id': index.index_id}, 'software_fixture_only': True},
        ('scripts/study012.py',), RunnerFixture, worker, workspace)
    arguments = argparse.Namespace(checkout=study010.ROOT, manifest=integration['manifest'],
        case_root=integration['registry'].runtime, task_id=integration['task']['id'],
        runtime=runtime, codex=None)
    original_manifest = os.environ.get('KAIROS_INVESTIGATION_MODEL_MANIFEST')
    result = study010.run010(arguments, policy=policy)
    assert result['verified'] and result['evidence_verified']
    assert json.loads((runtime / 'result.json').read_text())['version'] == VERSION
    assert result['cleanup_errors'] == [] and result['failure'] is None and result['source_unchanged']
    frozen = json.loads((runtime / 'experiment.json').read_text())
    assert frozen['action_protocol'] == configuration and frozen['policy'] == policy.metadata
    assert frozen['budgets']['max_calls'] == (10 if configuration == 'loop-v8' else 1)
    assert frozen['source']['scripts/study012.py'] == study010._sha(study010.ROOT / 'scripts/study012.py')
    assert study010.report010(runtime, expected_version=VERSION) == result
    assert study010.run010(arguments, policy=policy) == result
    assert len(providers) == 1 and providers[0].calls == 1
    assert encoder.queries == (0 if retrieval_mode == 'ast' else 1)
    assert os.environ.get('KAIROS_INVESTIGATION_MODEL_MANIFEST') == original_manifest
    stopped = subprocess.run([shutil.which('pg_ctl'), '-D', str(runtime / 'postgres-data'), 'status'],
                             capture_output=True, timeout=10)
    assert stopped.returncode != 0
    assert (integration['directory'] / 'source/package/logic.py').read_text() == FIXTURE_SOURCE
