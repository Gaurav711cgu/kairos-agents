"""F025 Colab probe runner: base model only, journaled multi-turn SEARCH/REPLACE repair chains.

Each model call inside ``repair_loop025.run_loop`` keeps the F024 journal semantics: an intent bound to
the package and the exact messages is published before dispatch and a hashed capture after it. An
intent without a capture is an uncertain dispatch and stops the run before any dispatch; a captured
error halts the run and is never retried; a 180 s hard deadline ends the process with evidence. A chain
that would exceed the observed T4 envelope stops with status ``envelope``; history is never truncated.
Interrupted chains replay their verified captures, so no call is made twice. Synthetic chains run their
visible check in a child interpreter; dev chains are static only and scored later in pinned Docker.
"""
import argparse
import hashlib
import inspect
import io
import json
import os
import re
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

try:
    from scripts.f024_colab import (BASE, ENVELOPE_TOKENS, PROFILE, REVISION, canonical, digest, hard_deadline,
                                    publish_atomic, token_ids)
except ImportError:  # run flat in Colab
    from f024_colab import (BASE, ENVELOPE_TOKENS, PROFILE, REVISION, canonical, digest, hard_deadline,
                            publish_atomic, token_ids)

VERSION = 'f025-probe-v1'
MAX_NEW = 768
MAX_CALLS_PER_CHAIN = 8  # hard cap shared by edits, corrections, FIND/READ and RUN turns
PACKAGE_CALL_CAP = 80  # 5 cases x 2 samples x 8 calls
HARD_DEADLINE_SECONDS = 180
MAX_ARCHIVE = 80 * 1024 * 1024
MAX_EXPANDED = 240 * 1024 * 1024
PREFIXES = {'django/django': 'django/', 'pytest-dev/pytest': 'src/_pytest/'}
TEST_ROOTS = {'django/django': 'tests/', 'pytest-dev/pytest': 'testing/'}  # base-commit tests, read-only for the model
PYTHON_PATHS = {'django/django': ['.'], 'pytest-dev/pytest': ['src']}
# RUN scripts need the interpreter the pinned scoring image uses: django 3.1 imports distutils, which Python 3.12
# (Colab) removed. Versions read from kairos-investigation-django:build003 (Python 3.8.20).
DJANGO_PRELUDE = (  # F025 run 5: 6 of 9 scripts died on app_label or a missing table before reaching the bug
    "import django\nfrom django.apps import AppConfig\nfrom django.conf import settings\n\n\n"
    "class Repro(AppConfig):  # models the script defines belong to this app\n"
    "    name, label, path = '__main__', 'repro', '.'\n\n\n"
    "settings.configure(SECRET_KEY='repro', USE_TZ=True, INSTALLED_APPS=['django.contrib.contenttypes', "
    "'django.contrib.auth', '__main__.Repro'], DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}, "
    "TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates'}])\ndjango.setup()\n"
    "from django.core.management import call_command\nfrom django.db import connection\n"
    "from django.db.models.signals import class_prepared\n"
    "call_command('migrate', run_syncdb=True, verbosity=0)\n\n\n"
    "def _create_table(sender, **kwargs):  # each model the script defines gets its table at once\n"
    "    if sender.__module__ == '__main__' and sender._meta.managed and not sender._meta.proxy:\n"
    "        try:\n"
    "            with connection.schema_editor() as editor:\n"
    "                editor.create_model(sender)\n"
    "        except Exception as error:\n"
    "            print('prelude: no table for %s: %s' % (sender.__name__, error))\n\n\n"
    "class_prepared.connect(_create_table)\n")
RUN_ENVS = {'django/django': {'python': '/content/run-env-django/bin/python', 'prelude': DJANGO_PRELUDE,
                              'packages': 'asgiref==3.2.10 pytz==2024.2 sqlparse==0.4.4'}}
SYNTHETIC = re.compile(r'synthetic/[a-z0-9-]+')
DEV = re.compile(r'dev/((django__django|pytest-dev__pytest)-[0-9]+)/oracle(-s[0-9])?')
ROOT = Path(__file__).resolve().parent.parent


class ChainStop(Exception):
    """Ends one chain without a dispatch (envelope or call cap); the run continues."""


