"""Drive f024_colab.run_gpu end to end with stub torch/transformers/peft/huggingface_hub; no GPU, no model.

Real-GPU behaviour is NOT verified here. Assumption (transformers 4.57.6): apply_chat_template(tokenize=True)
returns a flat list of ints, or a dict/BatchEncoding holding 'input_ids'; token_ids() accepts both.
"""
import contextlib
import hashlib
import json
import sys
import types
from types import SimpleNamespace

import pytest

from scripts import f024_colab as colab

sha = lambda b: hashlib.sha256(b).hexdigest()


def render(messages):
    return [ord(c) for c in messages[1]['content']]


class Tensor:
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]))

    def __getitem__(self, key):
        return _Row(self.rows[key[0]][key[1]])


class _Row:
    def __init__(self, v):
        self.v = v

    def tolist(self):
        return list(self.v)


class Env:
    def __init__(self, tmp_path, monkeypatch, template=None, oom_on=None):
        self.calls, self.disabled, self.exits, self.timers = [], [], [], []
        self.oom_on = oom_on
        model_dir, adapter = tmp_path / 'snap', tmp_path / 'adapter'
        model_dir.mkdir(), adapter.mkdir()
        (model_dir / 'config.json').write_bytes(b'{}')
        (adapter / 'adapter_model.safetensors').write_bytes(b'adapter')
        self.model_dir = model_dir
        self.manifest = tmp_path / 'model-manifest.json'
        self.manifest.write_text(json.dumps({'files': {'config.json': {'bytes': 2, 'sha256': sha(b'{}')}}}))
        self.binding = tmp_path / 'adapter-binding.json'
        self.binding.write_text(json.dumps({'files': [{'member': 'x/adapter_model.safetensors', 'bytes': 7, 'sha256': sha(b'adapter')}]}))
        jobs = []
        for arm in ('base', 'adapter'):
            m = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'hello'}]
            jobs.append({'job_id': f'django__django-1/issue/{arm}/t1', 'instance_id': 'django__django-1', 'context': 'issue', 'arm': arm,
                         'turn': 1, 'messages': m, 'prompt_tokens': 5, 'max_new_tokens': 512,
                         'prompt_token_ids_sha256': sha(json.dumps(render(m), separators=(',', ':')).encode())})
        self.package = {'version': colab.VERSION, 'base_model': colab.BASE, 'base_revision': colab.REVISION, 'jobs': jobs,
                        'bindings': {'adapter_binding': sha(self.binding.read_bytes()), 'model_manifest': sha(self.manifest.read_bytes())}}
        self.pkg_path = tmp_path / 'pkg.json'
        self.write_package()
        self.args = SimpleNamespace(package=str(self.pkg_path), package_sha256=sha(self.pkg_path.read_bytes()), adapter=str(adapter),
                                    adapter_binding=str(self.binding), model_manifest=str(self.manifest),
                                    scratch=str(tmp_path / 'scratch'), output=str(tmp_path / 'out'))
        self.out = tmp_path / 'out'
        env = self
        template = template or (lambda messages, **kw: render(messages))

        class Param:
            ndim, dtype, requires_grad = 2, 'f16', False
            device = SimpleNamespace(type='cuda')

        class Model:
            def eval(self): pass
            def gradient_checkpointing_disable(self): pass
            def parameters(self): return [Param()]
            def modules(self): return []

            @contextlib.contextmanager
            def disable_adapter(self):
                env.disabled.append(True)
                yield

            def generate(self, input_ids, **kw):
                env.calls.append(len(env.disabled))
                if env.oom_on == len(env.calls):
                    raise RuntimeError('CUDA out of memory')
                return Tensor([input_ids.rows[0] + [7, 8, 99]])

        cuda = SimpleNamespace(is_available=lambda: True, get_device_properties=lambda i: SimpleNamespace(total_memory=16 * 1024 ** 3),
                               get_device_name=lambda i: 'stub-T4', empty_cache=lambda: None, reset_peak_memory_stats=lambda: None,
                               synchronize=lambda: None, max_memory_reserved=lambda: 123)
        torch = types.ModuleType('torch')
        torch.cuda, torch.float16, torch.float32, torch.bfloat16 = cuda, 'f16', 'f32', 'bf16'
        torch.tensor = lambda rows, device=None: Tensor(rows)
        torch.ones_like = lambda x: x
        torch.inference_mode = torch.autocast = lambda *a, **k: contextlib.nullcontext()
        tok = SimpleNamespace(pad_token_id=None, eos_token_id=99, apply_chat_template=template,
                              decode=lambda ids, skip_special_tokens: ' '.join(map(str, ids)))
        tf = types.ModuleType('transformers')
        tf.AutoTokenizer = SimpleNamespace(from_pretrained=lambda *a, **k: tok)
        tf.AutoModelForCausalLM = SimpleNamespace(from_pretrained=lambda *a, **k: Model())
        tf.set_seed = lambda n: None
        peft = types.ModuleType('peft')
        peft.PeftModel = SimpleNamespace(from_pretrained=lambda base, *a, **k: base)
        hub = types.ModuleType('huggingface_hub')
        hub.snapshot_download = lambda *a, **k: str(model_dir)
        for name, mod in dict(torch=torch, transformers=tf, peft=peft, huggingface_hub=hub).items():
            monkeypatch.setitem(sys.modules, name, mod)
        import importlib.metadata as md
        monkeypatch.setattr(md, 'version', lambda name: colab.PROFILE[name])

        class Timer:
            def __init__(self, seconds, fn): env.timers.append((seconds, fn)); self.daemon = False
            def start(self): pass
            def cancel(self): pass
            def join(self): pass
        monkeypatch.setattr(colab.threading, 'Timer', Timer)
        monkeypatch.setattr(colab.os, '_exit', lambda code: env.exits.append(code))

    def write_package(self):
        self.pkg_path.write_text(json.dumps(self.package))


