"""Isolated fixtures test the investigation boundary; never published as model evidence."""
import json
from pathlib import Path
from uuid import uuid4
import os
from concurrent.futures import ThreadPoolExecutor
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from kairos_api.investigations.contracts import Action
from kairos_api.investigations.patches import apply_patch, source_path
from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.routes import create_investigation_router
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.model_runtime import digest

PATCH='--- a/source/value.py\n+++ b/source/value.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'


@pytest.fixture
def registry(tmp_path):
    root=tmp_path/'runtime';directory=root/'cases'/'fixture';source=directory/'source'/'source';source.mkdir(parents=True)
    (source/'value.py').write_text('value = 1\n')
    (directory/'reference.patch').write_text(PATCH);(directory/'test.patch').write_text('')
    import hashlib
    case={'id':'fixture','qualified':True,'title':'Isolated test fixture','issue':'Fix value', 'repository':'fixture',
          'revision':'fixture-v1','entry_files':['source/value.py'],'approved_prefix':'source/','split':'development',
          'source_digest':tree_hash(directory/'source'),'reference_digest':hashlib.sha256(PATCH.encode()).hexdigest(),
          'verification_digest':hashlib.sha256(b'').hexdigest()}
    manifest=tmp_path/'cases.json';manifest.write_text(json.dumps({'version':'repository-cases-v1','cases':[case]}))
    return CaseRegistry(manifest,root)


@pytest.fixture
def repository(tmp_path,registry):
    url=os.environ.get('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required')
    schema='investigations_'+uuid4().hex
    with psycopg.connect(url,autocommit=True) as connection: connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    repo=InvestigationRepository(make_conninfo(url,options='-c search_path='+schema),tmp_path/'blobs',registry)
    repo.initialize();yield repo
    with psycopg.connect(url,autocommit=True) as connection: connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def enqueue(repository,key='key',configuration='loop-v1'):
    return repository.enqueue('tenant-a',key,'fixture',configuration)


def expire(repository,identifier,deadline=False):
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_investigations SET lease_expires_at=clock_timestamp()-interval '1 second'"+(",deadline_at=clock_timestamp()-interval '1 second'" if deadline else '')+' WHERE id=%s',(identifier,))


class WorkspaceFixture:
    def __init__(self,registry,case): self.case=case
    def read(self,*args): return {'text':'value = 1'}
    def propose(self,patch):
        if patch!='valid': raise ValueError('Invalid fixture patch')
        return {'files':['source/value.py']}
    def propose_edits(self,edits): return {**self.propose(edits[0]['new']),'patch':edits[0]['new']}
    def checks(self,timeout=120): return {'passed':True,'environment_error':False,'returncode':0}
    def close(self): pass


class ProviderFixture:
    def __init__(self,actions): self.actions=iter(actions);self.calls=0
    def prepare(self,*args): return {'messages':[]},{'selection':'fixture'}
    def __call__(self,*args):
        self.calls+=1
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(next(self.actions))}}]}


def test_durable_command_identity_and_tenant_isolation(repository):
    record=enqueue(repository)
    assert enqueue(repository)['id']==record['id']
    with pytest.raises(HTTPException): enqueue(repository,configuration='baseline-v1')
    with pytest.raises(HTTPException) as error: repository.read(record['id'],'tenant-b')
    assert error.value.status_code==404
    with pytest.raises(HTTPException): repository.read(record['id'],public=True)
    restarted=InvestigationRepository(repository.database_url,repository.blobs.root,repository.registry)
    assert restarted.read(record['id'],'tenant-a')['integrity']['verified']


def test_single_global_slot_under_concurrent_claim(repository):
    enqueue(repository);enqueue(repository,'second')
    with ThreadPoolExecutor(max_workers=4) as executor:
        claims=list(executor.map(repository.claim,['a','b','c','d']))
    assert sum(c is not None for c in claims)==1


def test_unknown_dispatch_never_repeats(repository):
    record=enqueue(repository);job=repository.claim('first')
    repository.begin(job,'model','dispatch',{'messages':[]})
    expire(repository,record['id']);assert repository.claim('next') is None
    result=repository.read(record['id'],'tenant-a')
    assert result['status']=='unknown' and result['model_calls']==1
    with pytest.raises(RuntimeError): repository.capture(job,1,{'stale':True})


