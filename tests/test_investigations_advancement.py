"""Build004 control-plane regressions, using isolated PostgreSQL schemas."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from test_investigations import registry, repository, enqueue
from kairos_api.investigations.routes import create_investigation_router


def client_for(repo, tenant='tenant-a'):
    app=FastAPI()
    app.include_router(create_investigation_router(lambda:tenant,lambda:'key',lambda:tenant,lambda:repo))
    return TestClient(app)


def test_progress_is_scoped_and_contains_no_artifact_bodies(repository):
    record=enqueue(repository);job=repository.claim('worker')
    sequence=repository.begin(job,'model','dispatch',{'secret_prompt':'not in progress'})
    client=client_for(repository)
    response=client.get('/api/investigations/'+record['id']+'/progress')
    assert response.status_code==200
    body=response.json()
    assert body['phase']=='model_dispatch_pending' and body['latest_sequence']==sequence
    assert body['model_calls']==1 and body['status']=='running'
    assert 'steps' not in body and 'secret_prompt' not in response.text
    assert client_for(repository,'tenant-b').get('/api/investigations/'+record['id']+'/progress').status_code==404


def test_pagination_ties_and_scope(repository):
    ids=[enqueue(repository,str(i))['id'] for i in range(5)]
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_investigations SET created_at='2026-01-01T00:00:00Z'")
    client=client_for(repository); seen=[];cursor=None
    while True:
        response=client.get('/api/investigations',params={'limit':2,**({'cursor':cursor} if cursor else {})})
        assert response.status_code==200
        body=response.json();seen.extend(r['id'] for r in body['investigations'])
        cursor=body['next_cursor']
        if not cursor: break
    assert seen==sorted(ids,reverse=True)
    assert client_for(repository,'tenant-b').get('/api/investigations').json()['investigations']==[]
    assert client.get('/api/investigations?limit=101').status_code==422
    assert client.get('/api/investigations?cursor=garbage').status_code==422


def test_global_capacity_serializes_cross_tenant_enqueues_and_allows_retry(repository):
    def create(i):
        try: return repository.enqueue('tenant-'+str(i),str(i),'fixture','loop-v1')
        except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=8) as executor: results=list(executor.map(create,range(30)))
    accepted=[result for result in results if isinstance(result,dict)]
    assert len(accepted)==24 and results.count(429)==6
    first=next(i for i,r in enumerate(results) if isinstance(r,dict))
    assert create(first)['id']==results[first]['id']
    repository.cancel(accepted[0]['id'],'tenant-'+str(next(i for i,r in enumerate(results) if r is accepted[0])))
    assert isinstance(create(31),dict)


def test_private_download_integrity_and_tenant_guard(repository):
    record=enqueue(repository);job=repository.claim('worker')
    seq=repository.begin(job,'tool','propose_patch',{'edits':[]})
    repository.capture(job,seq,{'patch':'patch evidence'})
    repository.finish(job,'failed_checks')
    base='/api/investigations/'+record['id']
    client=client_for(repository)
    assert client.get(base+'/patch').text=='patch evidence'
    assert client.get(base+'/bundle').status_code==200
    assert client_for(repository,'tenant-b').get(base+'/bundle').status_code==404
    assert client.get('/api/public/investigations/'+record['id']+'/bundle').status_code==404
    stored=repository.read(record['id'],'tenant-a')
    (repository.blobs.root/stored['steps'][0]['result']['sha256']).write_text('{}')
    assert client.get(base+'/patch').status_code==409
    assert client.get(base+'/bundle').status_code==409


def test_snapshot_edits_bind_original_digest_range_and_captured_excerpt(registry):
    from kairos_api.investigations.sandbox import Workspace
    workspace=Workspace(registry,registry.get('fixture'))
    try:
        source=workspace.read_original('source/value.py');ref=source['reference']
        edit={**ref,'new':'value = 2\n'}
        result=workspace.propose_snapshot_edits([edit]);assert result['patch']
        assert workspace.read_original('source/value.py')['text']=='1: value = 1\n'
        assert workspace.read('source/value.py')['text']=='1: value = 2'
        with pytest.raises(ValueError,match='Stale'): workspace.propose_snapshot_edits([{**edit,'source_digest':'0'*64}])
        with pytest.raises(ValueError,match='escapes'): workspace.propose_snapshot_edits([{**edit,'end_line':2}])
        with pytest.raises(ValueError,match='captured'): workspace.propose_snapshot_edits([{**edit,'excerpt_id':'0'*64}])
        with pytest.raises(ValueError): workspace.propose_snapshot_edits([{**edit,'path':'../reference.patch'}])
    finally: workspace.close()


def test_v4_checks_first_patch_before_next_call_and_recovers_references(repository):
    from kairos_api.investigations.sandbox import Workspace
    from kairos_api.investigations.worker import InvestigationWorker
    from test_investigations import ProviderFixture
    history=[]
    class WorkspaceChecks(Workspace):
        def checks(self,timeout=120):
            history.append('check')
            return {'passed':self.root.joinpath('source/value.py').read_text()=='value = 3\n','environment_error':False,'returncode':1}
    workspace=WorkspaceChecks(repository.registry,repository.registry.get('fixture'))
    ref=workspace.read_original('source/value.py')['reference'];workspace.close()
    class Provider(ProviderFixture):
        def prepare(self,case,configuration,observations,budgets):
            if self.calls==1:
                assert history==['check']
                assert any(o['action']=='run_checks' and not o['result']['passed'] for o in observations)
            return {},{'selection':{'observations':observations}}
    provider=Provider([{'action':'propose_patch','edits':[{**ref,'new':'value = 2\n'}]},{'action':'propose_patch','edits':[{**ref,'new':'value = 3\n'}]}])
    record=repository.enqueue('tenant-a','feedback','fixture','loop-v4')
    result=InvestigationWorker(repository,provider,WorkspaceChecks).run_once()
    assert result['id']==record['id'] and result['outcome']=='verified_repair'
    assert result['model_calls']==2 and result['check_count']==2 and result['patch_count']==2


def test_rejected_v4_edit_is_recorded_without_consuming_applied_budget(repository):
    record=repository.enqueue('tenant-a','rejection','fixture','loop-v4');job=repository.claim('worker')
    for _ in range(3):
        seq=repository.begin(job,'tool','propose_patch',{'edits':[]})
        repository.capture(job,seq,{'error':'Invalid source reference'})
    assert repository.read(record['id'],'tenant-a')['patch_count']==0
    for _ in range(2):
        seq=repository.begin(job,'tool','propose_patch',{'edits':[]});repository.capture(job,seq,{'patch':'candidate'})
    seq=repository.begin(job,'tool','propose_patch',{'edits':[]})
    with pytest.raises(ValueError): repository.capture(job,seq,{'patch':'third'})


def test_pool_reuses_connections_and_rolls_back_failed_transactions(repository):
    from kairos_api.investigations.repository import InvestigationRepository
    pooled=InvestigationRepository(repository.database_url,repository.blobs.root,repository.registry,pooled=True)
    try:
        record=enqueue(repository)
        # The pool may grow and rotate FIFO connections. Warm every slot before
        # asserting reuse rather than requiring consecutive checkouts to share a PID.
        with ExitStack() as stack:
            connections=[stack.enter_context(pooled.connect()) for _ in range(pooled.pool.max_size)]
            pids={connection.execute('SELECT pg_backend_pid() AS id').fetchone()['id'] for connection in connections}
        assert len(pids)==pooled.pool.max_size
        opened=pooled.pool.get_stats()['connections_num']
        for _ in range(2*pooled.pool.max_size):
            with pooled.connect() as connection:
                assert connection.execute('SELECT pg_backend_pid() AS id').fetchone()['id'] in pids
        assert pooled.pool.get_stats()['connections_num']==opened
        with pytest.raises(RuntimeError):
            with pooled.connect() as connection:
                connection.execute("UPDATE kairos_investigations SET status='cancelled' WHERE id=%s",(record['id'],))
                raise RuntimeError('rollback')
        with pooled.connect() as connection:
            assert connection.execute('SELECT pg_backend_pid() AS id').fetchone()['id'] in pids
            assert connection.execute('SELECT status FROM kairos_investigations WHERE id=%s',(record['id'],)).fetchone()['status']=='queued'
    finally: pooled.close()


def test_independent_drafts_freeze_candidates_before_checks(repository):
    from kairos_api.investigations.sandbox import Workspace
    from kairos_api.investigations.worker import InvestigationWorker
    from test_investigations import ProviderFixture
    class WorkspaceChecks(Workspace):
        def checks(self,timeout=120):
            assert provider.calls==6
            return {'passed':self.root.joinpath('source/value.py').read_text()=='value = 2\n','environment_error':False,'returncode':0}
    workspace=WorkspaceChecks(repository.registry,repository.registry.get('fixture'));ref=workspace.read_original('source/value.py')['reference'];workspace.close()
    class Provider(ProviderFixture):
        def prepare(self,case,configuration,observations,budgets):
            assert len(observations)==1 and observations[0]['action']=='initial_source'
            return {},{'selection':{'observations':observations}}
    provider=Provider([{'action':'propose_patch','edits':[{**ref,'new':f'value = {n}\n'}]} for n in (2,3,4,5,6,7)])
    record=repository.enqueue('tenant-a','drafts','fixture','drafts-v4')
    result=InvestigationWorker(repository,provider,WorkspaceChecks).run_once()
    assert result['model_calls']==6 and result['patch_count']==2 and result['check_count']==2
    assert result['outcome']=='verified_repair'
    drafts=[s for s in result['steps'] if s['name']=='draft_candidate']
    checks=[s for s in result['steps'] if s['name']=='run_checks']
    assert len(drafts)==6 and sum(d['result']['body']['selected'] for d in drafts)==2
    assert max(d['seq'] for d in drafts)<min(c['seq'] for c in checks)
    assert 'value = 2' in client_for(repository).get('/api/investigations/'+record['id']+'/patch').text


def test_v4_context_omits_complete_regions_and_retains_verdict(monkeypatch):
    import json
    import httpx
    from kairos_api.investigations.model import LocalInvestigator
    def handle(request):
        body=json.loads(request.content)
        if request.url.path=='/apply-template':return httpx.Response(200,json={'prompt':json.dumps(body['messages'])})
        return httpx.Response(200,json={'tokens':[1]*(len(body['content'])//4)})
    real_client=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handle),**kwargs))
    observations=[{'action':'initial_source','result':{'text':''.join(f'{n}: full source line\n' for n in range(1,2001)),'reference':{'excerpt_id':'a'*64,'source_digest':'b'*64,'path':'source/value.py','start_line':1,'end_line':2000}}},{'action':'run_checks','result':{'passed':False,'returncode':1,'patch_digest':'b'*64,'stderr':'specific failure\n'*30}}]
    case={'issue':'Fix the behavior.','revision':'frozen','approved_prefix':'source/'}
    request,context=LocalInvestigator().prepare(case,'loop-v4',observations,{'calls_remaining':5})
    value=json.loads(request['messages'][1]['content'])
    assert value['issue']==case['issue'] and value['latest_verification']['passed'] is False
    assert context['omissions'] and context['rendered_input_tokens']+1024+32<=4096
    assert all('excerpt' not in observation for observation in value['observations'])


def test_loaded_model_mismatch_is_rejected_before_dispatch(repository):
    from kairos_api.investigations.worker import InvestigationWorker
    class WrongProfile:
        def verify_profile(self):raise ValueError('Loaded inference model differs from pinned profile')
        def __call__(self,*args):raise AssertionError('Dispatch must not occur')
    record=repository.enqueue('tenant-a','wrong-model','fixture','loop-v4')
    result=InvestigationWorker(repository,WrongProfile()).run_once()
    assert result['id']==record['id'] and result['model_calls']==0 and result['outcome']=='environment_failure'


def test_v4_rejects_joined_lines_and_invalid_python_before_checks(registry):
    from kairos_api.investigations.sandbox import Workspace
    workspace=Workspace(registry,registry.get('fixture'))
    try:
        ref=workspace.read_original('source/value.py')['reference']
        with pytest.raises(ValueError,match='syntax'):workspace.propose_snapshot_edits([{**ref,'new':'if True:\nvalue = 2\n'}])
        assert workspace.root.joinpath('source/value.py').read_text()=='value = 1\n'
    finally:workspace.close()


def test_baseline_v4_schema_excludes_read_actions_and_binds_visible_references(monkeypatch):
    import json,httpx
    from kairos_api.investigations.model import LocalInvestigator
    def handle(request):
        body=json.loads(request.content)
        return httpx.Response(200,json={'prompt':'rendered'}) if request.url.path=='/apply-template' else httpx.Response(200,json={'tokens':[1]*200})
    real_client=httpx.Client;monkeypatch.setattr(httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handle),**kwargs))
    reference={'path':'source/value.py','excerpt_id':'a'*64,'source_digest':'b'*64,'start_line':1,'end_line':1}
    request,context=LocalInvestigator().prepare({'issue':'Fix value','revision':'frozen','approved_prefix':'source/'},'baseline-v4',[{'action':'initial_source','result':{'text':'1: value = 1\n','reference':reference}}],{'calls_remaining':1})
    schema=request['response_format']['json_schema']['schema']
    assert set(schema['discriminator']['mapping'])=={'propose_patch','final_result'}
    assert schema['$defs']['SnapshotEdit']['properties']['excerpt_id']['enum']==['a'*64]
    observation=context['selection']['observations'][0]['result'];assert observation['lines']==[[1,'value = 1']] and 'text' not in observation


def test_study_verifier_zero_exit_without_completed_tests_is_not_a_repair(registry,monkeypatch):
    import subprocess
    from kairos_api.investigations.sandbox import Workspace
    case=registry.get('fixture');case.update(image='registered',command=['python','verify.py'],entry_lines={'source/value.py':1})
    workspace=Workspace(registry,case)
    def fake_run(argv,**kwargs):
        if argv[:2]==['docker','run']:
            kwargs['stdout'].write(b'no tests executed\n')
        return subprocess.CompletedProcess(argv,0)
    monkeypatch.setattr(subprocess,'run',fake_run)
    try:
        result=workspace.checks();assert not result['passed'] and result['verification_incomplete'] and result['returncode']==0
    finally:workspace.close()


def test_worker_waits_after_database_outage_without_redispatch():
    import psycopg
    from kairos_api.investigations.worker import serve
    class Worker:
        calls=0
        def run_once(self):
            self.calls+=1
            if self.calls==1:raise psycopg.OperationalError('database unavailable')
            raise KeyboardInterrupt()
    worker=Worker();waits=[]
    with pytest.raises(KeyboardInterrupt):serve(worker,waits.append)
    assert worker.calls==2 and waits==[2]


def test_snapshot_renderer_supplies_only_the_line_boundary(registry):
    from kairos_api.investigations.sandbox import Workspace
    workspace=Workspace(registry,registry.get('fixture'))
    try:
        ref=workspace.read_original('source/value.py')['reference']
        result=workspace.propose_snapshot_edits([{**ref,'new':'value = 2'}])
        assert workspace.root.joinpath('source/value.py').read_text()=='value = 2\n'
        assert '+value = 2\n' in result['patch']
        assert result['references'][0]['new']=='value = 2'
        with pytest.raises(ValueError,match='no change'):workspace.propose_snapshot_edits([{**ref,'new':'value = 1'}])
    finally:workspace.close()