def build_package(tasks, dev_cases=(), samples=1):
    if samples > 1:  # best-of-n: identical inputs, different seeds; the fair pick never sees hidden results
        dev_cases = [{**c, 'chain_id': f"{c['chain_id']}-s{k}", 'sample': k} for c in dev_cases for k in range(samples)]
    chains = [{'chain_id': 'synthetic/' + t['task_id'], 'kind': t['kind'], 'files': t['files'], 'issue': _prompt_issue(t),
               'regions': t['regions'], 'check': t['check']} for t in tasks]  # never t['reference']
    return {'version': VERSION, 'base_model': BASE, 'base_revision': REVISION, 'chains': chains + list(dev_cases)}


def _prompt_issue(task):
    try:
        from scripts.f025_tasks import prompt_issue
    except ImportError:
        from f025_tasks import prompt_issue
    return prompt_issue(task)


def dev_chains_from_f024(package_path, revisions):
    """Oracle regions and issue of each F024 oracle/base/t1 job; ``revisions`` maps instance_id to base commit."""
    chains = []
    for j in json.loads(Path(package_path).read_text())['jobs']:
        if (j['context'], j['arm'], j['turn']) != ('oracle', 'base', 1):
            continue
        user = json.loads(j['messages'][1]['content'])
        identifier = j['instance_id']
        chains.append({'chain_id': f'dev/{identifier}/oracle', 'instance_id': identifier,
                       'repo': 'django/django' if identifier.startswith('django__') else 'pytest-dev/pytest',
                       'base_commit': revisions[identifier], 'issue': user['issue'],
                       'regions': [{'path': r['path'], 'start_line': r['start_line'], 'end_line': r['end_line'],
                                    'text': re.sub(r'^\d+: ', '', r['numbered_original_source'], flags=re.M)}
                                   for r in user['original_source']]})
    return chains


def sampling_for(sample, call_index):
    """Greedy only for sample 0's first call; every other call samples with its own seed."""
    seed = 42 + call_index + 1000 * sample
    if sample == 0 and call_index == 0:
        return {'do_sample': False, 'seed': seed}
    return {'do_sample': True, 'temperature': 0.8, 'top_p': 0.95, 'seed': seed}


def dev_chains_from_cases(rows, directory, opener=urllib.request.urlopen):
    """Oracle chains for qualified dataset rows; the gold patch places regions and never enters a chain.

    A case ``oracle_regions`` refuses (more than 4 regions, an oversized window, a created or deleted file) is
    excluded rather than cut.
    """
    from scripts.oracle_context024 import oracle_regions
    chains = []
    for row in rows:
        chain = {'chain_id': f"dev/{row['instance_id']}/oracle", 'instance_id': row['instance_id'], 'repo': row['repo'],
                 'base_commit': row['base_commit'], 'issue': row['problem_statement'], 'regions': []}
        w = fetch_dev_source(chain, Path(directory) / row['instance_id'], opener)
        try:
            regions = oracle_regions(w, row['patch'], PREFIXES[row['repo']])
        except ValueError:
            continue
        finally:
            w.close()
        chain['regions'] = [{**{k: r['reference'][k] for k in ['path', 'start_line', 'end_line']},
                             'text': re.sub(r'^\d+: ', '', r['text'], flags=re.M)} for r in regions]
        chains.append(chain)
    return chains


def validate_package(package, call_cap=PACKAGE_CALL_CAP):
    if (package.get('version'), package.get('base_model'), package.get('base_revision')) != (VERSION, BASE, REVISION):
        raise ValueError('Package must name the pinned base model and revision')
    chains = package.get('chains', [])
    if not chains or len({c['chain_id'] for c in chains}) != len(chains):
        raise ValueError('Chains must be nonempty and unique')
    if len(chains) * MAX_CALLS_PER_CHAIN > call_cap:
        raise ValueError('Package exceeds the call cap')
    for c in chains:
        if 'reference' in c:
            raise ValueError('Reference fixes never enter the package')
        dev = DEV.fullmatch(c['chain_id'])
        if dev:
            if (dev[1] != c.get('instance_id') or c.get('repo') not in PREFIXES or not re.fullmatch(r'[a-f0-9]{40}', str(c.get('base_commit')))
                    or c['repo'] != ('django/django' if dev[2] == 'django__django' else 'pytest-dev/pytest')):
                raise ValueError('Invalid dev chain identity, repository or commit')
        elif not SYNTHETIC.fullmatch(c['chain_id']):
            raise ValueError('Invalid chain identity')
    return chains


