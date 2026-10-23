"""F025 probe runner: journaled multi-turn chains with scripted (mock) generations; no GPU, model or network.

Scripted replies are the task author's reference fixes; passing proves runner mechanics, never model skill.
"""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile

import pytest

from scripts.f024_colab import digest
from scripts.f025_colab import (ENVELOPE_TOKENS, MAX_NEW, PACKAGE_CALL_CAP, bundle, build_package, canonical,
                                dev_chains_from_f024, fetch_dev_source, notebook, run_chains, validate_package)
from scripts.f025_tasks import TASKS

SHA = 'a' * 40
SOURCE = 'import os\n\n\ndef add(a, b):\n    return a - b\n'


def publish(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def scripted(*replies):
    calls = []

    def generate(messages, call_index, sampling=None):
        calls.append((call_index, [dict(m) for m in messages]))
        return {'text': replies[call_index], 'input_tokens': 10, 'output_tokens': 5, 'ended_with_eos': True,
                'peak_reserved_bytes': 0}
    generate.calls = calls
    return generate


def one(task=TASKS[0]):
    return build_package([task])


def test_accepted_chain_is_journaled_and_hash_bound(tmp_path):
    package, generate = one(), scripted(TASKS[0]['reference'])
    summary = run_chains(package, tmp_path, generate, publish=publish, host_checks=True)
    assert summary == {'status': 'complete', 'chains': 1, 'synthetic_check_passed': 1, 'dev_static_accepted': 0, 'calls': 1, 'training_runs': 0}
    intent = json.loads((tmp_path / 'intents/synthetic/p1-constant/c0.json').read_text())
    capture = json.loads((tmp_path / 'captures/synthetic/p1-constant/c0.json').read_text())
    messages_sha = digest(generate.calls[0][1])
    assert intent['binding'] == capture['binding'] == digest(package)
    assert intent['messages_sha256'] == capture['messages_sha256'] == messages_sha
    assert capture['capture_sha256'] == digest({k: v for k, v in capture.items() if k != 'capture_sha256'})
    assert set(capture['result']) == {'text', 'input_tokens', 'output_tokens', 'ended_with_eos', 'peak_reserved_bytes'}
    record = json.loads((tmp_path / 'chains/synthetic/p1-constant.json').read_text())
    assert record['status'] == 'accepted' and record['calls'] == 1 and '+KB = 1024' in record['patch']
    assert record['final_reply'] == TASKS[0]['reference']
    assert record['regions'] == [{'path': 'pkg/units.py', 'start_line': 1, 'end_line': 5}]
    receipts = (tmp_path / 'receipts/synthetic/p1-constant.jsonl').read_bytes()
    assert record['receipts_sha256'] == hashlib.sha256(receipts).hexdigest()
    assert record['record_sha256'] == digest({k: v for k, v in record.items() if k != 'record_sha256'})


def test_rejected_then_fixed_uses_two_calls(tmp_path):
    generate = scripted('no blocks here', TASKS[0]['reference'])
    summary = run_chains(one(), tmp_path, generate, publish=publish, host_checks=True)
    assert summary['synthetic_check_passed'] == 1 and summary['calls'] == 2
    assert [i for i, _ in generate.calls] == [0, 1] and len(generate.calls[1][1]) == 4
    assert (tmp_path / 'captures/synthetic/p1-constant/c1.json').exists()


def test_envelope_stops_the_chain_without_dispatch_or_truncation(tmp_path):
    generate = scripted('no blocks here', TASKS[0]['reference'])
    count = lambda messages: 10 if len(messages) == 2 else ENVELOPE_TOKENS - MAX_NEW + 1
    summary = run_chains(one(), tmp_path, generate, publish=publish, count_tokens=count, host_checks=True)
    record = json.loads((tmp_path / 'chains/synthetic/p1-constant.json').read_text())
    assert record['status'] == 'envelope' and record['calls'] == 1 and record['patch'] is None
    assert summary['synthetic_check_passed'] == 0 and len(generate.calls) == 1
    assert not (tmp_path / 'intents/synthetic/p1-constant/c1.json').exists()


def test_generation_error_halts_and_preserves_capture(tmp_path):
    def generate(messages, call_index, sampling=None):
        raise RuntimeError('CUDA out of memory')
    package = build_package(TASKS[:2])
    with pytest.raises(RuntimeError, match='halted'):
        run_chains(package, tmp_path, generate, publish=publish, host_checks=True)
    capture = json.loads((tmp_path / 'captures/synthetic/p1-constant/c0.json').read_text())
    assert capture['status'] == 'generation_error' and 'out of memory' in capture['error']
    assert not (tmp_path / 'chains').exists() and not (tmp_path / 'intents/synthetic/p2-insert-import').exists()
    with pytest.raises(ValueError, match='failure preserved'):
        run_chains(package, tmp_path, scripted(TASKS[0]['reference']), publish=publish, host_checks=True)


def test_intent_without_capture_refuses_before_any_dispatch(tmp_path):
    def interrupted(messages, call_index, sampling=None):
        raise KeyboardInterrupt  # the process died mid-dispatch
    with pytest.raises(KeyboardInterrupt):
        run_chains(one(), tmp_path, interrupted, publish=publish, host_checks=True)
    generate = scripted(TASKS[0]['reference'])
    with pytest.raises(ValueError, match='Uncertain dispatch'):
        run_chains(one(), tmp_path, generate, publish=publish, host_checks=True)
    assert generate.calls == []


def test_tampered_capture_is_refused(tmp_path):
    run_chains(one(), tmp_path, scripted('no blocks here', TASKS[0]['reference']), publish=publish, host_checks=True)
    path = tmp_path / 'captures/synthetic/p1-constant/c0.json'
    saved = json.loads(path.read_text())
    saved['result']['text'] = 'edited'
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='hash'):
        run_chains(one(), tmp_path, scripted(), publish=publish, host_checks=True)


