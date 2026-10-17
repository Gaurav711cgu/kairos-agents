"""No GPU allocation is allowed before complete corpus and checkpoint admission."""
from copy import deepcopy
import hashlib,json
import pytest
from scripts.coding_train014 import admit_corpus,admit_pilot,checkpoint_receipt,verify_checkpoint,tokenize_example,read_bound,sha_file,safe_path


def row(i,repository):
    return {'instance_id':'task-'+str(i),'family_id':repository+'#'+str(i),'repository':repository,'admission':{'independent_checks':True,'rights_reviewed':True,'family_resolved':True,'near_deduplicated':True,'action_replayed':True},'qualification_receipt_sha256':'a'*64,'rights_receipt_sha256':'b'*64,'family_receipt_sha256':'c'*64,'input':{'issue':'Fix target','original_source':[{'source_id':'S'+'a'*12,'path':'package/value.py','start_line':1,'end_line':1,'numbered_original_source':'1: value = 0\n'}],'instruction':'Edit source'},'assistant_target':{'action':'propose_patch','edits':[{'source_id':'S'+'a'*12,'start_line':1,'end_line':1,'new':'value = '+str(i)}]}}


def corpus():
    return {'version':'coding-admitted-corpus014-v1','training_ready':True,'exposure_inventory_sha256':'df992139ab624087f6141eb8401e78294ff6bcb203dfb76c3ab22e0bbfed6957','train':[row(i,'owner/repo'+str(i%5)) for i in range(200)],'development':[row(i,'other/development') for i in range(200,206)],'locked_evaluation_families':['eval#'+str(i) for i in range(30)]}


def test_underqualified_or_unreviewed_data_cannot_start_training():
    data=corpus();assert admit_corpus(data) is data
    for change in ['floor','rights','repository','exposure']:
        bad=deepcopy(data)
        if change=='floor':bad['train']=bad['train'][:3]
        elif change=='rights':bad['train'][0]['admission']['rights_reviewed']=False
        elif change=='repository':
            for r in bad['train']:r['repository']='one/repository'
        else:bad['exposure_inventory_sha256']='0'*64
        with pytest.raises(ValueError):admit_corpus(bad)


def test_untouched_families_and_repositories_stay_outside_training():
    data=corpus();data['locked_evaluation_families'][0]=data['train'][0]['family_id']
    with pytest.raises(ValueError,match='overlap'):admit_corpus(data)
    data=corpus();data['development'][0]['repository']='sympy/sympy'
    with pytest.raises(ValueError,match='leaked'):admit_corpus(data)


class Tokenizer:
    def apply_chat_template(self,messages,tokenize,add_generation_prompt):
        prefix=[1,2,3]
        return prefix if add_generation_prompt else prefix+[4,5,6]


def test_loss_masks_all_prompt_tokens_and_preserves_complete_target():
    result=tokenize_example(Tokenizer(),row(0,'r/r'))
    assert result['input_ids']==[1,2,3,4,5,6]
    assert result['labels']==[-100,-100,-100,4,5,6]
    with pytest.raises(ValueError,match='no truncation'):tokenize_example(Tokenizer(),row(0,'r/r'),maximum=5)


def test_template_prefix_drift_is_rejected():
    class Drift(Tokenizer):
        def apply_chat_template(self,messages,tokenize,add_generation_prompt):return [1,2,3] if add_generation_prompt else [1,9,3,4]
    with pytest.raises(ValueError,match='exact supervised suffix'):tokenize_example(Drift(),row(0,'r/r'))


def test_checkpoint_hash_and_experiment_binding_are_enforced(tmp_path):
    d=tmp_path/'checkpoint';d.mkdir();(d/'adapter.safetensors').write_bytes(b'fixture-only')
    binding={'profile':'7B','corpus_sha256':'a'*64};checkpoint_receipt(d,binding);sha=sha_file(d/'kairos-checkpoint.json')
    assert verify_checkpoint(d,sha,binding)['binding']==binding
    with pytest.raises(ValueError,match='identity'):verify_checkpoint(d,sha,{'profile':'14B'})
    (d/'adapter.safetensors').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='bytes differ'):verify_checkpoint(d,sha,binding)


def test_extra_checkpoint_files_and_path_escapes_are_rejected(tmp_path):
    (tmp_path/'adapter').write_bytes(b'a');checkpoint_receipt(tmp_path,{});sha=sha_file(tmp_path/'kairos-checkpoint.json')
    (tmp_path/'unexpected').write_bytes(b'b')
    with pytest.raises(ValueError,match='file set'):verify_checkpoint(tmp_path,sha,{})
    for name in ['../secret','/private/secret','x/../secret','x\\secret']:
        with pytest.raises(ValueError,match='Unsafe'):safe_path(tmp_path,name)


