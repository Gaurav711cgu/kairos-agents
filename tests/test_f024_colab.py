"""F024 runner journal and package rules with mocked generations; no GPU, Colab or model."""
import json

import pytest

from scripts.f024_colab import BASE, REVISION, VERSION, digest, notebook, run_jobs, validate_package


def job(case='django__django-1', context='issue', arm='base', turn=1, tokens=2000, max_new=512, content='u'):
    messages = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': content}]
    j = {'job_id': f'{case}/{context}/{arm}/t{turn}', 'instance_id': case, 'context': context, 'arm': arm, 'turn': turn,
         'messages': messages, 'prompt_tokens': tokens, 'max_new_tokens': max_new, 'prompt_token_ids_sha256': 'x' * 64}
    if turn == 2:
        j.update(parent_job_id=f'{case}/{context}/{arm}/t1', parent_capture_sha256='c' * 64)
    return j


def package(jobs):
    return {'version': VERSION, 'base_model': BASE, 'base_revision': REVISION, 'jobs': jobs,
            'bindings': {'adapter_binding': 'a' * 64, 'model_manifest': 'b' * 64}}


def paired():
    return package([job(arm='base'), job(arm='adapter')])


def publish(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_package_rules_refuse_unsafe_jobs():
    validate_package(paired())
    with pytest.raises(ValueError, match='envelope'):
        validate_package(package([job(arm='base', tokens=3100), job(arm='adapter', tokens=3100)]))
    with pytest.raises(ValueError, match='pair'):
        validate_package(package([job(arm='base'), job(arm='adapter', content='different')]))
    with pytest.raises(ValueError, match='pinned'):
        validate_package({**paired(), 'base_revision': 'main'})
    with pytest.raises(ValueError, match='unique'):
        validate_package(package([job(), job()]))
    validate_package(package([job(arm='adapter', turn=2)]))  # turn two exists only for a rejected arm
    orphan = job(arm='adapter', turn=2)
    del orphan['parent_capture_sha256']
    with pytest.raises(ValueError, match='parent'):
        validate_package(package([orphan]))
    with pytest.raises(ValueError, match='identity'):
        validate_package(package([job(case='../../escape', arm='base'), job(case='../../escape', arm='adapter')]))
    with pytest.raises(ValueError, match='bindings'):
        validate_package({**paired(), 'bindings': {}})


def test_journal_captures_then_resumes_without_redispatch(tmp_path):
    calls = []
    generate = lambda j: calls.append(j['job_id']) or {'text': '{}', 'output_tokens': 2}
    assert run_jobs(paired(), tmp_path, generate, publish)['captures'] == 2
    assert run_jobs(paired(), tmp_path, lambda j: pytest.fail('captured job redispatched'), publish)['captures'] == 2
    assert len(calls) == 2


def test_uncertain_dispatch_stops_everything(tmp_path):
    p = paired()
    publish(tmp_path / 'intents' / (p['jobs'][0]['job_id'] + '.json'), {'binding': digest(p), 'job_sha256': digest(p['jobs'][0])})
    with pytest.raises(ValueError, match='Uncertain dispatch'):
        run_jobs(p, tmp_path, lambda j: pytest.fail('no dispatch after uncertainty'), publish)


def test_generation_error_including_oom_is_captured_and_halts(tmp_path):
    def generate(j):
        raise MemoryError('CUDA out of memory')
    with pytest.raises(RuntimeError, match='halted'):
        run_jobs(paired(), tmp_path, generate, publish)
    captures = list((tmp_path / 'captures').glob('**/*.json'))
    assert len(captures) == 1 and json.loads(captures[0].read_text())['status'] == 'generation_error'
    with pytest.raises(ValueError, match='Prior generation failure'):
        run_jobs(paired(), tmp_path, lambda j: pytest.fail('no automatic continuation'), publish)


def test_notebook_binds_hashes_and_carries_no_secrets():
    cells = notebook('a' * 64, 'b' * 64, 'c' * 64, 'd' * 64, max_generations=16)
    text = json.dumps(cells)
    assert all(h * 64 in text for h in 'abcd') and '16' in text
    assert 'token=' not in text.replace('token=False', '') and 'HF_TOKEN' not in text


def test_journal_rejects_capture_without_intent_and_misattributed_captures(tmp_path):
    p = paired()
    run_jobs(p, tmp_path, lambda j: {'text': j['arm'], 'output_tokens': 1}, publish)
    base, adapter = (tmp_path / 'captures' / (j['job_id'] + '.json') for j in p['jobs'])
    adapter.write_text(base.read_text())  # base output copied onto the adapter path
    with pytest.raises(ValueError, match='differs'):
        run_jobs(p, tmp_path, lambda j: pytest.fail('no dispatch'), publish)
    (tmp_path / 'intents' / (p['jobs'][0]['job_id'] + '.json')).unlink()
    with pytest.raises(ValueError, match='intent'):
        run_jobs(p, tmp_path, lambda j: pytest.fail('no dispatch'), publish)


def test_journal_rejects_foreign_intent(tmp_path):
    p = paired()
    run_jobs(p, tmp_path, lambda j: {'text': 'x', 'output_tokens': 1}, publish)
    publish(tmp_path / 'intents' / (p['jobs'][0]['job_id'] + '.json'), {'binding': 'z' * 64, 'job_sha256': 'z' * 64})
    with pytest.raises(ValueError, match='intent'):
        run_jobs(p, tmp_path, lambda j: pytest.fail('no dispatch'), publish)


def test_runner_is_self_contained_for_hash_binding():
    import ast, pathlib
    tree = ast.parse(pathlib.Path('scripts/f024_colab.py').read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.startswith(('scripts', 'kairos_api')) for m in imported)
