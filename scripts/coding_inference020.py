"""Inference-only paired comparison. Never trains, grades repairs or retries unknown dispatches."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import tempfile
import time
import traceback

BASE = 'unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit'
REVISION = 'ecfc63c083900ce4f19daad695e711f38ab98fcf'
ARMS = ('base', 'adapter')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def publish(path, value):
    """Publish complete fsynced JSON without overwriting a prior receipt."""
    path = Path(path)
    raw = canonical(value) + b'\n'
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('Preserve prior receipt: ' + path.name)
        return
    handle, temporary = tempfile.mkstemp(prefix='.capture-', dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def verify_inputs(prompts, adapter, expected_sha):
    prompts, adapter = Path(prompts), Path(adapter)
    if prompts.is_symlink() or not prompts.is_file() or prompts.stat().st_size > 2 * 1024**2 or sha(prompts) != expected_sha:
        raise ValueError('Frozen prompts differ')
    package = json.loads(prompts.read_bytes())
    if (package.get('version') != 'coding-repair-comparison020-v1'
            or package.get('base_model') != BASE or package.get('base_revision') != REVISION
            or package.get('reference_material_included') is not False):
        raise ValueError('Unexpected comparison identity')
    expected_generation = {'do_sample': False, 'max_new_tokens': 1024, 'context_tokens': 4096,
                           'seed': 42, 'max_time_seconds': 180, 'calls_per_arm_case': 1}
    if package.get('generation') != expected_generation:
        raise ValueError('Frozen generation settings differ')
    ids = [case['instance_id'] for case in package['cases']]
    if len(ids) != 12 or len(set(ids)) != 12 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', value) for value in ids):
        raise ValueError('Case membership differs')
    for name in ['adapter_model.safetensors', 'adapter_config.json']:
        path = adapter / name
        expected = package['adapter_files'][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
            raise ValueError('Trained adapter differs: ' + name)
    if json.loads((adapter / 'adapter_config.json').read_bytes()).get('base_model_name_or_path') != BASE:
        raise ValueError('Adapter base differs')
    for case in package['cases']:
        if set(case['messages'][0]) != {'role', 'content'} or [m['role'] for m in case['messages']] != ['system', 'user']:
            raise ValueError('Only frozen system/user messages are allowed')
        if any(not isinstance(m['content'], str) for m in case['messages']):
            raise ValueError('Invalid message content')
    return package


def tokenize_cases(package, tokenize):
    prepared = []
    for case in package['cases']:
        tokens = tokenize(case['messages'])
        unavailable = case.get('unavailable_reason') if not case.get('context_available') else None
        if len(tokens) + package['generation']['max_new_tokens'] > package['generation']['context_tokens']:
            unavailable = 'Whole prompt exceeds frozen context budget; no truncation or model call'
        prepared.append({**case, 'input_token_ids': tokens, 'input_tokens': len(tokens), 'unavailable_reason': unavailable})
    return prepared


def error_details(error):
    """Bound private diagnostics without locals, source lines or environment secrets."""
    message = str(error)
    for key, value in os.environ.items():
        if value and len(value) >= 8 and any(word in key.upper() for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET', 'CREDENTIAL')):
            message = message.replace(value, '[redacted]')
    return {'message': message[:4096],
            'frames': [{'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
                       for frame in traceback.extract_tb(error.__traceback__)[-12:]]}


def paired_run(package, cases, output, binding, generate, *, capture_error_details=False):
    """A crash after intent is unknown; captured outputs are reused, never regenerated."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    publish(output / 'binding.json', binding)
    records = []
    for index, case in enumerate(cases):
        # Counterbalance order without changing case membership or selecting on outcomes.
        for arm in (ARMS if index % 2 == 0 else tuple(reversed(ARMS))):
            stem = case['instance_id'] + '.' + arm
            result_path, intent_path = output / (stem + '.json'), output / (stem + '.intent.json')
            if result_path.exists():
                result = json.loads(result_path.read_bytes())
                if (result.get('binding_sha256') != hashlib.sha256(canonical(binding)).hexdigest()
                        or result.get('capture_sha256') != hashlib.sha256(canonical({k: v for k, v in result.items() if k != 'capture_sha256'})).hexdigest()
                        or (result.get('instance_id'), result.get('arm')) != (case['instance_id'], arm)):
                    raise ValueError('Captured result belongs to another configuration')
                records.append(result)
                continue
            if intent_path.exists():
                raise RuntimeError('Unknown prior dispatch; never resend: ' + stem)
            result = {'instance_id': case['instance_id'], 'arm': arm,
                      'binding_sha256': hashlib.sha256(canonical(binding)).hexdigest(),
                      'input_tokens': case['input_tokens'], 'verified_repair': None,
                      'verification_complete': False}
            if case.get('unavailable_reason'):
                result.update(status='unavailable', reason=case['unavailable_reason'], model_calls=0)
            else:
                publish(intent_path, {'instance_id': case['instance_id'], 'arm': arm,
                                      'binding_sha256': result['binding_sha256'],
                                      'prompt_sha256': hashlib.sha256(canonical(case['messages'])).hexdigest()})
                started = time.monotonic()
                try:
                    generated = generate(case, arm)
                    if not isinstance(generated['text'], str) or len(generated['text'].encode()) > 128 * 1024:
                        raise ValueError('Oversized or invalid model output')
                    result.update(status='captured', model_calls=1, **generated)
                except Exception as error:
                    # A dispatched inference error is preserved once; no alternate model/retry.
                    result.update(status='inference_error', model_calls=1, error_type=type(error).__name__,
                                  reason='Inference raised; inspect captured runtime. No retry was sent.')
                    if capture_error_details:
                        result['error_details'] = error_details(error)
                result['elapsed_seconds'] = time.monotonic() - started
            result['capture_sha256'] = hashlib.sha256(canonical(result)).hexdigest()
            publish(result_path, result)
            records.append(result)
            print(json.dumps({'instance_id': case['instance_id'], 'arm': arm, 'status': result['status'],
                              'model_calls': result['model_calls']}), flush=True)
    result = {'version': 'coding-generation-results020-v1', 'binding': binding, 'records': records,
              'inference_complete': len(records) == 2 * len(package['cases']), 'repair_verification_complete': False,
              'scope': package['scope'], 'training_runs': 0}
    publish(output / 'generations.json', result)
    return result