def test_changed_frozen_inputs_and_symlinks_are_rejected(tmp_path):
    p=tmp_path/'input.json';p.write_text('{}');original=sha_file(p)
    assert read_bound(p,original)=={}
    p.write_text('{"changed":true}')
    with pytest.raises(ValueError):read_bound(p,original)
    link=tmp_path/'alias';link.symlink_to(p)
    with pytest.raises(ValueError):read_bound(link,sha_file(p))


def test_full_training_requires_actual_fit_and_resume_acceptance():
    binding={'profile':'7B','planned_steps':25,'model_manifest_sha256':'a'*64}
    data={'version':'coding-pilot-acceptance014-v1','identity':{k:v for k,v in binding.items() if k!='planned_steps'},'resource_fit_verified':True,'resume_equivalence_verified':False,'comparison_receipt_sha256':'b'*64}
    with pytest.raises(ValueError,match='resume'):admit_pilot(data,binding)
    data['resume_equivalence_verified']=True;admit_pilot(data,binding)


def test_empty_context_and_unread_edit_ranges_cannot_be_training_examples():
    for mode in ['empty','range','line_number']:
        data=corpus();r=data['train'][0]
        if mode=='empty':r['input']['original_source']=[]
        elif mode=='range':r['assistant_target']['edits'][0]['end_line']=2
        else:r['input']['original_source'][0]['numbered_original_source']='2: value = 0\n'
        with pytest.raises(ValueError):admit_corpus(data)


def test_train_command_reaches_pilot_gate_before_loading_model(tmp_path, monkeypatch):
    """Exercise the real command preflight without allocating CUDA or weights."""
    import sys
    from types import ModuleType, SimpleNamespace
    from scripts import coding_train014 as runner

    scratch = tmp_path / 'scratch'
    model = scratch / 'model'
    model.mkdir(parents=True)
    weights = model / 'fixture.safetensors'
    weights.write_bytes(b'isolated-test-only-not-model-weights')
    dataset = scratch / 'corpus.json'
    dataset.write_text(json.dumps(corpus()))
    manifest = scratch / 'model-manifest.json'
    packages = {name: 'fixture' for name in ['torch', 'transformers', 'peft', 'accelerate', 'bitsandbytes']}
    manifest.write_text(json.dumps({'model': runner.MODELS['14B'][0], 'revision': runner.MODELS['14B'][1], 'quantization': 'nf4-double-quant', 'training_environment': packages, 'files': {'fixture.safetensors': {'sha256': sha_file(weights), 'bytes': weights.stat().st_size}}}))
    class NoModelAllocation:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            raise AssertionError('Model allocation happened before pilot admission')
    torch = ModuleType('torch')
    torch.cuda = SimpleNamespace(is_available=lambda: True, get_device_name=lambda _: 'fixture-GPU', get_device_capability=lambda _: (7, 5))
    torch.version = SimpleNamespace(cuda='fixture-CUDA')
    transformers = ModuleType('transformers')
    for name in ['AutoModelForCausalLM', 'AutoTokenizer', 'Trainer', 'TrainerCallback', 'TrainingArguments', 'DataCollatorForSeq2Seq']:
        setattr(transformers, name, NoModelAllocation)
    transformers.set_seed = lambda _: None
    peft = ModuleType('peft')
    for name in ['LoraConfig', 'get_peft_model', 'prepare_model_for_kbit_training']:
        setattr(peft, name, NoModelAllocation)
    for name, module in [('torch', torch), ('transformers', transformers), ('peft', peft)]:
        monkeypatch.setitem(sys.modules, name, module)
    # This test isolates the later pilot gate; admission integrity has its own
    # real command rejection and graph tests in test_coding_admission014.py.
    monkeypatch.setattr(runner, 'verify_admission_bundle', lambda *args: {'fixture_only': True})
    monkeypatch.setattr(runner.importlib.metadata, 'version', lambda _: 'fixture')
    monkeypatch.setattr(runner.os, 'environ', dict(runner.os.environ))
    args = SimpleNamespace(admission_directory=scratch / 'fixture-admission', admission_index_sha256='f' * 64, corpus=dataset, corpus_sha256=sha_file(dataset), model_manifest=manifest, model_manifest_sha256=sha_file(manifest), profile='14B', model_directory=model, output=scratch / 'output', scratch_root=scratch, scratch_bytes=20 * 1024**3, action='train', resume_checkpoint=None, pilot_evidence=scratch / 'missing-pilot.json', pilot_evidence_sha256='a' * 64, learning_rate=0.0001)
    with pytest.raises(ValueError, match='Frozen input hash, size or path differs'):
        runner.run(args)
    assert (args.output / 'intent.json').is_file()
