"""Offline boundaries for the separately authorized one-dispatch API pilot."""
import json
from pathlib import Path
import threading

import httpx
import pytest

from scripts import free_model_pilot as pilot

CASE = 'django__django-11066'
KEY = 'private_fixture_key_1234567890'


def environment(tmp_path, value=KEY, mode=0o600):
    path = tmp_path / 'environment.env'
    path.write_text('GEMINI_API_KEY=' + value + '\n')
    path.chmod(mode)
    return path


def response(action=None, finish='STOP'):
    source, _ = pilot.source_input(CASE)
    block = source['source_blocks'][0]
    action = action or {'action': 'propose_patch', 'edits': [{
        'source_id': block['source_id'], 'start_line': 27, 'end_line': 27,
        'new': "                    content_type.save(using=db, update_fields={'model'})\n"}]}
    return pilot.canonical({'candidates': [{'finishReason': finish,
        'content': {'parts': [{'text': json.dumps(action)}]}}],
        'usageMetadata': {'promptTokenCount': 123, 'candidatesTokenCount': 30,
                          'totalTokenCount': 153, 'unsupported': 'private'},
        'modelVersion': 'gemini-3.8-flash-test-fixture'})


@pytest.mark.parametrize('case_id', sorted(pilot.CASES))
def test_allowlisted_payloads_contain_only_public_pre_dispatch_source(case_id):
    request, source, provenance = pilot.request_for(case_id)
    assert set(source) == {'case_id', 'issue_url', 'title', 'issue', 'source_revision',
                          'source_blocks', 'budgets', 'scope'}
    assert source['case_id'] == case_id
    assert 'previously' in source['scope'].lower()
    raw = pilot.canonical(request)
    for forbidden in (b'/Users/', b'.runtime/', b'reference.patch', b'verification_digest',
                      b'latest_verification', b'current_candidate', b'GEMINI_API_KEY'):
        assert forbidden not in raw
    assert provenance['record_sha256'] == pilot.CASES[case_id][1]
    assert request['generationConfig']['maxOutputTokens'] == 1024
    assert 'tools' not in request


def test_validation_cases_and_arbitrary_paths_are_rejected():
    for identifier in ('django__django-11163', '../../private', '/Users/private'):
        with pytest.raises(ValueError, match='allowlisted'):
            pilot.request_for(identifier)


def test_capture_corruption_is_rejected_before_dispatch(tmp_path, monkeypatch):
    identifier, _ = pilot.CASES[CASE]
    path = tmp_path / 'dashboard/evidence/records' / f'{identifier}.json'
    path.parent.mkdir(parents=True)
    path.write_text('{}')
    monkeypatch.setattr(pilot, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='fingerprint'):
        pilot.prepare(tmp_path / 'runtime', CASE)
    assert not (tmp_path / 'runtime').exists()


def test_doctor_is_read_only_and_reports_no_secret(tmp_path):
    key_file = environment(tmp_path)
    runtime = tmp_path / 'missing-runtime'
    result = pilot.doctor(runtime, CASE, key_file)
    assert result['read_only'] and result['key_present']
    assert result['external_requests'] == 0 and not runtime.exists()
    assert KEY not in json.dumps(result)


@pytest.mark.parametrize('contents,mode', [
    ('GEMINI_API_KEY=' + KEY + '\n', 0o644),
    ('GEMINI_API_KEY=' + KEY + '\nDATABASE_URL=private\n', 0o600),
    ('OTHER_KEY=' + KEY + '\n', 0o600),
    ('GEMINI_API_KEY=not a supported key\n', 0o600),
])
def test_explicit_environment_rejects_unsafe_mode_or_entries(tmp_path, contents, mode):
    path = tmp_path / 'environment.env'
    path.write_text(contents)
    path.chmod(mode)
    with pytest.raises(ValueError):
        pilot.environment_key(path)


def test_environment_symlink_is_rejected(tmp_path):
    path = environment(tmp_path)
    symlink = tmp_path / 'linked.env'
    symlink.symlink_to(path)
    with pytest.raises(OSError):
        pilot.environment_key(symlink)