def run_gpu(prompts, adapter, output, expected_sha, scratch):
    package = verify_inputs(prompts, adapter, expected_sha)
    # A partially dispatched prior run must be diagnosed before allocating GPU or fetching weights.
    output = Path(output)
    if output.exists():
        for intent in output.glob('*.intent.json'):
            if not intent.with_name(intent.name.replace('.intent.json', '.json')).exists():
                raise RuntimeError('Unknown prior dispatch; no model was loaded: ' + intent.name)
        completed = output / 'generations.json'
        if completed.exists():
            saved = json.loads(completed.read_bytes())
            if saved.get('binding', {}).get('prompts_sha256') != expected_sha or saved.get('binding', {}).get('runner_sha256') != sha(__file__):
                raise ValueError('Completed study configuration differs')
            for case in package['cases']:
                for arm in ARMS:
                    if not (output / (case['instance_id'] + '.' + arm + '.json')).is_file():
                        raise ValueError('Completed study has a missing capture; never regenerate it')
            cases = tokenize_cases(package, lambda messages: [])
            return paired_run(package, cases, output, saved['binding'], lambda *_: (_ for _ in ()).throw(RuntimeError('Completed output must never dispatch')))
    if os.environ.get('KAIROS_EVALUATION_GPU') != '1':
        raise RuntimeError('Set KAIROS_EVALUATION_GPU=1 only in the approved free GPU evaluation runtime')
    import shutil
    if shutil.disk_usage(scratch).free < 16 * 1024**3:
        raise RuntimeError('Need 16 GiB cloud scratch free before the pinned model download')
    os.environ.update(HF_HUB_DISABLE_IMPLICIT_TOKEN='1', WANDB_DISABLED='true',
                      TOKENIZERS_PARALLELISM='false', PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, set_seed
    from peft import PeftModel
    from huggingface_hub import snapshot_download
    if not torch.cuda.is_available() or torch.cuda.get_device_properties(0).total_memory < 14 * 1024**3:
        raise RuntimeError('A CUDA GPU with at least 14 GiB is required; no CPU/Mac fallback')
    runtime = {name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'peft', 'accelerate', 'bitsandbytes', 'tokenizers']}
    if any(runtime[name] != value for name, value in {'transformers': '4.57.6', 'peft': '0.21.2', 'accelerate': '1.15.0', 'bitsandbytes': '0.50.2'}.items()):
        raise RuntimeError('Reviewed inference dependency profile differs; stop before weights')
    model_path = Path(snapshot_download(BASE, revision=REVISION, cache_dir=str(Path(scratch) / 'public-model-cache'),
        token=False, allow_patterns=['*.json', '*.safetensors', 'tokenizer.model', '*.txt'], ignore_patterns=['*.bin', '*.pt', '*.pth']))
    model_files = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in model_path.iterdir() if p.is_file()}
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    for case in package['cases']:
        rendered = ''.join('<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n'
                           for message in case['messages']) + '<|im_start|>assistant\n'
        if rendered != tokenizer.apply_chat_template(case['messages'], tokenize=False, add_generation_prompt=True):
            raise ValueError('Pinned system/user template rendering differs; no inference dispatched')
    cases = tokenize_cases(package, lambda messages: tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
    base = AutoModelForCausalLM.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False,
        use_safetensors=True, device_map={'': 0}, torch_dtype=torch.float16, attn_implementation='sdpa')
    model = PeftModel.from_pretrained(base, str(adapter), is_trainable=False, local_files_only=True, use_safetensors=True)
    model.eval()
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise RuntimeError('Inference model unexpectedly has trainable parameters')
    if any(parameter.device.type != 'cuda' for parameter in model.parameters()):
        raise RuntimeError('CPU/disk offload is outside this profile')
    binding = {'version': 'coding-inference-binding020-v1', 'prompts_sha256': expected_sha,
               'runner_sha256': sha(__file__), 'adapter_sha256': package['adapter_files']['adapter_model.safetensors']['sha256'],
               'runtime': runtime, 'gpu': torch.cuda.get_device_name(0), 'model_revision': REVISION,
               'model_files': model_files, 'generation': package['generation'], 'training_runs': 0}
    def generate(case, arm):
        set_seed(package['generation']['seed'])
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        ids = torch.tensor([case['input_token_ids']], device='cuda')
        started = time.monotonic()
        # Disabling adapters exposes the same frozen quantized base, with identical input and decoding.
        with (model.disable_adapter() if arm == 'base' else nullcontext()), torch.inference_mode():
            values = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), do_sample=False,
                max_new_tokens=package['generation']['max_new_tokens'], max_time=package['generation']['max_time_seconds'],
                pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id, use_cache=True)
        new = values[0, ids.shape[1]:].tolist()
        eos = bool(new and new[-1] == tokenizer.eos_token_id)
        return {'text': tokenizer.decode(new, skip_special_tokens=True), 'output_token_ids': new,
                'output_tokens': len(new), 'ended_with_eos': eos,
                'stop_reason': 'eos' if eos else ('output_budget' if len(new) >= package['generation']['max_new_tokens'] else 'generation_time_limit'),
                'generation_seconds': time.monotonic() - started,
                'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
                'peak_allocated_bytes': torch.cuda.max_memory_allocated()}
    return paired_run(package, cases, output, binding, generate)