def test_captured_response_continues_without_another_model_call(repository):
    record=enqueue(repository);job=repository.claim('first')
    seq=repository.begin(job,'model','dispatch',{})
    response={'choices':[{'finish_reason':'stop','message':{'content':'{"action":"final_result","summary":"No evidence"}'}}]}
    repository.capture(job,seq,response);expire(repository,record['id'])
    provider=ProviderFixture([])
    result=InvestigationWorker(repository,provider,WorkspaceFixture).run_once()
    assert result['outcome']=='no_patch' and provider.calls==0 and result['claims']==2


def test_success_requires_a_patch_and_recorded_checks(repository):
    enqueue(repository)
    provider=ProviderFixture([{'action':'propose_patch','edits':[{'path':'source/value.py','old':'value = 1','new':'valid'}]},{'action':'final_result','summary':'Candidate ready'}])
    result=InvestigationWorker(repository,provider,WorkspaceFixture).run_once()
    assert result['outcome']=='verified_repair' and result['check_count']==1 and result['integrity']['verified']
    assert result['model_calls']==2


def test_final_claim_cannot_manufacture_a_repair(repository):
    enqueue(repository)
    result=InvestigationWorker(repository,ProviderFixture([{'action':'final_result','summary':'I fixed it'}]),WorkspaceFixture).run_once()
    assert result['outcome']=='no_patch' and result['check_count']==0


def test_invalid_patch_is_preserved(repository):
    enqueue(repository,configuration='baseline-v1')
    result=InvestigationWorker(repository,ProviderFixture([{'action':'propose_patch','edits':[{'path':'source/value.py','old':'value = 1','new':'invalid'}]}]),WorkspaceFixture).run_once()
    assert result['outcome']=='invalid_patch'
    assert result['steps'][-1]['request']['body']['edits'][0]['new']=='invalid'


def test_cancellation_fences_active_worker(repository):
    record=enqueue(repository);job=repository.claim('first')
    assert repository.cancel(record['id'],'tenant-a')['status']=='cancelled'
    with pytest.raises(RuntimeError): repository.begin(job,'model','dispatch',{})


def test_database_deadline_blocks_new_dispatch(repository):
    record=enqueue(repository);job=repository.claim('first')
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_investigations SET deadline_at=clock_timestamp()-interval '1 second' WHERE id=%s",(record['id'],))
    with pytest.raises(TimeoutError): repository.begin(job,'model','dispatch',{})
    assert repository.finish(job,'no_patch')['status']=='timed_out'


def test_call_and_patch_budgets_are_transactional(repository):
    enqueue(repository,configuration='baseline-v1');job=repository.claim('first')
    seq=repository.begin(job,'model','dispatch',{});repository.capture(job,seq,{})
    with pytest.raises(ValueError): repository.begin(job,'model','dispatch',{})
    seq=repository.begin(job,'tool','propose_patch',{});repository.capture(job,seq,{})
    with pytest.raises(ValueError): repository.begin(job,'tool','propose_patch',{})


def test_artifact_corruption_blocks_publication(repository):
    record=enqueue(repository);job=repository.claim('first')
    seq=repository.begin(job,'context','selection',{});repository.capture(job,seq,{'evidence':'original'})
    result=repository.finish(job,'no_patch')
    key=result['steps'][0]['result']['sha256'];(repository.blobs.root/key).write_text('{}')
    assert not repository.read(record['id'],'tenant-a')['integrity']['verified']
    with pytest.raises(HTTPException): repository.publish(record['id'],'tenant-a')


def test_source_changes_are_rejected(registry):
    case=registry.get('fixture');registry.verify(case)
    (registry.directory(case)/'source/source/value.py').write_text('changed')
    with pytest.raises(ValueError,match='Source snapshot'): registry.verify(case)


