"""Actual PostgreSQL receipts and recovery; provider/checks are isolated fixtures."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from test_investigations import registry, repository
from kairos_api.investigations.contracts import GENERATION, generation_for
from kairos_api.investigations.routes import create_investigation_router
from kairos_api.investigations.sandbox import Workspace
from kairos_api.investigations.worker import InvestigationWorker


def test_v5_routes_acknowledge_frozen_generation_with_durable_retry(repository):
    app=FastAPI()
    app.include_router(create_investigation_router(lambda:'tenant-a',lambda:'stable-command',lambda:'tenant-a',lambda:repository))
    client=TestClient(app)
    payload={'task_id':'fixture','configuration':'loop-v5'}
    first=client.post('/api/investigations',json=payload)
    assert first.status_code==202
    record=first.json()
    assert record['config_snapshot']['generation']==generation_for('loop-v5')
    assert record['config_snapshot']['generation']['temperature']==0
    assert record['config_snapshot']['budgets']=={'max_calls':6,'max_patches':2,'max_checks':2,'seconds':600}
    assert client.post('/api/investigations',json=payload).json()['id']==record['id']
    assert client.post('/api/investigations',json={**payload,'configuration':'baseline-v5'}).status_code==409
    stored=repository.read(record['id'],'tenant-a')
    assert stored['integrity']['verified'] and stored['config_snapshot']==record['config_snapshot']
    legacy=repository.enqueue('tenant-b','historical','fixture','baseline-v4')
    assert legacy['config_snapshot']['generation']==GENERATION
    baseline=repository.enqueue('tenant-c','new-baseline','fixture','baseline-v5')
    assert baseline['config_snapshot']['budgets']['max_calls']==1


def test_v5_applied_patch_budget_ignores_rejections_and_enforces_acceptances(repository):
    record=repository.enqueue('tenant-a','patch-counter','fixture','loop-v5')
    job=repository.claim('counter-worker')
    for index in range(3):
        sequence=repository.begin(job,'tool','propose_patch',{'fixture_rejection':index})
        repository.capture(job,sequence,{'error':'Fixture rejected source fragment'})
    assert repository.read(record['id'],'tenant-a')['patch_count']==0
    workspace=Workspace(repository.registry,repository.registry.get('fixture'))
    try:
        source=workspace.read_original('source/value.py');reference=source['reference'];handle='S'+reference['excerpt_id'][:12]
        for replacement in ('value = 2','value = 3'):
            workspace.references.clear()
            edit={'source_id':handle,'old':'value = 1','new':replacement}
            result=workspace.propose_handle_edits([edit],{handle:reference})
            sequence=repository.begin(job,'tool','propose_patch',{'edits':[edit]})
            repository.capture(job,sequence,result)
        assert repository.read(record['id'],'tenant-a')['patch_count']==2
        sequence=repository.begin(job,'tool','propose_patch',{'fixture_third_candidate':True})
        with pytest.raises(ValueError,match='Applied patch budget exhausted'):
            repository.capture(job,sequence,{'patch':'Forbidden third candidate'})
        assert repository.read(record['id'],'tenant-a')['patch_count']==2
    finally:workspace.close()


class FixtureChecks(Workspace):
    """These checks are deliberately not evidence of real model performance."""
    target='value = 3\n'

    def checks(self,timeout=120):
        passed=self.root.joinpath('source/value.py').read_text()==self.target
        return {'passed':passed,'environment_error':False,'returncode':0 if passed else 1,
                'stdout':'Isolated fixture comparison','stderr':'','verification_complete':True,'tests_run':1}


def context_for(observations):
    sources=[observation['result'] for observation in observations if isinstance(observation.get('result'),dict) and observation['result'].get('reference')]
    bindings={'S'+source['reference']['excerpt_id'][:12]:source['reference'] for source in sources}
    return {'allowed_actions':['propose_patch','final_result'],'reference_bindings':bindings,
            'source_catalog':sources,'selection':{'observations':observations}}


def response_for(action):
    return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(action)}}]}


def test_v5_first_patch_checked_before_revision_and_source_survives(repository):
    class Provider:
        calls=0

        def prepare(self,case,configuration,observations,budgets):
            assert configuration=='loop-v5'
            context=context_for(observations)
            assert context['reference_bindings']
            if self.calls==1:
                checks=[observation['result'] for observation in observations if observation['action']=='run_checks']
                assert len(checks)==1 and checks[0]['passed'] is False
                assert budgets['patches_remaining']==1 and budgets['checks_remaining']==1
            self.handle=next(iter(context['reference_bindings']))
            return {'fixture_only':True},context

        def __call__(self,request,seconds):
            self.calls+=1
            return response_for({'action':'propose_patch','edits':[{'source_id':self.handle,'old':'value = 1','new':'value = '+str(self.calls+1)}]})

    provider=Provider()
    record=repository.enqueue('tenant-a','feedback','fixture','loop-v5')
    result=InvestigationWorker(repository,provider,FixtureChecks).run_once()
    assert result['id']==record['id'] and result['integrity']['verified']
    assert result['outcome']=='verified_repair'
    assert provider.calls==2 and result['model_calls']==2 and result['patch_count']==2 and result['check_count']==2
    assert result['steps'][0]['name']=='initial_source'
    assert result['steps'][0]['state']=='captured'


def test_v5_recovery_consumes_captured_dispatch_and_restores_handles_without_redispatch(repository):
    record=repository.enqueue('tenant-a','captured-recovery','fixture','loop-v5')
    job=repository.claim('interrupted-worker')
    workspace=Workspace(repository.registry,repository.registry.get('fixture'))
    try:source=workspace.read_original('source/value.py')
    finally:workspace.close()
    sequence=repository.begin(job,'tool','initial_source',{'origin':'isolated fixture'})
    repository.capture(job,sequence,source)
    context=context_for([{'action':'initial_source','result':source}])
    sequence=repository.begin(job,'context','selection',{'configuration':'loop-v5'})
    repository.capture(job,sequence,context)
    sequence=repository.begin(job,'model','dispatch',{'fixture_captured_request':True})
    handle=next(iter(context['reference_bindings']))
    repository.capture(job,sequence,response_for({'action':'propose_patch','edits':[{'source_id':handle,'old':'value = 1','new':'value = 3'}]}))
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_investigations SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(record['id'],))

    class NoRedispatch:
        def __call__(self,*args):raise AssertionError('Captured dispatch must not run again')
        def prepare(self,*args):raise AssertionError('Captured context must retain source authority')

    result=InvestigationWorker(repository,NoRedispatch(),FixtureChecks).run_once()
    assert result['id']==record['id'] and result['outcome']=='verified_repair'
    assert result['model_calls']==1 and result['patch_count']==1 and result['check_count']==1
    assert result['claims']==2 and result['integrity']['verified']
    proposals=[step for step in result['steps'] if step['name']=='propose_patch']
    assert len(proposals)==1 and proposals[0]['result']['body']['reference_bindings']==context['reference_bindings']
