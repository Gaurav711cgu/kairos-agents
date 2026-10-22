"""F024 Colab runner: hash-bound, journaled, memory-preflighted 14B generations.

Journal semantics match the frozen unseen023 runner: an intent bound to the package
and job is published before each dispatch and a hashed capture bound to the same
job after it. An intent without a capture is an uncertain dispatch and stops the
run; a capture without an intent, or one bound to another job, is refused; a
captured error (including CUDA out of memory) halts the run and is never retried;
a 180 s hard deadline ends the process with evidence. Unlike that runner, the
package is not tied to a fixed cohort and each job carries its own context, arm,
turn and output cap. This file imports no project module, so its one hash binds
every rule it enforces. Nothing runs unless an approved notebook calls ``run_gpu``.
"""
import argparse
import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path

VERSION = 'f024-pilot-v1'
BASE = 'unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit'
REVISION = 'ecfc63c083900ce4f19daad695e711f38ab98fcf'
# Largest input+output ever observed on the T4 profile (peak 14.42 of 14.6 GiB).
ENVELOPE_TOKENS = 3539
ALLOWED_MAX_NEW = {512}
HARD_DEADLINE_SECONDS = 180
PROFILE = {'torch': '2.11.0+cu130', 'transformers': '4.57.6', 'peft': '0.21.2', 'accelerate': '1.15.0',
           'bitsandbytes': '0.50.2', 'tokenizers': '0.22.2'}
INSTANCE = re.compile(r'(django__django|pytest-dev__pytest)-[0-9]+')
SHA = re.compile(r'[a-f0-9]{64}')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_package(package):
    if (package.get('version'), package.get('base_model'), package.get('base_revision')) != (VERSION, BASE, REVISION):
        raise ValueError('Package must name the pinned base model and revision')
    bindings = package.get('bindings', {})
    if set(bindings) != {'adapter_binding', 'model_manifest'} or not all(SHA.fullmatch(str(v)) for v in bindings.values()):
        raise ValueError('Package bindings must pin the adapter binding and model manifest hashes')
    jobs = package.get('jobs', [])
    if not jobs or len({j['job_id'] for j in jobs}) != len(jobs):
        raise ValueError('Jobs must be nonempty and unique')
    pairs = {}
    for j in jobs:
        if (not INSTANCE.fullmatch(str(j['instance_id'])) or j['arm'] not in {'base', 'adapter'} or j['context'] not in {'issue', 'oracle'}
                or j['turn'] not in {1, 2} or j['job_id'] != f"{j['instance_id']}/{j['context']}/{j['arm']}/t{j['turn']}"):
            raise ValueError('Invalid job identity')
        if j['max_new_tokens'] not in ALLOWED_MAX_NEW or j['prompt_tokens'] + j['max_new_tokens'] > ENVELOPE_TOKENS:
            raise ValueError('Job exceeds the observed T4 memory envelope')
        if [m['role'] for m in j['messages']] != ['system', 'user']:
            raise ValueError('Only the trained system/user protocol shape is allowed')
        if j['turn'] == 1:
            pairs.setdefault((j['instance_id'], j['context']), []).append(j)
        elif j.get('parent_job_id') != j['job_id'][:-1] + '1' or not SHA.fullmatch(str(j.get('parent_capture_sha256'))):
            raise ValueError('Turn-two job must name its turn-one parent and that capture hash')
    for pair in pairs.values():
        if sorted(j['arm'] for j in pair) != ['adapter', 'base'] or pair[0]['messages'] != pair[1]['messages']:
            raise ValueError('Turn-one base and adapter jobs must pair with identical inputs')
    return jobs


def _paths(output, job):
    return output / 'intents' / (job['job_id'] + '.json'), output / 'captures' / (job['job_id'] + '.json')


