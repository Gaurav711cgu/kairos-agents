"""Integrity fixtures exercise the pilot gate, not a real model or GPU result."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from scripts import coding_resource014 as resource
from scripts import coding_train014 as runner
from tests.test_coding_public100014 import example


def test_state_proofs_preserve_types_order_and_values():
    assert resource.state_digest({'a': 1, 'b': [2]}) == resource.state_digest({'b': [2], 'a': 1})
    assert resource.state_digest([1]) != resource.state_digest((1,))
    assert resource.state_digest(1) != resource.state_digest(True)
    assert resource.state_digest(1) != resource.state_digest(1.0)
    with pytest.raises(ValueError): resource.state_digest(float('nan'))
    with pytest.raises(ValueError): resource.state_digest(object())


def fixture_pilot(root, mutation=None):
    binding = {'study': 'resource2', 'profile': '14B', 'planned_steps': 20,
               'corpus_sha256': 'a' * 64, 'admission_index_sha256': 'b' * 64,
               'runner_sha256': 'c' * 64, 'max_sequence': 2048, 'gradient_accumulation': 8,
               'model_manifest_sha256': 'd' * 64, 'loss_projection': 'supervised-causal-positions-v1',
               'max_supervised_tokens': 350}
    manifest = {'version': 'coding-resource-acceptance014-v1', 'runs': {}}
    for name, steps in [('full', 20), ('interrupted', 10), ('resumed', 20)]:
        folder = root / name; checkpoint = folder / ('checkpoint-' + str(steps)); checkpoint.mkdir(parents=True)
        proof = {'step': steps, **{key: 'e' * 64 for key in ('adapter', 'optimizer', 'scheduler', 'rng')}}
        receipt = {'version': 'coding-training-run014-v1', 'binding': deepcopy(binding),
                   'completed_steps': steps, 'run_complete': steps == 20, 'resource_fit_verified': steps == 20,
                   'adapter_updated': True, 'resumed_from_receipt_sha256': None}
        if name == 'resumed': receipt['resumed_from_receipt_sha256'] = manifest['runs']['interrupted']['checkpoint_receipt_sha256']
        if mutation: mutation(name, receipt, proof)
        (folder / 'receipt.json').write_bytes(runner.encoded(receipt))
        (checkpoint / 'resource-proof.json').write_bytes(runner.encoded(proof))
        (checkpoint / 'trainer_state.json').write_text(json.dumps({'global_step': steps}))
        (checkpoint / 'adapter.safetensors').write_bytes(b'isolated-fixture-not-a-model')
        runner.checkpoint_receipt(checkpoint, receipt['binding'])
        manifest['runs'][name] = {'receipt': str((folder / 'receipt.json').relative_to(root)),
            'receipt_sha256': runner.sha_file(folder / 'receipt.json'), 'checkpoint': str(checkpoint.relative_to(root)),
            'checkpoint_receipt_sha256': runner.sha_file(checkpoint / 'kairos-checkpoint.json'),
            'proof_sha256': runner.sha_file(checkpoint / 'resource-proof.json')}
    return manifest, binding


def test_same_measured_recipe_can_gate_public100_without_claiming_100_training(tmp_path):
    manifest, binding = fixture_pilot(tmp_path)
    manifest['comparison'] = resource.inspect_pilot(tmp_path, manifest)
    path = tmp_path / 'resource-acceptance.json'; path.write_bytes(runner.encoded(manifest))
    public = {**binding, 'study': 'public100', 'planned_steps': 40,
              'corpus_sha256': '1' * 64, 'admission_index_sha256': '2' * 64}
    result = resource.verify_acceptance(path, runner.sha_file(path), public)
    assert result['passed'] is True and result['full_corpus_training_complete'] is False
    assert result['repair_effectiveness_verified'] is False
    public['max_sequence'] = 4096
    with pytest.raises(ValueError, match='recipe'): resource.verify_acceptance(path, runner.sha_file(path), public)


@pytest.mark.parametrize('failure', ['memory', 'unchanged_adapter', 'different_rng', 'wrong_resume', 'wrong_data', 'incomplete'])
def test_failed_or_unrelated_pilots_cannot_authorize_training(tmp_path, failure):
    def mutate(name, receipt, proof):
        if name != 'resumed': return
        if failure == 'memory': receipt['resource_fit_verified'] = False
        elif failure == 'unchanged_adapter': receipt['adapter_updated'] = False
        elif failure == 'different_rng': proof['rng'] = 'f' * 64
        elif failure == 'wrong_resume': receipt['resumed_from_receipt_sha256'] = '0' * 64
        elif failure == 'wrong_data': receipt['binding']['corpus_sha256'] = '0' * 64
        elif failure == 'incomplete': receipt['completed_steps'] = 19
    manifest, binding = fixture_pilot(tmp_path, mutate)
    if failure in {'wrong_resume', 'wrong_data', 'incomplete'}:
        with pytest.raises(ValueError): resource.inspect_pilot(tmp_path, manifest)
    else:
        manifest['comparison'] = resource.inspect_pilot(tmp_path, manifest)
        assert manifest['comparison']['passed'] is False
        path = tmp_path / 'resource-acceptance.json'; path.write_bytes(runner.encoded(manifest))
        with pytest.raises(ValueError): resource.verify_acceptance(path, runner.sha_file(path), binding)


def test_corrupt_checkpoint_bytes_reject_before_comparison(tmp_path):
    manifest, _ = fixture_pilot(tmp_path)
    (tmp_path / 'full/checkpoint-20/adapter.safetensors').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='bytes differ'): resource.inspect_pilot(tmp_path, manifest)


def test_two_example_resource_path_never_bypasses_full_training(tmp_path, monkeypatch):
    corpus = {'version': 'coding-reviewed-example-set014-v1', 'training_ready': False,
              'train': [example(1), example(2)], 'development': [], 'locked_evaluation_families': []}
    path = tmp_path / 'corpus.json'; path.write_bytes(runner.encoded(corpus))
    monkeypatch.setattr(runner, 'verify_admission_bundle', lambda *args: {'verified_rows': 2})
    args = SimpleNamespace(study='resource2', action='doctor', profile='14B', corpus=path,
                           corpus_sha256=runner.sha_file(path), admission_directory=tmp_path, admission_index_sha256='a' * 64)
    assert len(runner.admitted_inputs(args)[0]['train']) == 2
    args.action = 'train'
    with pytest.raises(ValueError, match='never full training'): runner.admitted_inputs(args)
    args.action = 'fit'; args.profile = '7B'
    with pytest.raises(ValueError, match='14B'): runner.admitted_inputs(args)


def test_resource_precision_keeps_large_frozen_matrices_half_and_norm_vectors_full():
    class Parameter:
        def __init__(self,dtype,ndim):self.dtype=dtype;self.ndim=ndim;self.requires_grad=True;self.data=self
        def to(self,dtype):return Parameter(dtype,self.ndim)
    embedding=Parameter('float32',2);head=Parameter('bfloat16',2)
    norm=Parameter('float16',1);quantized=Parameter('uint8',2)
    parameters=[embedding,head,norm,quantized]
    class Module:
        def __init__(self,parameter):self.parameter=parameter
        def parameters(self):return [self.parameter]
    class Model:
        def parameters(self):return parameters
        def get_input_embeddings(self):return Module(embedding)
        def get_output_embeddings(self):return Module(head)
        def enable_input_require_grads(self):self.inputs_enabled=True
        def gradient_checkpointing_enable(self,**kwargs):self.checkpoint_options=kwargs
    torch=SimpleNamespace(float32='float32',float16='float16',bfloat16='bfloat16')
    model=resource.prepare_resource_base(Model(),torch)
    assert all(parameter.requires_grad is False for parameter in parameters)
    assert embedding.data.dtype==head.data.dtype=='float16'
    assert norm.data.dtype=='float32' and quantized.data.dtype=='uint8'
    assert model.inputs_enabled and model.checkpoint_options=={'gradient_checkpointing_kwargs':{'use_reentrant':False}}


def test_transformers_config_object_and_dictionary_share_strict_nf4_gate():
    expected = {'bnb_4bit_quant_type': 'nf4', 'bnb_4bit_use_double_quant': True}
    class ConfigObject:
        def to_dict(self): return dict(expected)
    for config in (expected, ConfigObject()):
        model = SimpleNamespace(config=SimpleNamespace(quantization_config=config), is_loaded_in_4bit=True)
        assert runner.validate_quantized_model(model) == expected


@pytest.mark.parametrize('config', [None, [], {'bnb_4bit_quant_type': 'fp4', 'bnb_4bit_use_double_quant': True},
    {'bnb_4bit_quant_type': 'nf4', 'bnb_4bit_use_double_quant': False},
    {'bnb_4bit_quant_type': 'nf4', 'bnb_4bit_use_double_quant': 1}])
def test_invalid_quantization_configuration_is_still_rejected(config):
    model = SimpleNamespace(config=SimpleNamespace(quantization_config=config), is_loaded_in_4bit=True)
    with pytest.raises(ValueError, match='frozen NF4 profile'): runner.validate_quantized_model(model)


def test_config_serializer_cannot_bypass_mapping_or_actual_model_gate():
    invalid = SimpleNamespace(to_dict=lambda: [])
    model = SimpleNamespace(config=SimpleNamespace(quantization_config=invalid), is_loaded_in_4bit=True)
    with pytest.raises(ValueError): runner.validate_quantized_model(model)
    model.config.quantization_config = {'bnb_4bit_quant_type': 'nf4', 'bnb_4bit_use_double_quant': True}
    model.is_loaded_in_4bit = False
    with pytest.raises(ValueError): runner.validate_quantized_model(model)


def test_supervised_positions_keep_every_nonmasked_causal_target():
    assert resource.supervised_positions([-100, -100, 7, 8, -100, 9, -100]) == [1, 2, 4]
    assert resource.supervised_positions([-100, 0]) == [0]


@pytest.mark.parametrize('labels', [[], [-100], [-100, -100], [1, 2], [-100, -1], [-100, True], [-100, 1.5]])
def test_supervised_positions_reject_invalid_or_empty_objectives(labels):
    with pytest.raises(ValueError): resource.supervised_positions(labels)


def test_resource_transfer_rejects_more_target_logits_than_actually_measured(tmp_path):
    manifest,binding=fixture_pilot(tmp_path)
    manifest['comparison']=resource.inspect_pilot(tmp_path,manifest)
    path=tmp_path/'resource-acceptance.json';path.write_bytes(runner.encoded(manifest))
    smaller={**binding,'study':'public100','planned_steps':40,'max_supervised_tokens':225}
    assert resource.verify_acceptance(path,runner.sha_file(path),smaller)['passed']
    larger={**smaller,'max_supervised_tokens':351}
    with pytest.raises(ValueError,match='memory demand'):resource.verify_acceptance(path,runner.sha_file(path),larger)
    with pytest.raises(ValueError,match='memory demand'):resource.verify_acceptance(path,runner.sha_file(path),{**smaller,'max_supervised_tokens':True})


def test_pytorch_cuda_alloc_conf_expandable_segments_configured():
    import os
    assert os.environ.get('PYTORCH_CUDA_ALLOC_CONF') == 'expandable_segments:True'


def test_receipt_with_peak_allocated_bytes_passes_pilot_inspection(tmp_path):
    def mutate(name, receipt, proof):
        receipt['peak_reserved_bytes'] = 12_000_000_000
        receipt['peak_allocated_bytes'] = 9_500_000_000
        receipt['gpu_total_bytes'] = 15_637_086_208
        receipt['vram_headroom_fraction'] = 1 - (12_000_000_000 / 15_637_086_208)
    manifest, binding = fixture_pilot(tmp_path, mutate)
    manifest['comparison'] = resource.inspect_pilot(tmp_path, manifest)
    assert manifest['comparison']['passed'] is True
    path = tmp_path / 'resource-acceptance.json'
    path.write_bytes(runner.encoded(manifest))
    public = {**binding, 'study': 'public100', 'planned_steps': 40,
              'corpus_sha256': '1' * 64, 'admission_index_sha256': '2' * 64}
    result = resource.verify_acceptance(path, runner.sha_file(path), public)
    assert result['passed'] is True