def _journal(output, chain_id, index):
    name = Path(chain_id) / f'c{index}.json'
    return output / 'intents' / name, output / 'captures' / name


def _preflight(output, binding):
    for intent in sorted((output / 'intents').rglob('*.json')):
        if not (output / 'captures' / intent.relative_to(output / 'intents')).exists():
            raise ValueError('Uncertain dispatch preserved; no retry or further dispatch')
    for capture in sorted((output / 'captures').rglob('*.json')):
        if not (output / 'intents' / capture.relative_to(output / 'captures')).exists():
            raise ValueError('Capture has no dispatch intent')
        saved = json.loads(capture.read_text())
        if saved.get('binding') != binding or saved.get('capture_sha256') != digest({k: v for k, v in saved.items() if k != 'capture_sha256'}):
            raise ValueError('Prior capture binding or hash differs')
        if saved['status'] != 'captured':
            raise ValueError('Prior generation failure preserved; no automatic continuation')


def run_chains(package, output, generate, publish=publish_atomic, prepare_dev=None,
               count_tokens=lambda messages: len(canonical(messages)) // 3, host_checks=False,
               envelope_tokens=ENVELOPE_TOKENS, call_cap=PACKAGE_CALL_CAP):
    """``host_checks`` must be set explicitly: synthetic checks import model-written code in a child
    interpreter without a container, which is acceptable only in a disposable VM (Colab) or when
    ``prepare_dev`` points RUN at a container. The envelope and cap default to the T4 budget."""
    try:
        from scripts.repair_loop025 import run_loop, subprocess_check
        from scripts.f025_tasks import workspace as synthetic_workspace
    except ImportError:
        from repair_loop025 import run_loop, subprocess_check
        from f025_tasks import workspace as synthetic_workspace
    chains, binding, output = validate_package(package, call_cap), digest(package), Path(output)
    _preflight(output, binding)
    for chain in chains:
        record_path = output / 'chains' / (chain['chain_id'] + '.json')
        if record_path.exists():
            saved = json.loads(record_path.read_text())
            if saved.get('binding') != binding or saved.get('record_sha256') != digest({k: v for k, v in saved.items() if k != 'record_sha256'}):
                raise ValueError('Existing chain record belongs to another package or was altered: ' + chain['chain_id'])
            continue
        if 'instance_id' not in chain and not host_checks:
            raise ValueError('Synthetic checks execute model-written code; run only in a disposable VM with host_checks=True')
        state = {'calls': 0, 'reply': None}

        def model(messages, chain=chain, state=state):
            index = state['calls']
            if index >= MAX_CALLS_PER_CHAIN:
                raise ChainStop('call_cap')
            if count_tokens(messages) + MAX_NEW > envelope_tokens:
                raise ChainStop('envelope')
            intent, capture = _journal(output, chain['chain_id'], index)
            bound = {'binding': binding, 'chain_id': chain['chain_id'], 'call_index': index, 'messages_sha256': digest(messages)}
            if capture.exists():  # replay of an interrupted chain; verified in preflight, bound here
                saved = json.loads(capture.read_text())
                if {k: saved[k] for k in bound} != bound:
                    raise ValueError('Prior capture is bound to other messages')
                text = saved['result']['text']
            else:
                publish(intent, {**bound, 'status': 'dispatch_intent'})
                started = time.monotonic()
                try:
                    result = generate(messages, index, sampling_for(chain.get('sample', 0), index))
                    if not isinstance(result.get('text'), str) or len(result['text'].encode()) > 128 * 1024:
                        raise ValueError('Missing or oversized generation')
                    record = {'status': 'captured', 'result': result}
                except Exception as error:  # CUDA out of memory included: captured, never retried
                    record = {'status': 'generation_error', 'error_type': type(error).__name__, 'error': str(error)[:2000]}
                record.update(bound, model_calls=1, elapsed_seconds=time.monotonic() - started)
                # shortcut: self-hashes detect corruption, not forgery by someone with write access; anchor the hashes outside the output dir if it is ever shared
                record['capture_sha256'] = digest(record)
                publish(capture, record)
                print('KAIROS_F025_CAPTURE ' + canonical({k: record[k] for k in ['chain_id', 'call_index', 'status']}).decode(), flush=True)
                if record['status'] == 'generation_error':
                    raise RuntimeError('Generation failed; capture preserved, run halted')
                text = result['text']
            state['calls'], state['reply'] = index + 1, text
            return text

        receipts = output / 'receipts' / (chain['chain_id'] + '.jsonl')
        receipts.parent.mkdir(parents=True, exist_ok=True)
        receipts.unlink(missing_ok=True)  # a replayed chain rewrites its receipts from verified captures
        regions = [{k: r[k] for k in ['path', 'start_line', 'end_line']} for r in chain['regions']]
        with tempfile.TemporaryDirectory(prefix='f025-') as directory:
            if 'instance_id' in chain:
                w = prepare_dev(chain, directory)
                check = lambda _: (True, 'static checks only; scored later in pinned Docker')
            else:
                w, check = synthetic_workspace(chain, directory), subprocess_check(chain['check'])
            try:
                result = run_loop(model, w, chain['issue'], regions, check, receipts, max_corrections=3, allow_run=host_checks,
                                  stop=(ChainStop,), self_test='instance_id' in chain)
                status, patch, widened = result['status'], result['patch'], result['regions']
            except ChainStop as stop:
                status, patch, widened = str(stop), None, regions
            finally:
                w.close()
        record = {'chain_id': chain['chain_id'], 'binding': binding, 'status': status, 'calls': state['calls'],
                  'final_reply': state['reply'], 'patch': patch, 'regions': regions,
                  'read_regions': [r for r in widened if r not in regions],
                  'receipts_sha256': hashlib.sha256(receipts.read_bytes() if receipts.exists() else b'').hexdigest()}
        record['record_sha256'] = digest(record)
        publish(record_path, record)
    records = [json.loads((output / 'chains' / (c['chain_id'] + '.json')).read_text()) for c in chains]
    accepted = [r['chain_id'].split('/')[0] for r in records if r['status'] == 'accepted']
    # dev chains pass only static gates here; only f025_score's Docker run can call them repairs
    return {'status': 'complete', 'chains': len(records), 'synthetic_check_passed': accepted.count('synthetic'),
            'dev_static_accepted': accepted.count('dev'),
            'calls': sum(r['calls'] for r in records), 'training_runs': 0}


