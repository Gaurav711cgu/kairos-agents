"""Hosted-model repair runs: provider client, credentials and run wiring, with a fake transport (no network)."""
import io
import json
import urllib.error

import pytest

import scripts.hosted_repair as hosted


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def transport(*outcomes):
    sent = []

    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        outcome = outcomes[len(sent) - 1]
        if isinstance(outcome, int):
            raise urllib.error.HTTPError(request.full_url, outcome, 'busy', {}, io.BytesIO(b'{}'))
        return Reply(json.dumps(outcome).encode())
    urlopen.sent = sent
    return urlopen


def completion(text, finish='stop'):
    return {'model': 'm', 'choices': [{'message': {'content': text}, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 7, 'completion_tokens': 3}}


def test_generate_sends_the_messages_and_keeps_only_the_answer():
    urlopen = transport(completion('<think>plan</think>\nRUN\n```python\nprint(1)\n```'))
    generate = hosted.client('nvidia', 'vendor/model', key='k', urlopen=urlopen, sleep=lambda s: None)
    result = generate([{'role': 'user', 'content': 'fix'}], 0, {'do_sample': False, 'seed': 42})
    assert result['text'] == 'RUN\n```python\nprint(1)\n```' and result['ended_with_eos'] is True
    assert (result['input_tokens'], result['output_tokens']) == (7, 3)
    body = urlopen.sent[0]
    assert body['model'] == 'vendor/model' and body['messages'][0]['content'] == 'fix' and body['temperature'] == 0.0


def test_busy_provider_is_retried_but_a_bad_request_is_not():
    urlopen = transport(429, 503, completion('ok'))
    generate = hosted.client('nvidia', 'm', key='k', urlopen=urlopen, sleep=lambda s: None)
    assert generate([], 0, {})['text'] == 'ok' and len(urlopen.sent) == 3
    generate = hosted.client('nvidia', 'm', key='k', urlopen=transport(400), sleep=lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        generate([], 0, {})


def test_credentials_come_from_the_private_file_without_overriding_the_environment(tmp_path, monkeypatch):
    env = tmp_path / 'provider.env'
    env.write_text('NVIDIA_API_KEY=nvapi-file\n# comment\nOPENROUTER_API_KEY=sk-or-file\n')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-or-shell')
    monkeypatch.delenv('NVIDIA_API_KEY', raising=False)
    hosted.load_env(env)
    assert hosted.api_key('nvidia') == 'nvapi-file' and hosted.api_key('openrouter') == 'sk-or-shell'


def test_missing_key_names_the_variable_never_a_value(monkeypatch):
    monkeypatch.delenv('NVIDIA_API_KEY', raising=False)
    with pytest.raises(SystemExit, match='NVIDIA_API_KEY'):
        hosted.api_key('nvidia')


def test_run_uses_the_container_sandbox_and_the_hosted_budget(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(hosted, 'run_chains', lambda package, output, generate, **kw: seen.update(kw) or {'status': 'complete'})
    package = {'chains': [{'chain_id': f'dev/c/{n}'} for n in range(3)]}
    assert hosted.run(package, tmp_path, generate=lambda *a: None) == {'status': 'complete'}
    assert seen['host_checks'] is True and seen['envelope_tokens'] == hosted.HOSTED_ENVELOPE_TOKENS
    assert seen['call_cap'] == 3 * hosted.MAX_CALLS_PER_CHAIN
    workspace_args = {}
    monkeypatch.setattr(hosted, 'fetch_dev_source', lambda chain, directory, **kw: workspace_args.update(kw))
    seen['prepare_dev']({'chain_id': 'dev/c/0'}, tmp_path)
    assert workspace_args['run_python'] == str(hosted.SANDBOX_PYTHON) and hosted.SANDBOX_PYTHON.exists()