def export_results(output):
    import zipfile
    output = Path(output)
    result = json.loads((output / 'generations.json').read_bytes())
    expected = {'binding.json', 'generations.json'}
    for record in result['records']:
        stem = record['instance_id'] + '.' + record['arm']
        expected.add(stem + '.json')
        if record['model_calls']:
            expected.add(stem + '.intent.json')
    files = {p.name: p for p in output.iterdir() if p.is_file() and p.suffix == '.json'}
    if set(files) != expected or sum(p.stat().st_size for p in files.values()) > 4 * 1024**2:
        raise ValueError('Unexpected or oversized export membership')
    manifest = {'version': 'coding-inference-export020-v1', 'contains_model_weights': False,
                'training_runs': 0, 'repair_verification_complete': False,
                'files': {name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for name, p in sorted(files.items())}}
    target = output.parent / 'kairos-evaluation020.zip'
    if not target.exists():
        with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
            for name, path in sorted(files.items()):
                archive.write(path, name)
            archive.writestr('manifest.json', canonical(manifest))
    with zipfile.ZipFile(target) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())) or set(archive.namelist()) != expected | {'manifest.json'}:
            raise ValueError('Existing export membership differs')
        if json.loads(archive.read('manifest.json')) != manifest:
            raise ValueError('Existing export manifest differs; never regenerate it')
        for name, item in manifest['files'].items():
            raw = archive.read(name)
            if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Export byte hash differs')
    return {'path': str(target), 'bytes': target.stat().st_size, 'sha256': sha(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompts', type=Path, required=True)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prompts-sha256', required=True)
    parser.add_argument('--scratch', type=Path, default=Path('/content'))
    args = parser.parse_args()
    run_gpu(args.prompts, args.adapter, args.output, args.prompts_sha256, args.scratch)


if __name__ == '__main__':
    main()