def test_empty_key_can_be_inspected_but_cannot_dispatch(tmp_path):
    key_file = environment(tmp_path, '')
    assert not pilot.doctor(tmp_path / 'runtime', CASE, key_file)['key_present']
    with pytest.raises(ValueError, match='no API key'):
        pilot.run(tmp_path / 'runtime', CASE, key_file, True)


@pytest.mark.parametrize('quote', ['"', "'"])
def test_environment_accepts_matched_quotes_without_shell_evaluation(tmp_path, quote):
    key_file = environment(tmp_path, quote + KEY + quote)
    assert pilot.environment_key(key_file) == KEY


def test_environment_accepts_dotted_auth_keys_but_rejects_header_newlines(tmp_path):
    dotted = 'private.auth_fixture_key.signature_1234567890'
    key_file = environment(tmp_path, dotted)
    assert pilot.environment_key(key_file) == dotted
    key_file.write_text('GEMINI_API_KEY=' + dotted + '\nInjected: value\n')
    with pytest.raises(ValueError):
        pilot.environment_key(key_file)


def test_prepare_is_immutable_and_does_not_send(tmp_path):
    runtime = tmp_path / 'runtime'
    first = pilot.prepare(runtime, CASE)
    assert pilot.prepare(runtime, CASE) == first
    assert not (runtime / 'dispatch.json').exists()
    (runtime / CASE / 'request.json').write_text('{}')
    with pytest.raises(ValueError, match='Immutable'):
        pilot.prepare(runtime, CASE)


def test_paid_or_unconfirmed_dispatch_is_refused_before_key_read(tmp_path):
    with pytest.raises(ValueError, match='free-tier-confirmed'):
        pilot.run(tmp_path / 'runtime', CASE, tmp_path / 'nonexistent', False)
    assert not (tmp_path / 'runtime').exists()


def test_one_call_is_prepared_and_captured_durably_without_secret(tmp_path):
    runtime = tmp_path / 'runtime'
    key_file = environment(tmp_path)
    calls = []

    def send(request, key):
        assert (runtime / CASE / 'request.json').exists()
        assert (runtime / CASE / 'prepared.json').exists()
        assert (runtime / 'dispatch.json').exists()
        assert key == KEY
        calls.append(request)
        return 200, response(), True

    first = pilot.run(runtime, CASE, key_file, True, send)
    second = pilot.run(runtime, CASE, key_file, True, send)
    assert len(calls) == 1 and first == second
    assert first['dispatch_status'] == 'captured'
    assert first['proposal_status'] == 'structurally_valid_not_verified'
    assert first['repair_outcome'] == 'not_verified'
    assert not first['retry_permitted']
    for path in runtime.rglob('*'):
        if path.is_file():
            assert KEY.encode() not in path.read_bytes()
    with pytest.raises(ValueError, match='one permitted dispatch'):
        pilot.run(runtime, 'pytest-dev__pytest-6197', key_file, True, send)
    assert len(calls) == 1


@pytest.mark.parametrize('status,expected', [(429, 'quota_rejected'),
    (401, 'provider_rejected'), (503, 'unknown_dispatch')])
def test_provider_rejections_never_retry_or_fall_back(tmp_path, status, expected):
    runtime = tmp_path / 'runtime'
    key_file = environment(tmp_path)
    calls = []

    def send(request, key):
        calls.append(request)
        return status, b'{"error":{"message":"captured provider fixture"}}', True

    result = pilot.run(runtime, CASE, key_file, True, send)
    assert result['dispatch_status'] == expected
    assert pilot.run(runtime, CASE, key_file, True, send) == result
    assert len(calls) == 1


def test_network_uncertainty_remains_unknown_and_error_does_not_leak_key(tmp_path):
    key_file = environment(tmp_path)
    runtime = tmp_path / 'runtime'
    calls = []

    def send(request, key):
        calls.append(request)
        raise TimeoutError('Secret accidentally present in exception: ' + key)

    result = pilot.run(runtime, CASE, key_file, True, send)
    assert result['dispatch_status'] == 'unknown_dispatch'
    assert result['error_type'] == 'TimeoutError'
    assert KEY not in json.dumps(result)
    assert pilot.run(runtime, CASE, key_file, True, send) == result
    assert len(calls) == 1