def fetch_dev_source(chain, directory, opener=urllib.request.urlopen, run_python=None):
    """Pinned codeload archive, package and test-root directories only, every oracle region verified against the bytes."""
    from kairos_api.investigations.sandbox import Workspace
    repository, revision = chain['repo'], chain['base_commit']
    if repository not in PREFIXES or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Source must use an approved repository and full pinned commit')
    prefix, test_root, directory = PREFIXES[repository], TEST_ROOTS[repository], Path(directory)
    url = 'https://codeload.github.com/' + repository + '/tar.gz/' + revision
    data = bytearray()
    with opener(url, timeout=60) as response:
        if response.geturl() != url:
            raise ValueError('Pinned codeload URL unexpectedly redirected')
        while chunk := response.read(1024 * 1024):
            data += chunk
            if len(data) > MAX_ARCHIVE:
                raise ValueError('Source archive exceeds the 80 MiB bounded download')
    members, expanded, top = [], 0, None
    with tarfile.open(fileobj=io.BytesIO(bytes(data))) as files:
        for member in files.getmembers():
            parts = member.name.split('/', 1)
            top = top or parts[0]
            if parts[0] != top:
                raise ValueError('Source archive has multiple top-level roots')
            if len(parts) != 2 or not parts[1]:
                continue
            name, path = parts[1], PurePosixPath(parts[1])
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Source archive contains traversal, hard links or special files')
            if not name.startswith(prefix) and not (name.startswith(test_root) and (member.isfile() or member.isdir())):
                continue  # never extracted: django's docs ship harmless ../ symlinks; test links are not needed to read
            link = PurePosixPath(member.linkname) if member.issym() else PurePosixPath('.')
            if (member.islnk() or link.is_absolute() or '..' in link.parts
                    or not (member.isfile() or member.isdir() or member.issym())):
                raise ValueError('Source archive contains traversal, hard links or special files')
            member.name = name
            expanded += member.size
            if expanded > MAX_EXPANDED:
                raise ValueError('Expanded source exceeds the 240 MiB safety bound')
            members.append(member)
        if not members:
            raise ValueError('Pinned source archive has no package files')
        (directory / 'source').mkdir(parents=True)
        files.extractall(directory / 'source', members=members, filter='data')
    for region in chain['regions']:
        path = PurePosixPath(region['path'])
        target = directory / 'source' / path
        if not region['path'].startswith(prefix) or '..' in path.parts or not target.is_file():
            raise ValueError('Oracle region file is missing from the pinned source: ' + region['path'])
        if ''.join(target.read_text().splitlines(True)[region['start_line'] - 1:region['end_line']]) != region['text']:
            raise ValueError('Oracle region text differs from the pinned source: ' + region['path'])
    registry = SimpleNamespace(verify=lambda _: None, directory=lambda _: directory)
    return Workspace(registry, {'issue': chain['issue'], 'approved_prefix': prefix, 'entry_files': [],
                                'test_roots': [test_root], 'python_paths': PYTHON_PATHS[repository],
                                **({'run_python': run_python or RUN_ENVS[repository]['python'], 'run_prelude': RUN_ENVS[repository]['prelude']}
                                   if repository in RUN_ENVS else {})})


