"""CLI status and read-only admission checks; no model or service execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def study():
    from scripts import study012
    return study012


def forbid(*args, **kwargs):
    raise AssertionError('Unexpected service, policy, or task execution')


@pytest.mark.parametrize('receipt', [
    {'status': 'failed', 'outcome': 'environment_failure'},
    {'status': 'incomplete'},
    {'status': 'unknown'},
    {'status': 'completed', 'outcome': 'unknown_dispatch'},
    {'status': 'completed', 'outcome': 'environment_failure'},
])
def test_failed_report_returns_nonzero_and_preserves_json(study, monkeypatch, capsys, tmp_path, receipt):
    monkeypatch.setattr(study, 'registered_task010', forbid)
    monkeypatch.setattr(study, 'policy012', forbid)
    monkeypatch.setattr(study, 'run010', forbid)
    monkeypatch.setattr(study, 'report010', lambda *a, **k: receipt)
    assert study.main(['report', '--runtime', str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out) == receipt
    assert list(tmp_path.iterdir()) == []


def test_doctor_remains_read_only(study, monkeypatch, capsys):
    receipt = {'operation': 'doctor', 'passed': True, 'inference_started': False,
               'database_started': False, 'docker_started': False}
    monkeypatch.setattr(study, 'doctor010', lambda args: receipt)
    monkeypatch.setattr(study, 'registered_task010', forbid)
    monkeypatch.setattr(study, 'policy012', forbid)
    monkeypatch.setattr(study, 'run010', forbid)
    assert study.main(['doctor']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['passed'] is True and output['version'] == study.VERSION
    assert not output['inference_started'] and not output['database_started'] and not output['docker_started']


def test_verified_report_returns_zero_without_preparing_a_run(study, monkeypatch, capsys, tmp_path):
    receipt = {'status': 'completed', 'outcome': 'verified_repair', 'verified': True}
    calls = []
    def report(runtime, *, expected_version):
        calls.append((runtime, expected_version))
        return receipt
    monkeypatch.setattr(study, 'report010', report)
    monkeypatch.setattr(study, 'registered_task010', forbid)
    monkeypatch.setattr(study, 'policy012', forbid)
    monkeypatch.setattr(study, 'run010', forbid)
    assert study.main(['report', '--runtime', str(tmp_path)]) == 0
    assert calls == [(tmp_path, study.VERSION)]
    assert json.loads(capsys.readouterr().out) == receipt


def test_incomplete_runtime_exits_nonzero_at_process_boundary(study, tmp_path):
    environment = {'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1',
                   'PYTHONPATH': os.pathsep.join(value for value in sys.path if value and Path(value).is_dir())}
    target = Path(study.__file__)
    arguments = [sys.executable, str(target), 'report', '--runtime', str(tmp_path)]
    if target.with_name('retrieval_loop012.py').is_file():
        from scripts import study010
        sources = [
            ('kairos_api.investigations.context_v7', str(target.with_name('context_v7.py'))),
            ('kairos_api.investigations.worker', str(target.with_name('worker.py'))),
            ('scripts.repair010.feedback010', str(study010.ROOT / 'scripts/repair010/feedback010.py')),
            ('scripts.repair012.retrieval_loop012', str(target.with_name('retrieval_loop012.py'))),
        ]
        bootstrap = """import importlib.util,json,runpy,sys
sources=json.loads(sys.argv.pop(1)); target=sys.argv.pop(1)
for name,path in sources:
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
runpy.run_path(target,run_name='__main__')
"""
        arguments = [sys.executable, '-c', bootstrap, json.dumps(sources), str(target),
                     'report', '--runtime', str(tmp_path)]
    result = subprocess.run(arguments,
                            capture_output=True, env=environment, timeout=20, check=False)
    assert result.returncode == 1, result.stderr.decode(errors='replace')
    assert result.stdout, result.stderr.decode(errors='replace')
    assert json.loads(result.stdout)['status'] == 'incomplete'
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('configuration,cap', [('loop-v8', 10), ('baseline-v8', 1)])
def test_policy_freezes_the_registered_dispatch_cap(study, monkeypatch, tmp_path, configuration, cap):
    monkeypatch.setattr(study, 'storage_guard', lambda roots, projected: {'owned_bytes': 0})
    recorded = []
    monkeypatch.setattr(study, 'TokenBoundCLI012', type('FixtureTransport', (), {
        'prompt_ceiling': 64000, 'completion_ceiling': 8192,
        '__init__': lambda self, *a, **k: recorded.append(k['max_dispatches'])}))
    args = SimpleNamespace(configuration=configuration, budget_root=[tmp_path], retrieval_mode='ast')
    policy = study.policy012(args, object(), {'revision': 'fixture-revision'})
    policy.provider_factory()
    assert recorded == [cap]
    assert policy.generation['max_harness_dispatches'] == cap
    assert all((study.ROOT / name).is_file() for name in policy.source_files)


def test_semantic_policy_refuses_index_outside_counted_storage(study, monkeypatch, tmp_path):
    budget = tmp_path / 'owned'
    budget.mkdir()
    monkeypatch.setattr(study, 'storage_guard', lambda roots, projected: {'owned_bytes': 0})
    monkeypatch.setattr(study, 'QueryEncoder012', forbid)
    args = SimpleNamespace(configuration='loop-v8', budget_root=[budget], retrieval_mode='hybrid',
                           index_root=tmp_path / 'uncounted', index_id='fixture-id',
                           encoder_dir=budget / 'encoder', encoder_profile=budget / 'profile.json')
    with pytest.raises(ValueError, match='counted experiment roots'):
        study.policy012(args, object(), {'revision': 'fixture-revision', 'issue': 'query'})


@pytest.mark.parametrize('issue', ['x' * 4097, '\u00e9' * 2049, '   ', '!!!', 'valid\x00query'])
def test_invalid_initial_query_is_refused_before_encoder_or_runtime(study, monkeypatch, tmp_path, issue):
    monkeypatch.setattr(study, 'storage_guard', lambda roots, projected: {'owned_bytes': 0})
    monkeypatch.setattr(study, 'QueryEncoder012', forbid)
    monkeypatch.setattr(study, 'load_index', forbid)
    monkeypatch.setattr(study, 'run010', forbid)
    args = SimpleNamespace(configuration='loop-v8', budget_root=[tmp_path], retrieval_mode='hybrid')
    with pytest.raises(ValueError, match='4096 UTF-8 bytes'):
        study.policy012(args, object(), {'revision': 'fixture-revision', 'issue': issue})
    assert list(tmp_path.iterdir()) == []
