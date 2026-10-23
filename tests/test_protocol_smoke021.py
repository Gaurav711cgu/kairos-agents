from types import SimpleNamespace
import pytest
from scripts.coding_protocol_smoke021 import package,run
from scripts.source_edit_protocol021 import training_messages
from test_coding_train014 import row


def test_smoke_uses_shared_messages_without_assistant_targets():
    corpus={'train':[row(1,'one/repo'),row(2,'two/repo')],'development':[]}
    result=package(corpus)
    assert len(result['cases'])==2
    assert result['cases'][0]['messages']==training_messages(corpus['train'][0])
    assert [m['role'] for m in result['cases'][0]['messages']]==['system','user']
    assert result['generation']['calls_per_arm_case']==1
    assert 'known training' in result['scope']


@pytest.mark.parametrize('bad', [{'train':[],'development':[]},{'train':[row(1,'a/b'),row(2,'b/c')],'development':[row(3,'c/d')]}])
def test_other_membership_rejected(bad):
    with pytest.raises(ValueError):package(bad)


def test_gpu_dispatch_requires_explicit_flag_before_any_inputs(monkeypatch):
    monkeypatch.delenv('KAIROS_PROTOCOL_SMOKE_GPU',raising=False)
    with pytest.raises(RuntimeError,match='explicit approval'):run(SimpleNamespace())


def test_prior_output_never_redispatched(tmp_path,monkeypatch):
    monkeypatch.setenv('KAIROS_PROTOCOL_SMOKE_GPU','1')
    with pytest.raises(RuntimeError,match='Prior smoke'):run(SimpleNamespace(output=tmp_path))


@pytest.mark.parametrize('identity',['../escape','task-1'])
def test_unsafe_or_duplicate_case_identity_rejected(identity):
    corpus={'train':[row(1,'one/repo'),row(2,'two/repo')],'development':[]}
    corpus['train'][1]['instance_id']=identity
    with pytest.raises(ValueError,match='safe training identities'):package(corpus)


@pytest.fixture
def inference_adapter(tmp_path):
    import json,hashlib
    from scripts.coding_inference020 import sha
    from scripts.coding_protocol_smoke021 import verify_inference_adapter
    files={}
    for name in ('adapter_config.json','adapter_model.safetensors'):
        (tmp_path/name).write_bytes(b'fixture')
        files[name]={'bytes':7,'sha256':sha(tmp_path/name)}
    receipt={'version':'coding-checkpoint014-v1','binding':{'fixture':True},'files':{**files,'optimizer.pt':{'bytes':99,'sha256':'0'*64}}}
    (tmp_path/'kairos-checkpoint.json').write_text(json.dumps(receipt))
    return tmp_path,sha(tmp_path/'kairos-checkpoint.json'),receipt['binding'],verify_inference_adapter


def test_inference_artifact_verifies_without_claiming_optimizer_resume(inference_adapter):
    path,digest,binding,verify=inference_adapter
    assert 'optimizer.pt' in verify(path,digest,binding)['files']
    assert not (path/'optimizer.pt').exists()


@pytest.mark.parametrize('change',['corrupt','extra','missing','symlink','binding'])
def test_inference_artifact_rejects_mismatches(inference_adapter,change):
    path,digest,binding,verify=inference_adapter
    if change=='corrupt':(path/'adapter_model.safetensors').write_bytes(b'changed')
    if change=='extra':(path/'optimizer.pt').write_bytes(b'unreviewed')
    if change=='missing':(path/'adapter_config.json').unlink()
    if change=='symlink':(path/'extra').symlink_to(path/'adapter_config.json')
    if change=='binding':binding={'fixture':False}
    with pytest.raises(ValueError):verify(path,digest,binding)