def run_jobs(package, output, generate, publish):
    jobs, binding, output = validate_package(package), digest(package), Path(output)
    for j in jobs:  # preflight the whole journal before any dispatch
        intent, capture = _paths(output, j)
        if intent.exists() and not capture.exists():
            raise ValueError('Uncertain dispatch preserved; no retry or further dispatch')
        if capture.exists() and not intent.exists():
            raise ValueError('Capture has no dispatch intent')
        if intent.exists():
            prior = json.loads(intent.read_text())
            if prior.get('binding') != binding or prior.get('job_sha256') != digest(j):
                raise ValueError('Prior intent binding differs')
        if capture.exists():
            saved = json.loads(capture.read_text())
            if (saved.get('binding'), saved.get('job_id'), saved.get('job_sha256')) != (binding, j['job_id'], digest(j)) \
                    or saved.get('capture_sha256') != digest({k: v for k, v in saved.items() if k != 'capture_sha256'}):
                raise ValueError('Prior capture binding, job or hash differs')
            if saved['status'] != 'captured':
                raise ValueError('Prior generation failure preserved; no automatic continuation')
    for j in jobs:
        intent, capture = _paths(output, j)
        if capture.exists():
            continue
        publish(intent, {'binding': binding, 'job_sha256': digest(j), 'job_id': j['job_id'], 'status': 'dispatch_intent'})
        started = time.monotonic()
        try:
            result = generate(j)
            if not isinstance(result.get('text'), str) or len(result['text'].encode()) > 128 * 1024:
                raise ValueError('Missing or oversized generation')
            record = {'status': 'captured', 'result': result}
        except Exception as error:  # CUDA out of memory included: captured, never retried
            record = {'status': 'generation_error', 'error_type': type(error).__name__, 'error': str(error)[:2000]}
        record.update(binding=binding, job_id=j['job_id'], job_sha256=digest(j), model_calls=1, elapsed_seconds=time.monotonic() - started)
        record['capture_sha256'] = digest(record)
        publish(capture, record)
        print('KAIROS_F024_CAPTURE ' + canonical({k: record[k] for k in ['job_id', 'status', 'elapsed_seconds']}).decode(), flush=True)
        if record['status'] == 'generation_error':
            raise RuntimeError('Generation failed; capture preserved, run halted')
    return {'status': 'complete', 'captures': len(jobs), 'binding': binding, 'training_runs': 0}


def notebook(package_sha256, runner_sha256, adapter_binding_sha256, model_manifest_sha256, *, max_generations):
    """Notebook cells: pinned profile, hash checks, one bounded run. No credentials."""
    pins = ' '.join(f'{name}=={version}' for name, version in PROFILE.items() if name != 'torch')
    checks = {'f024-package.json': package_sha256, 'f024_colab.py': runner_sha256,
              'adapter-binding.json': adapter_binding_sha256, 'model-manifest.json': model_manifest_sha256}
    code = [
        f'!pip install -q {pins}',
        ('import hashlib,json,pathlib\n'
         'sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()\n'
         + ''.join(f"assert sha('{name}')=='{value}', '{name} changed'\n" for name, value in checks.items())
         + f"assert len(json.loads(pathlib.Path('f024-package.json').read_text())['jobs'])<={max_generations}, 'generation cap'"),
        (f'!python f024_colab.py --package f024-package.json --package-sha256 {package_sha256} '
         '--adapter adapter --adapter-binding adapter-binding.json --model-manifest model-manifest.json '
         '--scratch /content/scratch --output /content/f024-results'),
    ]
    return {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'accelerator': 'GPU'},
            'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': [f'F024 pilot: at most {max_generations} generations, journaled; never rerun a cell after an uncertain dispatch.']}]
            + [{'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': [c]} for c in code]}


@contextmanager
def hard_deadline(seconds, expired):
    timer = threading.Timer(seconds, expired)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join()


def publish_atomic(target, value):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True))
    temporary.replace(target)  # a record is either complete or absent