@pytest.mark.parametrize('name',['../secret.py','source/../../secret.py','source/.env.py','source/tests/test.py','source/link.py','/source/file.py','source\\value.py'])
def test_paths_and_symlinks_are_rejected(tmp_path,name):
    (tmp_path/'source').mkdir();(tmp_path/'source/link.py').symlink_to('/etc/passwd')
    with pytest.raises(ValueError): source_path(tmp_path,'source/',name)


def test_patch_is_applied_only_to_disposable_copy(tmp_path):
    original=tmp_path/'original';copy=tmp_path/'copy'
    (original/'source').mkdir(parents=True);(original/'source/value.py').write_text('value = 1\n')
    import shutil
    shutil.copytree(original,copy)
    result=apply_patch(copy,'source/',PATCH)
    assert result['added']==1 and (copy/'source/value.py').read_text()=='value = 2\n'
    assert (original/'source/value.py').read_text()=='value = 1\n'
    with pytest.raises(ValueError): apply_patch(copy,'source/',PATCH.replace('source/value.py','tests/value.py'))


def test_replay_and_public_routes_do_not_execute_tools(repository):
    record=enqueue(repository);job=repository.claim('first');repository.finish(job,'no_patch')
    app=FastAPI();app.include_router(create_investigation_router(lambda:'tenant-a',lambda:'key',lambda:'tenant-a',lambda:repository))
    client=TestClient(app)
    assert client.get('/api/public/investigations/'+record['id']).status_code==404
    assert client.post('/api/investigations/'+record['id']+'/publish').status_code==200
    replay=client.get('/api/investigations/'+record['id']+'/replay').json()
    assert replay['tool_executions']==0 and replay['network_calls']==0
    assert client.get('/api/public/investigations/'+record['id']+'/bundle').status_code==200
    assert client.post('/api/investigations',json={'task_id':'fixture','url':'http://attacker/'}).status_code==422
    assert client.get('/api/public/investigations/'+record['id']+'/patch').status_code==404


def test_pending_safe_tool_can_resume_but_not_change_request(repository):
    record=enqueue(repository);job=repository.claim('first')
    seq=repository.begin(job,'tool','search',{'query':'value'})
    expire(repository,record['id']);recovered=repository.claim('second')
    assert repository.begin(recovered,'tool','search',{'query':'value'})==seq
    with pytest.raises(RuntimeError): repository.begin(recovered,'tool','search',{'query':'different'})
    repository.capture(recovered,seq,{'matches':[]})
    with pytest.raises(RuntimeError): repository.capture(job,seq,{'stale':True})


def test_transport_failure_keeps_unknown_dispatch(repository):
    enqueue(repository)
    class BrokenProvider(ProviderFixture):
        def __call__(self,*args): raise ConnectionError('lost response')
    result=InvestigationWorker(repository,BrokenProvider([]),WorkspaceFixture).run_once()
    assert result['status']=='unknown' and result['outcome']=='unknown_dispatch'
    assert result['steps'][-1]['state']=='pending' and result['model_calls']==1


def test_invalid_response_remains_exact(repository):
    enqueue(repository)
    class InvalidProvider(ProviderFixture):
        def __call__(self,*args): return {'choices':[{'finish_reason':'length','message':{'content':'{"action":'}}]}
    result=InvestigationWorker(repository,InvalidProvider([]),WorkspaceFixture).run_once()
    assert result['outcome']=='invalid_response'
    assert result['steps'][-1]['result']['body']['choices'][0]['message']['content']=='{"action":'


def test_unknown_dispatch_survives_expired_deadline(repository):
    record=enqueue(repository);job=repository.claim('first');repository.begin(job,'model','dispatch',{})
    expire(repository,record['id'],deadline=True)
    assert repository.claim('second') is None
    assert repository.read(record['id'],'tenant-a')['outcome']=='unknown_dispatch'


def test_configuration_tampering_is_detected(repository):
    record=enqueue(repository)
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_investigations SET config_snapshot=jsonb_set(config_snapshot,'{version}','\"tampered\"') WHERE id=%s",(record['id'],))
    assert not repository.read(record['id'],'tenant-a')['integrity']['verified']