def test_completed_chains_are_skipped_on_rerun(tmp_path):
    first = run_chains(one(), tmp_path, scripted(TASKS[0]['reference']), publish=publish, host_checks=True)
    generate = scripted()
    assert run_chains(one(), tmp_path, generate, publish=publish, host_checks=True) == first and generate.calls == []


def test_package_rules():
    package = build_package(TASKS)
    validate_package(package)
    with pytest.raises(ValueError, match='pinned'):
        validate_package({**package, 'base_revision': 'main'})
    with pytest.raises(ValueError, match='unique'):
        validate_package({**package, 'chains': package['chains'] + package['chains'][:1]})
    many = [{**package['chains'][0], 'chain_id': f'synthetic/t{i}'} for i in range(PACKAGE_CALL_CAP // 6 + 1)]
    with pytest.raises(ValueError, match='call cap'):
        validate_package({**package, 'chains': many})
    with pytest.raises(ValueError, match='dev chain'):
        validate_package({**package, 'chains': [dev_chain(base_commit='main')]})
    with pytest.raises(ValueError, match='dev chain'):
        validate_package({**package, 'chains': [dev_chain(repo='evil/repo')]})
    validate_package({**package, 'chains': [dev_chain()]})


def test_reference_fix_never_enters_the_package():
    text = canonical(build_package(TASKS)).decode()
    for task in TASKS:
        assert task['reference'] not in text
    for task in [t for t in TASKS if t['kind'] == 'R']:
        replace = task['reference'].split('=======\n')[1].split('>>>>>>>')[0]
        assert json.dumps(replace)[1:-1] not in text


def dev_chain(text=SOURCE, base_commit=SHA, repo='django/django'):
    return {'chain_id': 'dev/django__django-1/oracle', 'instance_id': 'django__django-1', 'repo': repo,
            'base_commit': base_commit, 'issue': 'add(2, 3) should be 5',
            'regions': [{'path': 'django/value.py', 'start_line': 1, 'end_line': 5, 'text': text}]}


def test_dev_chains_come_from_the_f024_oracle_base_turn_one_job(tmp_path):
    numbered = ''.join(f'{n}: {line}' for n, line in enumerate(SOURCE.splitlines(True), 1))
    user = {'issue': 'add(2, 3) should be 5', 'protocol': 'p',
            'original_source': [{'path': 'django/value.py', 'start_line': 1, 'end_line': 5, 'source_id': 'S1',
                                 'numbered_original_source': numbered}]}
    jobs = [{'job_id': f'django__django-1/{c}/{a}/t1', 'instance_id': 'django__django-1', 'context': c, 'arm': a, 'turn': 1,
             'messages': [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': json.dumps(user if c == 'oracle' else {})}]}
            for c in ['issue', 'oracle'] for a in ['base', 'adapter']]
    path = tmp_path / 'f024.json'
    path.write_text(json.dumps({'jobs': jobs}))
    assert dev_chains_from_f024(path, {'django__django-1': SHA}) == [dev_chain()]


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


def tarball(files, top=f'django-{SHA}'):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, text in files.items():
            info = tarfile.TarInfo(f'{top}/{name}')
            info.size = len(text.encode())
            archive.addfile(info, io.BytesIO(text.encode()))
    return buffer.getvalue()


def opener(data):
    seen = []

    def open_url(url, timeout=None):
        seen.append(url)
        return Response(data, url)
    open_url.seen = seen
    return open_url


def test_fetch_dev_source_verifies_regions_and_runs_a_static_chain(tmp_path):
    fake = opener(tarball({'django/value.py': SOURCE, 'docs/notes.txt': 'not extracted\n'}))
    chain = dev_chain()
    package = {**build_package([]), 'chains': [chain]}
    reply = 'django/value.py\n<<<<<<< SEARCH\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE\n'
    summary = run_chains(package, tmp_path / 'out', scripted(reply), publish=publish,
                         prepare_dev=lambda c, d: fetch_dev_source(c, d, opener=fake))
    assert fake.seen == [f'https://codeload.github.com/django/django/tar.gz/{SHA}'] and summary['dev_static_accepted'] == 1
    record = json.loads((tmp_path / 'out/chains/dev/django__django-1/oracle.json').read_text())
    assert '+    return a + b' in record['patch']


def test_fetch_dev_source_refuses_mismatch_traversal_and_redirect(tmp_path):
    with pytest.raises(ValueError, match='region'):
        fetch_dev_source(dev_chain(text='different\n' * 5), tmp_path / 'a',
                         opener=opener(tarball({'django/value.py': SOURCE})))
    with pytest.raises(ValueError, match='traversal'):
        fetch_dev_source(dev_chain(), tmp_path / 'b', opener=opener(tarball({'django/value.py': SOURCE, '../evil.py': 'x'})))
    assert not (tmp_path / 'evil.py').exists()

    def redirected(url, timeout=None):
        return Response(tarball({'django/value.py': SOURCE}), 'https://example.com/other')
    with pytest.raises(ValueError, match='redirect'):
        fetch_dev_source(dev_chain(), tmp_path / 'c', opener=redirected)


def test_bundle_runs_a_chain_without_project_dependencies(tmp_path):
    hashes = bundle(tmp_path)
    code = tmp_path / 'f025-code.zip'
    assert hashes['f025-code.zip'] == hashlib.sha256(code.read_bytes()).hexdigest()
    assert bundle(tmp_path / 'again')['f025-code.zip'] == hashes['f025-code.zip']  # reproducible bytes
    with zipfile.ZipFile(code) as archive:
        archive.extractall(tmp_path / 'x')
    shim = (tmp_path / 'x/kairos_api/model_runtime.py').read_text()
    assert 'def digest' in shim and 'import httpx' not in shim
    script = ("import sys, json, tempfile\nsys.modules['httpx'] = None\nsys.path.insert(0, sys.argv[1])\n"
              'from scripts.f025_colab import build_package, run_chains\nfrom scripts.f025_tasks import TASKS\n'
              'reply = lambda m, i, s=None: {"text": TASKS[0]["reference"], "input_tokens": 1, "output_tokens": 1, '
              '"ended_with_eos": True, "peak_reserved_bytes": 0}\n'
              'print(json.dumps(run_chains(build_package(TASKS[:1]), tempfile.mkdtemp(), reply, host_checks=True)))\n')
    done = subprocess.run([sys.executable, '-I', '-c', script, str(tmp_path / 'x')], capture_output=True, text=True,
                          cwd=tmp_path, timeout=60)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.splitlines()[-1])['synthetic_check_passed'] == 1


def test_notebook_pins_hashes_and_one_bounded_run():
    cells = notebook('p' * 64, 'b' * 64, 'm' * 64)['cells']
    text = '\n'.join(''.join(c['source']) for c in cells)
    assert 'p' * 64 in text and 'b' * 64 in text and 'm' * 64 in text and 'peft' not in text
    assert 'python -m scripts.f025_colab --package' in text and '/content/f025-results' in text


def test_synthetic_checks_refuse_to_run_without_the_disposable_vm_flag(tmp_path):
    with pytest.raises(ValueError, match='disposable VM'):
        run_chains(one(), tmp_path, scripted(TASKS[0]['reference']))


def test_stale_record_from_another_package_is_refused(tmp_path):
    run_chains(one(), tmp_path, scripted(TASKS[0]['reference']), host_checks=True)
    other = {**one(), 'chains': [{**one()['chains'][0], 'issue': 'changed'}]}
    with pytest.raises(ValueError, match='Prior capture binding'):  # journal preflight refuses first
        run_chains(other, tmp_path, scripted(TASKS[0]['reference']), host_checks=True)
    import shutil
    shutil.rmtree(tmp_path / 'captures'), shutil.rmtree(tmp_path / 'intents')  # isolate the record check
    with pytest.raises(ValueError, match='another package'):
        run_chains(other, tmp_path, scripted(TASKS[0]['reference']), host_checks=True)


def with_symlink(data, name, target, top=f'django-{SHA}'):
    """Re-pack ``data`` with one extra symlink member."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(data)) as source, tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for member in source.getmembers():
            archive.addfile(member, source.extractfile(member))
        link = tarfile.TarInfo(f'{top}/{name}')
        link.type, link.linkname = tarfile.SYMTYPE, target
        archive.addfile(link)
    return buffer.getvalue()


def test_relative_symlinks_outside_the_package_are_ignored(tmp_path):
    # real django@6c9778a5 ships docs/_theme/djangodocs-epub/static/*.png -> ../../djangodocs/static/...
    data = with_symlink(tarball({'django/value.py': SOURCE}), 'docs/_theme/a.png', '../../other/a.png')
    w = fetch_dev_source(dev_chain(), tmp_path / 'a', opener=opener(data))
    w.close()
    escaping = with_symlink(tarball({'django/value.py': SOURCE}), 'django/link.py', '../../etc/passwd')
    with pytest.raises(ValueError, match='traversal'):
        fetch_dev_source(dev_chain(), tmp_path / 'b', opener=opener(escaping))


def test_fetch_dev_source_extracts_visible_test_roots_read_only(tmp_path):
    data = with_symlink(tarball({'django/value.py': SOURCE, 'tests/test_value.py': 'def test_add():\n    pass\n',
                                 'docs/notes.txt': 'x\n'}), 'tests/link.py', 'test_value.py')
    w = fetch_dev_source(dev_chain(), tmp_path / 'a', opener=opener(data))
    try:
        assert w.case['test_roots'] == ['tests/'] and w.case['python_paths'] == ['.']
        assert (w.root / 'tests/test_value.py').is_file() and not (w.root / 'docs').exists()
        assert not (w.root / 'tests/link.py').exists()  # links under test roots are skipped, never followed
    finally:
        w.close()
    chain = {**dev_chain(repo='pytest-dev/pytest'), 'chain_id': 'dev/pytest-dev__pytest-1/oracle', 'instance_id': 'pytest-dev__pytest-1',
             'regions': [{**dev_chain()['regions'][0], 'path': 'src/_pytest/value.py'}]}
    data = tarball({'src/_pytest/value.py': SOURCE, 'testing/test_value.py': 'x = 1\n'}, top=f'pytest-{SHA}')
    w = fetch_dev_source(chain, tmp_path / 'b', opener=opener(data))
    try:
        assert w.case['test_roots'] == ['testing/'] and w.case['python_paths'] == ['src']
        assert (w.root / 'testing/test_value.py').is_file()
    finally:
        w.close()


def test_run_chains_allows_run_only_with_host_checks(tmp_path):
    run = 'RUN\n```python\nprint("probe", 6 * 7)\n```'
    generate = scripted(run, TASKS[0]['reference'])
    run_chains(one(), tmp_path / 'a', generate, publish=publish, host_checks=True)
    assert 'exit 0' in generate.calls[1][1][-1]['content'] and 'probe 42' in generate.calls[1][1][-1]['content']
    fake = opener(tarball({'django/value.py': SOURCE}))
    reply = 'django/value.py\n<<<<<<< SEARCH\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE\n'
    generate = scripted(run, reply)
    run_chains({**build_package([]), 'chains': [dev_chain()]}, tmp_path / 'b', generate, publish=publish,
               prepare_dev=lambda c, d: fetch_dev_source(c, d, opener=fake))
    assert 'RUN refused: no disposable VM' in generate.calls[1][1][-1]['content']


def gold(hunks):
    """A gold patch on django/value.py with one single-line hunk per listed old line."""
    body = ''.join(f'@@ -{n},1 +{n},1 @@\n-x\n+GOLD_ADDED_{n}\n' for n in hunks)
    return f'diff --git a/django/value.py b/django/value.py\n--- a/django/value.py\n+++ b/django/value.py\n{body}'


def test_dev_chains_from_cases_places_oracle_regions(tmp_path):
    from scripts.f025_colab import dev_chains_from_cases
    row = {'instance_id': 'django__django-1', 'repo': 'django/django', 'base_commit': SHA, 'problem_statement': 'add is wrong',
           'patch': gold([5])}
    [chain] = dev_chains_from_cases([row], tmp_path, opener=opener(tarball({'django/value.py': SOURCE})))
    assert chain['chain_id'] == 'dev/django__django-1/oracle' and chain['issue'] == 'add is wrong'
    [region] = chain['regions']
    assert (region['path'], region['start_line'], region['end_line']) == ('django/value.py', 1, 5)
    assert region['text'] == SOURCE and 'GOLD_ADDED' not in json.dumps(chain)


def test_case_with_gold_outside_regions_is_excluded(tmp_path):
    from scripts.f025_colab import dev_chains_from_cases
    source = ''.join(f'line_{n} = {n}\n' for n in range(1, 200))
    row = {'instance_id': 'django__django-2', 'repo': 'django/django', 'base_commit': SHA, 'problem_statement': 'p',
           'patch': gold([10, 40, 70, 100, 130])}
    assert dev_chains_from_cases([row], tmp_path, opener=opener(tarball({'django/value.py': source}))) == []


def test_samples_expand_dev_chains():
    chains = [dev_chain()]
    ids = [c['chain_id'] for c in build_package([], chains, samples=2)['chains']]
    assert ids == ['dev/django__django-1/oracle-s0', 'dev/django__django-1/oracle-s1']
    assert [c['chain_id'] for c in build_package([], chains)['chains']] == ['dev/django__django-1/oracle']


def test_call_cap_is_80():
    from scripts.f025_colab import MAX_CALLS_PER_CHAIN
    chain = dev_chain()
    ten = {**build_package([]), 'chains': [{**chain, 'chain_id': f'dev/django__django-{n}/oracle', 'instance_id': f'django__django-{n}'} for n in range(10)]}
    assert len(validate_package(ten)) == 10 and MAX_CALLS_PER_CHAIN == 8
    with pytest.raises(ValueError, match='call cap'):
        validate_package({**ten, 'chains': ten['chains'] + [{**chain, 'chain_id': 'dev/django__django-99/oracle', 'instance_id': 'django__django-99'}]})


def test_sampling_differs_per_sample_and_call():
    from scripts.f025_colab import sampling_for
    assert sampling_for(0, 0) == {'do_sample': False, 'seed': 42}
    assert sampling_for(1, 0) == {'do_sample': True, 'temperature': 0.8, 'top_p': 0.95, 'seed': 1042}
    assert sampling_for(0, 2)['do_sample'] and sampling_for(0, 2)['seed'] == 44



def test_django_workspace_gets_the_pinned_run_environment(tmp_path):
    from scripts.f025_colab import RUN_ENVS
    w = fetch_dev_source(dev_chain(), tmp_path / 'a', opener=opener(tarball({'django/value.py': SOURCE})))
    w.close()
    assert w.case['run_python'] == RUN_ENVS['django/django']['python'] and 'django.setup()' in w.case['run_prelude']


def test_notebook_builds_the_python38_run_environment():
    cells = ''.join(''.join(c['source']) for c in notebook('a' * 64, 'b' * 64, 'c' * 64)['cells'])
    assert 'uv venv -p 3.8 /content/run-env-django' in cells and 'asgiref==3.2.10' in cells and 'sqlparse==0.4.4' in cells


def test_django_prelude_gives_script_models_an_app_and_a_table():
    """Real Django only: KAIROS_RUN_DJANGO_PYTHON (asgiref/pytz/sqlparse) and KAIROS_DJANGO_SOURCE (a pinned checkout)."""
    import os
    from scripts.f025_colab import DJANGO_PRELUDE
    from scripts.repair_loop025 import _execute
    python, source = os.environ.get('KAIROS_RUN_DJANGO_PYTHON'), os.environ.get('KAIROS_DJANGO_SOURCE')
    if not (python and source):
        pytest.skip('needs a Django interpreter and source checkout')
    script = ('from django.db import models\n\n\nclass Article(models.Model):\n    slug = models.CharField(max_length=9)\n\n\n'
              "class Tagged(models.Model):\n    name = models.CharField(max_length=9)\n\n    class Meta:\n        app_label = 'auth'\n\n\n"
              "Article.objects.create(slug='a'); Tagged.objects.create(name='t')\n"
              "from django.contrib.auth.models import User\nprint(Article._meta.label, Article.objects.count(), Tagged.objects.count(), User.objects.count())\n")
    code, output = _execute('import sys\nsys.path.insert(0, ".")\n' + DJANGO_PRELUDE + script, source, 30, python)
    assert (code, output.strip()) == (0, 'repro.Article 1 1 0')