BUNDLE = ['scripts/f025_colab.py', 'scripts/f024_colab.py', 'scripts/repair_loop025.py', 'scripts/search_replace025.py',
          'scripts/edit_preflight024.py', 'scripts/f025_tasks.py', 'scripts/__init__.py', 'kairos_api/__init__.py',
          'kairos_api/investigations/__init__.py', 'kairos_api/investigations/patches.py', 'kairos_api/investigations/sandbox.py']


def bundle(out_dir):
    from kairos_api import model_runtime
    shim = ('"""Bundle shim: only canonical() and digest(), copied verbatim, because the real module imports httpx\n'
            'and the API stack, which the Colab probe neither needs nor pins."""\nimport hashlib\nimport json\n\n\n'
            + inspect.getsource(model_runtime.canonical) + '\n\n' + inspect.getsource(model_runtime.digest))
    files = {name: (ROOT / name).read_bytes() for name in BUNDLE if (ROOT / name).exists()}
    files['kairos_api/model_runtime.py'] = shim.encode()
    target = Path(out_dir) / 'f025-code.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w') as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))  # fixed time: reproducible hash
            info.external_attr, info.compress_type = 0o644 << 16, zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    hashes['f025-code.zip'] = hashlib.sha256(target.read_bytes()).hexdigest()
    return hashes


def notebook(package_sha256, bundle_sha256, model_manifest_sha256):
    """Notebook cells: pinned profile, hash checks, one bounded run. No credentials."""
    pins = ' '.join(f'{name}=={version}' for name, version in PROFILE.items() if name not in {'torch', 'peft'})
    checks = {'f025-package.json': package_sha256, 'f025-code.zip': bundle_sha256, 'model-manifest.json': model_manifest_sha256}
    code = [
        f'!pip install -q {pins}',
        ('import hashlib,json,pathlib\n'
         'sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()\n'
         + ''.join(f"assert sha('{name}')=='{value}', '{name} changed'\n" for name, value in checks.items())
         + f"assert len(json.loads(pathlib.Path('f025-package.json').read_text())['chains'])*{MAX_CALLS_PER_CHAIN}<={PACKAGE_CALL_CAP}, 'call cap'"),
        '!unzip -q -o f025-code.zip -d /content',
        ('# RUN interpreter matching the pinned scoring image (Python 3.8; django 3.1 needs distutils)\n'
         '!pip install -q uv==0.4.30 && uv python install 3.8 && uv venv -p 3.8 /content/run-env-django && '
         f"uv pip install -q --python /content/run-env-django/bin/python {RUN_ENVS['django/django']['packages']}\n"
         '!/content/run-env-django/bin/python --version'),
        ('%cd /content\n'
         f'!python -m scripts.f025_colab --package f025-package.json --package-sha256 {package_sha256} '
         '--model-manifest model-manifest.json --scratch /content/scratch --output /content/f025-results'),
        '!cd /content && zip -q -r f025-results.zip f025-results',
    ]
    return {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'accelerator': 'GPU'},
            'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': [f'F025 probe: base model only, at most {PACKAGE_CALL_CAP} journaled calls; never rerun a cell after an uncertain dispatch.']}]
            + [{'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': [c]} for c in code]}