def run_gpu(args):  # pragma: no cover - executes only on an approved Colab GPU
    import importlib.metadata as metadata
    from contextlib import nullcontext
    import torch
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if sha(args.package) != args.package_sha256:
        raise ValueError('Package changed')
    package = json.loads(Path(args.package).read_text())
    validate_package(package)
    if sha(args.adapter_binding) != package['bindings']['adapter_binding'] or sha(args.model_manifest) != package['bindings']['model_manifest']:
        raise ValueError('Adapter binding or model manifest differs from the package')
    versions = {name: metadata.version(name) for name in PROFILE}
    if versions != PROFILE:
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
    for item in json.loads(Path(args.adapter_binding).read_text())['files']:
        member = Path(args.adapter) / Path(item['member']).name
        if member.stat().st_size != item['bytes'] or sha(member) != item['sha256']:
            raise ValueError('Adapter bytes differ')
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    ids = {}
    for j in package['jobs']:  # every prompt is re-rendered and checked before the model loads
        rendered = list(tokenizer.apply_chat_template(j['messages'], tokenize=True, add_generation_prompt=True))
        if hashlib.sha256(json.dumps(rendered, separators=(',', ':')).encode()).hexdigest() != j['prompt_token_ids_sha256'] \
                or len(rendered) + j['max_new_tokens'] > ENVELOPE_TOKENS:
            raise ValueError('Prompt rendering or memory envelope differs before dispatch: ' + j['job_id'])
        ids[j['job_id']] = rendered
    base = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True,
                                                device_map={'': 0}, torch_dtype=torch.float16, attn_implementation='sdpa')
    # Precision profile copied from the frozen unseen023 runner so arms stay comparable.
    for module in base.modules():
        if hasattr(module, 'compute_dtype'):
            module.compute_dtype = torch.float16
    for parameter in base.parameters():
        if parameter.ndim == 1 and parameter.dtype in (torch.float16, torch.bfloat16):
            parameter.data = parameter.data.to(torch.float32)
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False, local_files_only=True, use_safetensors=True)
    model.eval()
    model.gradient_checkpointing_disable()
    if any(p.requires_grad or p.device.type != 'cuda' for p in model.parameters()):
        raise RuntimeError('Trainable parameters or offload outside profile')
    output = Path(args.output)
    publish_atomic(output / 'runtime.json', {'versions': versions, 'gpu': torch.cuda.get_device_name(0),
                                             'gpu_bytes': torch.cuda.get_device_properties(0).total_memory, 'model_revision': REVISION,
                                             'model_files': {name: item['sha256'] for name, item in manifest['files'].items()},
                                             'package_sha256': args.package_sha256, 'training_runs': 0})

    def generate(j):
        def expired():
            try:
                publish_atomic(output / 'hard-timeout.json', {'job_id': j['job_id'], 'reason': f'{HARD_DEADLINE_SECONDS}-second hard dispatch deadline; result unknown'})
            finally:
                os._exit(124)
        with hard_deadline(HARD_DEADLINE_SECONDS, expired):
            set_seed(42)
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            x = torch.tensor([ids[j['job_id']]], device='cuda')
            with (model.disable_adapter() if j['arm'] == 'base' else nullcontext()), torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
                values = model.generate(input_ids=x, attention_mask=torch.ones_like(x), do_sample=False, max_new_tokens=j['max_new_tokens'],
                                        max_time=HARD_DEADLINE_SECONDS, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                                        eos_token_id=tokenizer.eos_token_id, use_cache=True)
            new = values[0, x.shape[1]:].tolist()
            torch.cuda.synchronize()
        return {'text': tokenizer.decode(new, skip_special_tokens=True), 'output_tokens': len(new), 'input_tokens': x.shape[1],
                'ended_with_eos': bool(new and new[-1] == tokenizer.eos_token_id), 'peak_reserved_bytes': torch.cuda.max_memory_reserved()}

    print(json.dumps(run_jobs(package, output, generate, publish_atomic)))


def main():  # pragma: no cover
    parser = argparse.ArgumentParser()
    for name in ['package', 'adapter', 'adapter-binding', 'model-manifest', 'scratch', 'output']:
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--package-sha256', required=True)
    run_gpu(parser.parse_args())


if __name__ == '__main__':
    main()