def test_success_writes_runtime_captures_all_and_disables_adapter_only_for_base(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    colab.run_gpu(e.args)
    runtime = json.loads((e.out / 'runtime.json').read_text())
    assert runtime['versions'] == colab.PROFILE and runtime['training_runs'] == 0 and runtime['gpu'] == 'stub-T4'
    caps = {str(p): json.loads(p.read_text()) for p in (e.out / 'captures').glob('**/*.json')}
    assert len(caps) == 2 and {c['status'] for c in caps.values()} == {'captured'}
    assert (e.out / 'intents').exists() and all(c['model_calls'] == 1 for c in caps.values())
    assert e.disabled == [True] and e.calls == [1, 1]  # base (first job) disabled; adapter arm did not add one
    adapter = next(c for c in caps.values() if c['job_id'].endswith('/adapter/t1'))
    assert adapter['result']['ended_with_eos'] and adapter['result']['output_tokens'] == 3
    assert len(e.timers) == 2 and e.timers[0][0] == colab.HARD_DEADLINE_SECONDS


def test_oom_is_captured_as_generation_error_and_halts(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch, oom_on=1)
    with pytest.raises(RuntimeError, match='halted'):
        colab.run_gpu(e.args)
    files = list((e.out / 'captures').glob('**/*.json'))
    assert len(files) == 1 and json.loads(files[0].read_text())['status'] == 'generation_error'
    assert 'out of memory' in json.loads(files[0].read_text())['error'] and len(e.calls) == 1


def test_hard_deadline_publishes_timeout_then_exits(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    colab.run_gpu(e.args)
    e.timers[0][1]()
    assert json.loads((e.out / 'hard-timeout.json').read_text())['job_id'].endswith('/base/t1') and e.exits == [124]


def run_refused(e, match):
    with pytest.raises(ValueError, match=match):
        colab.run_gpu(e.args)
    assert not e.calls and not (e.out / 'runtime.json').exists()


def test_package_hash_mismatch(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    e.args.package_sha256 = '0' * 64
    run_refused(e, 'Package changed')


def test_binding_and_manifest_hash_mismatch(tmp_path, monkeypatch):
    for target in ('binding', 'manifest'):
        e = Env(tmp_path / target if (tmp_path / target).mkdir() is None else tmp_path, monkeypatch)
        getattr(e, target).write_text(getattr(e, target).read_text() + ' ')
        run_refused(e, 'differs from the package')


def test_downloaded_file_set_differs_from_manifest(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    (e.model_dir / 'extra.json').write_bytes(b'{}')
    run_refused(e, 'file set')


def test_pinned_base_file_bytes_differ(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    (e.model_dir / 'config.json').write_bytes(b'{!}')
    run_refused(e, 'Pinned base file')


def test_adapter_bytes_differ(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    (tmp_path / 'adapter' / 'adapter_model.safetensors').write_bytes(b'tampered')
    run_refused(e, 'Adapter bytes')


def test_dependency_profile_mismatch(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    import importlib.metadata as md
    monkeypatch.setattr(md, 'version', lambda name: '0.0.0')
    run_refused(e, 'dependency profile')


def test_prompt_rerender_digest_mismatch(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch, template=lambda messages, **kw: render(messages) + [1])
    run_refused(e, 'Prompt rendering')


def test_envelope_overflow_after_rerender(tmp_path, monkeypatch):
    big = [1] * 3100
    e = Env(tmp_path, monkeypatch, template=lambda messages, **kw: big)
    for j in e.package['jobs']:
        j['prompt_token_ids_sha256'] = sha(json.dumps(big, separators=(',', ':')).encode())
    e.write_package()
    e.args.package_sha256 = sha(e.pkg_path.read_bytes())
    for k, f in (('adapter_binding', e.binding), ('model_manifest', e.manifest)):
        assert e.package['bindings'][k] == sha(f.read_bytes())
    run_refused(e, 'Prompt rendering')


def test_token_ids_accepts_list_or_batchencoding_and_refuses_nesting():
    assert colab.token_ids([1, 2]) == [1, 2] and colab.token_ids({'input_ids': [3, 4]}) == [3, 4]
    for bad in ([[1, 2]], [], {'attention_mask': [1]}):
        with pytest.raises((ValueError, TypeError)):
            colab.token_ids(bad)


def test_batchencoding_template_runs_end_to_end(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch, template=lambda messages, **kw: {'input_ids': render(messages)})
    colab.run_gpu(e.args)
    assert len(e.calls) == 2


def test_turn2_notebook_bound_to_package_hash_cap_8():
    nb = colab.turn2_notebook('a' * 64, 'b' * 64, 'c' * 64, 'd' * 64)
    text = json.dumps(nb)
    assert "<=8, 'generation cap'" in text and text.count('a' * 64) >= 2 and 'at most 8 generations' in text