def run_gpu(args):  # pragma: no cover - executes only on an approved Colab GPU
    import importlib.metadata as metadata
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if sha(args.package) != args.package_sha256:
        raise ValueError('Package changed')
    package = json.loads(Path(args.package).read_text())
    validate_package(package)
    profile = {name: version for name, version in PROFILE.items() if name != 'peft'}
    versions = {name: metadata.version(name) for name in profile}
    if versions != profile:
        raise ValueError('Reviewed inference dependency profile differs')
    if not torch.cuda.is_available() or torch.cuda.get_device_properties(0).total_memory < 14 * 1024 ** 3:
        raise RuntimeError('CUDA GPU with at least 14 GiB required; no fallback')
    path = Path(snapshot_download(BASE, revision=REVISION, cache_dir=str(Path(args.scratch) / 'model'), token=False,
                                  allow_patterns=['*.json', '*.safetensors', 'tokenizer.model', '*.txt']))
    manifest = json.loads(Path(args.model_manifest).read_text())
    if {p.name for p in path.iterdir() if p.is_file()} != set(manifest['files']):
        raise ValueError('Downloaded model file set differs from the manifest')
    for name, item in manifest['files'].items():
        if (path / name).stat().st_size != item['bytes'] or sha(path / name) != item['sha256']:
            raise ValueError('Pinned base file differs: ' + name)
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    render = lambda messages: token_ids(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
    model = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True,
                                                 device_map={'': 0}, torch_dtype=torch.float16, attn_implementation='sdpa')
    # Precision profile copied from the F024 runner so base-model results stay comparable.
    for module in model.modules():
        if hasattr(module, 'compute_dtype'):
            module.compute_dtype = torch.float16
    for parameter in model.parameters():
        if parameter.ndim == 1 and parameter.dtype in (torch.float16, torch.bfloat16):
            parameter.data = parameter.data.to(torch.float32)
    model.requires_grad_(False)
    model.eval()
    if any(p.device.type != 'cuda' for p in model.parameters()):
        raise RuntimeError('Offload outside profile')
    output = Path(args.output)
    publish_atomic(output / 'runtime.json', {'versions': versions, 'gpu': torch.cuda.get_device_name(0),
                                             'gpu_bytes': torch.cuda.get_device_properties(0).total_memory, 'model_revision': REVISION,
                                             'model_files': {name: item['sha256'] for name, item in manifest['files'].items()},
                                             'package_sha256': args.package_sha256, 'training_runs': 0})

    def generate(messages, call_index, sampling):
        def expired():
            try:
                publish_atomic(output / 'hard-timeout.json', {'call_index': call_index, 'messages_sha256': digest(messages),
                                                              'reason': f'{HARD_DEADLINE_SECONDS}-second hard dispatch deadline; result unknown'})
            finally:
                os._exit(124)
        with hard_deadline(HARD_DEADLINE_SECONDS, expired):
            sampling = dict(sampling)
            set_seed(sampling.pop('seed'))
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            x = torch.tensor([render(messages)], device='cuda')
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
                values = model.generate(input_ids=x, attention_mask=torch.ones_like(x), max_new_tokens=MAX_NEW, **sampling,
                                        max_time=HARD_DEADLINE_SECONDS, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                                        eos_token_id=tokenizer.eos_token_id, use_cache=True)
            new = values[0, x.shape[1]:].tolist()
            torch.cuda.synchronize()
        return {'text': tokenizer.decode(new, skip_special_tokens=True), 'output_tokens': len(new), 'input_tokens': x.shape[1],
                'ended_with_eos': bool(new and new[-1] == tokenizer.eos_token_id), 'peak_reserved_bytes': torch.cuda.max_memory_reserved()}

    print(json.dumps(run_chains(package, output, generate, publish_atomic, prepare_dev=fetch_dev_source,
                                count_tokens=lambda messages: len(render(messages)), host_checks=True)))  # Colab VM is disposable


def main():  # pragma: no cover
    parser = argparse.ArgumentParser()
    for name in ['package', 'package-sha256', 'model-manifest', 'scratch', 'output']:
        parser.add_argument('--' + name, required=True)
    run_gpu(parser.parse_args())


if __name__ == '__main__':
    main()