def test_crash_after_claim_cannot_dispatch_again(tmp_path):
    runtime = tmp_path / 'runtime'
    pilot.prepare(runtime, CASE)
    pilot.durable_create(runtime / 'dispatch.json', pilot.canonical({'case_id': CASE}))
    calls = []
    result = pilot.run(runtime, CASE, tmp_path / 'no-key', True,
                       lambda *arguments: calls.append(arguments))
    assert result['dispatch_status'] == 'unknown_dispatch'
    assert not calls


def test_crash_after_response_capture_continues_without_execution(tmp_path):
    runtime = tmp_path / 'runtime'
    pilot.prepare(runtime, CASE)
    pilot.durable_create(runtime / 'dispatch.json', pilot.canonical({'case_id': CASE}))
    raw = response()
    pilot.capture_file(runtime / CASE / 'response.bin', raw)
    pilot.capture_file(runtime / CASE / 'response.json', pilot.canonical({
        'http_status': 200, 'response_sha256': pilot.sha(raw), 'complete': True,
        'elapsed_seconds': 1.25, 'captured_at': '2026-10-13T00:00:00+00:00'}))
    calls = []
    result = pilot.run(runtime, CASE, tmp_path / 'no-key', True,
                       lambda *arguments: calls.append(arguments))
    assert result['dispatch_status'] == 'captured'
    assert result['elapsed_seconds'] == 1.25 and not calls


def test_complete_invalid_response_is_captured_but_not_verified(tmp_path):
    result = pilot.run(tmp_path / 'runtime', CASE, environment(tmp_path), True,
                       lambda *arguments: (200, b'{"candidates":[]}', True))
    assert result['dispatch_status'] == 'captured'
    assert result['proposal_status'] == 'invalid_response'
    assert result['repair_outcome'] == 'not_verified'


def test_bad_edit_ranges_and_overlap_are_rejected():
    source, _ = pilot.source_input(CASE)
    block = source['source_blocks'][0]
    edit = {'source_id': block['source_id'], 'start_line': 1, 'end_line': 1, 'new': 'pass\n'}
    with pytest.raises(ValueError, match='captured source'):
        pilot.parse_action(response({'action': 'propose_patch', 'edits': [edit]}), source)
    edit.update(start_line=27, end_line=27)
    with pytest.raises(ValueError, match='overlapping'):
        pilot.parse_action(response({'action': 'propose_patch', 'edits': [edit, edit]}), source)


def test_http_transport_is_single_fixed_host_call_with_bounded_output(monkeypatch):
    original = httpx.Client
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url) == pilot.ENDPOINT
        assert request.headers['x-goog-api-key'] == KEY
        assert 'key=' not in str(request.url)
        return httpx.Response(200, content=b'x' * (pilot.MAX_RESPONSE_BYTES + 1))

    def client(**options):
        assert options == {'timeout': 60, 'follow_redirects': False, 'trust_env': False}
        return original(**options, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(httpx, 'Client', client)
    status, raw, complete = pilot.transport({'contents': []}, KEY)
    assert status == 200 and len(raw) == pilot.MAX_RESPONSE_BYTES
    assert not complete and len(calls) == 1


def test_concurrent_run_cannot_duplicate_dispatch(tmp_path):
    key_file = environment(tmp_path)
    runtime = tmp_path / 'runtime'
    began = threading.Event()
    finish = threading.Event()
    calls = []
    results = []

    def send(request, key):
        calls.append(request)
        began.set()
        assert finish.wait(5)
        return 200, response(), True

    first = threading.Thread(target=lambda: results.append(
        pilot.run(runtime, CASE, key_file, True, send)))
    first.start()
    assert began.wait(5)
    second = pilot.run(runtime, CASE, key_file, True, send)
    finish.set()
    first.join(5)
    assert not first.is_alive() and len(calls) == 1
    assert second['dispatch_status'] == 'unknown_dispatch'
    assert results[0]['dispatch_status'] == 'captured'


def test_model_specific_thinking_setting_is_supported():
    request,_,_=pilot.request_for('django__django-11066')
    assert request['generationConfig']['thinkingConfig']['thinkingLevel']=='LOW'