def test_reference_and_verification_are_not_readable_by_tools(registry):
    from kairos_api.investigations.sandbox import Workspace
    workspace=Workspace(registry,registry.get('fixture'))
    try:
        for path in ['../reference.patch','verify.py','../test.patch']:
            with pytest.raises(ValueError): workspace.read(path)
        assert workspace.search('value')['matches']
        proposal=workspace.propose_edits([{'path':'source/value.py','old':'value = 1','new':'value = 2'}])
        assert '+value = 2' in proposal['patch']
        with pytest.raises(ValueError): workspace.propose_edits([{'path':'source/value.py','old':'value','new':'other'},{'path':'source/value.py','old':'value = 1','new':'value = 2'}])
    finally: workspace.close()


def test_real_docker_verifier_is_nonroot_readonly_and_network_disabled(registry):
    if os.environ.get('KAIROS_TEST_INVESTIGATION_DOCKER')!='1': pytest.skip('Set KAIROS_TEST_INVESTIGATION_DOCKER=1 for real Docker isolation check')
    from kairos_api.investigations.sandbox import Workspace
    import subprocess
    case=registry.get('fixture');case['image']=subprocess.check_output(['docker','image','inspect',os.environ.get('KAIROS_TEST_INVESTIGATION_IMAGE','kairos-api:build002'),'--format','{{.Id}}'],text=True).strip()
    probe="""import os,socket,pathlib
from source.value import value
assert value==2
assert os.getuid()==10001
assert not pathlib.Path('/var/run/docker.sock').exists()
try: pathlib.Path('/workspace/forbidden').write_text('x')
except OSError: pass
else: raise AssertionError('Writable verifier snapshot')
sock=socket.socket();sock.settimeout(.2)
try: sock.connect(('1.1.1.1',80))
except OSError: pass
else: raise AssertionError('Outbound networking permitted')
print('Non-root, read-only source, no Docker socket, no outbound network')
"""
    case['command']=['python','-c',probe]
    workspace=Workspace(registry,case)
    try:
        workspace.propose(PATCH);result=workspace.checks()
        assert result['passed'],result
        assert 'Non-root' in result['stdout']
        case['command']=['python','-c',"import sys;sys.stdout.write('x'*1200000);sys.stdout.flush()"]
        bounded=workspace.checks();assert not bounded['passed'] and len(bounded['stdout'].encode())<=24000
        case['command']=['python','-c','import kairos_deliberately_missing_dependency']
        missing=workspace.checks()
        assert not missing['passed'] and not missing['environment_error'] and 'ModuleNotFoundError' in missing['stderr']
        case['image']='kairos-investigation-nonexistent:'+uuid4().hex
        unavailable=workspace.checks()
        assert not unavailable['passed'] and unavailable['environment_error'] and unavailable['returncode']==125
        assert 'never' in unavailable['stderr'] or 'No such image' in unavailable['stderr']
    finally: workspace.close()


def test_real_model_enforces_nested_schema():
    if os.environ.get('KAIROS_TEST_INVESTIGATION_PROVIDER')!='1': pytest.skip('Set KAIROS_TEST_INVESTIGATION_PROVIDER=1 for actual local schema probe')
    from kairos_api.investigations.model import LocalInvestigator
    schema={'type':'object','properties':{'probe':{'const':'pinned'}},'required':['probe'],'additionalProperties':False}
    response=LocalInvestigator()({'messages':[{'role':'user','content':'Respond with an array of three numbers.'}],
        'response_format':{'type':'json_schema','json_schema':{'name':'contract_probe','strict':True,'schema':schema}},
        'max_tokens':40,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}})
    assert json.loads(response['choices'][0]['message']['content'])=={'probe':'pinned'}


def test_corrupt_patch_download_is_rejected():
    class CorruptRepository:
        def read(self, *args, **kwargs):
            return {'integrity': {'verified': False}, 'steps': []}
    app = FastAPI()
    app.include_router(create_investigation_router(lambda: 'tenant', lambda: 'key', lambda: 'tenant', lambda: CorruptRepository()))
    client = TestClient(app)
    assert client.get('/api/public/investigations/corrupt/patch').status_code == 409
    assert client.get('/api/public/investigations/corrupt/bundle').status_code == 409
