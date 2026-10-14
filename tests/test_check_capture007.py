"""Verifier streams remain byte-exact, bounded and available in evidence downloads."""
import base64
import hashlib
import json
import subprocess
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from kairos_api.investigations.sandbox import Workspace, RAW_OUTPUT_LIMIT
from kairos_api.investigations.routes import create_investigation_router
from kairos_api.investigations.worker import InvestigationWorker
from test_investigations import registry, repository, enqueue


VERDICT = b'\nKAIROS_VERIFIER_RESULT {"complete":true,"tests_run":110}\n'


@pytest.fixture
def workspace(tmp_path):
    directory = tmp_path / 'case'
    source = directory / 'source' / 'source'
    source.mkdir(parents=True)
    (source / 'value.py').write_text('value = 1\n')
    (directory / 'test.patch').write_text('')
    instance = Workspace(SimpleNamespace(verify=lambda _: None, directory=lambda _: directory),
                         {'image': 'isolated-fixture', 'command': ['registered-check'],
                          'entry_lines': {'source/value.py': 1}})
    try:
        yield instance
    finally:
        instance.close()


def mocked_check(monkeypatch, stdout, stderr=b'', timeout=False):
    def run(argv, **kwargs):
        if argv[1] == 'rm':
            return subprocess.CompletedProcess(argv, 0)
        assert '--network=none' in argv and '--read-only' in argv
        kwargs['stdout'].write(stdout)
        kwargs['stderr'].write(stderr)
        if timeout:
            raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr('kairos_api.investigations.sandbox.subprocess.run', run)


def stream_bytes(result, name):
    stream = result['raw_output'][name]
    value = base64.b64decode(stream['data'], validate=True)
    assert len(value) == stream['bytes']
    assert hashlib.sha256(value).hexdigest() == stream['sha256']
    return value


def test_full_raw_output_survives_tail_truncation_and_invalid_utf8(workspace, monkeypatch):
    stdout = b'first assertion\xff\n' + b'captured output\n' * 3000 + VERDICT
    stderr = 'context λ\n'.encode() + b'\xfe\n'
    mocked_check(monkeypatch, stdout, stderr)
    result = workspace.checks()
    assert result['passed'] and result['output_truncated']
    assert 'first assertion' not in result['stdout']
    assert stream_bytes(result, 'stdout') == stdout
    assert stream_bytes(result, 'stderr') == stderr
    assert result['raw_output']['complete'] is True
    assert result['raw_output']['observed_bytes'] == len(stdout) + len(stderr)
    assert result['stdout'] == stdout[-24000:].decode(errors='replace')


def test_combined_output_ceiling_fails_even_with_completion_marker(workspace, monkeypatch):
    stdout = b'A' * (RAW_OUTPUT_LIMIT - 100) + VERDICT
    stderr = b'B' * 200
    mocked_check(monkeypatch, stdout, stderr)
    result = workspace.checks()
    assert not result['passed'] and result['verification_complete']
    assert result['stop_reason'] == 'output_limit_exceeded'
    assert result['raw_output']['complete'] is False
    assert stream_bytes(result, 'stdout') == stdout
    remainder = RAW_OUTPUT_LIMIT - len(stdout)
    assert stream_bytes(result, 'stderr') == stderr[:remainder]
    assert result['raw_output']['stderr']['truncated'] is True
    assert result['raw_output']['stderr']['observed_bytes'] == len(stderr)


def test_file_guard_is_explicitly_incomplete(workspace, monkeypatch):
    stdout = b'x' * RAW_OUTPUT_LIMIT
    mocked_check(monkeypatch, stdout)
    result = workspace.checks()
    assert result['output_limit_exceeded'] and not result['passed']
    assert not result['raw_output']['complete']
    assert stream_bytes(result, 'stdout') == stdout


def test_timeout_preserves_exact_output_written_before_interruption(workspace, monkeypatch):
    stdout = b'started check\xff\n'
    mocked_check(monkeypatch, stdout, timeout=True)
    result = workspace.checks()
    assert result['returncode'] == 124 and result['stop_reason'] == 'timeout'
    assert not result['passed']
    assert stream_bytes(result, 'stdout') == stdout
    assert stream_bytes(result, 'stderr') == b''


def test_raw_streams_survive_durable_capture_and_authenticated_download(repository):
    raw = b'original assertion\xff\n'
    stream = {'data': base64.b64encode(raw).decode(), 'bytes': len(raw),
              'observed_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
              'truncated': False}
    result = {'passed': False, 'returncode': 1,
              'raw_output': {'encoding': 'base64', 'stdout': stream}}
    queued = enqueue(repository)
    job = repository.claim('capture-test')
    worker = InvestigationWorker(repository, provider=object())
    worker._verify(job, SimpleNamespace(checks=lambda _: dict(result)), 'fixture-patch')
    record = repository.read(queued['id'], 'tenant-a')
    assert record['integrity']['verified']
    assert stream_bytes(record['steps'][0]['result']['body'], 'stdout') == raw
    application = FastAPI()
    application.include_router(create_investigation_router(lambda: 'tenant-a', lambda: 'key',
                                lambda: 'tenant-a', lambda: repository))
    response = TestClient(application).get('/api/investigations/' + queued['id'] + '/bundle')
    assert response.status_code == 200
    downloaded = json.loads(response.content)
    assert stream_bytes(downloaded['steps'][0]['result']['body'], 'stdout') == raw
