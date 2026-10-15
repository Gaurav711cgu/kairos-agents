"""Versioned longer budgets reuse source authority, never promise repair quality."""
from copy import deepcopy
from contextlib import contextmanager
from types import SimpleNamespace
import pytest

from kairos_api.investigations.contracts import CONFIGURATIONS, execution_timeouts, generation_for
from kairos_api.investigations.routes import CreateInvestigation, ForkInvestigation
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.investigations.model import LocalInvestigator
from kairos_api.investigations.sandbox import Workspace
from test_investigations import registry
from test_context_v5 import MemoryRepository, tokenizer, excerpt, CASE, response
from test_v5_postgres import context_for


def job(configuration='loop-v8'):
    return {'id':'fixture','tenant_id':'tenant','configuration':configuration,
            'config_snapshot':{'budgets':dict(CONFIGURATIONS[configuration]),
                               'generation':generation_for(configuration)}}


class IndependentFixtureChecks(Workspace):
    """A deterministic software fixture; not real model-quality evidence."""
    target = 'value = 5\n'
    def checks(self, timeout=120):
        passed=(self.root/'source/value.py').read_text()==self.target
        return {'passed':passed,'returncode':0 if passed else 1,'environment_error':False,
                'verification_complete':True,'tests_run':1,'stdout':'Fixture verdict','stderr':''}


class Provider:
    def __init__(self, values):
        self.values=iter(values);self.calls=0;self.budgets=[];self.observed_checks=[]
    def prepare(self, case, configuration, observations, budgets):
        self.budgets.append(deepcopy(budgets))
        self.observed_checks.append(sum(item['action']=='run_checks' for item in observations))
        context=context_for(observations);self.handle=next(iter(context['reference_bindings']))
        return {'fixture':True},context
    def __call__(self, request, seconds):
        self.calls+=1
        return response({'action':'propose_patch','edits':[{'source_id':self.handle,
            'start_line':1,'end_line':1,'new':f'value = {next(self.values)}\n'}]})


def run(registry, provider, configuration='loop-v8', workspace_class=IndependentFixtureChecks):
    repository=MemoryRepository(registry)
    workspace=workspace_class(registry,registry.get('fixture'))
    try:
        result=InvestigationWorker(repository,provider)._run(job(configuration),workspace)
        return result,repository
    finally:workspace.close()


def test_v8_budgets_are_new_and_historical_budgets_remain_fixed():
    assert CONFIGURATIONS['loop-v8']=={'max_calls':10,'max_patches':4,'max_checks':4,'seconds':900}
    assert CONFIGURATIONS['baseline-v8']=={'max_calls':1,'max_patches':1,'max_checks':1,'seconds':600}
    assert execution_timeouts('loop-v8')==(900,960)
    for name in CONFIGURATIONS:
        if name!='loop-v8':assert execution_timeouts(name)==(600,660)
    for version in range(1,8):
        assert CONFIGURATIONS[f'loop-v{version}']=={'max_calls':6,'max_patches':2,'max_checks':2,'seconds':600}
    assert generation_for('loop-v8')==generation_for('loop-v7')
    with pytest.raises(ValueError):execution_timeouts('loop-v900')


def test_http_types_accept_explicit_new_configuration_without_changing_default():
    for configuration in ('loop-v8','baseline-v8'):
        assert CreateInvestigation(task_id='fixture',configuration=configuration).configuration==configuration
        assert ForkInvestigation(configuration=configuration).configuration==configuration
    assert CreateInvestigation(task_id='fixture').configuration=='loop-v3'


def test_local_v8_still_uses_line_handles_complete_context_and_no_shell(tokenizer):
    request,context=LocalInvestigator().prepare(CASE,'loop-v8',[{'action':'initial_source','result':excerpt()}],
        {'calls_remaining':10,'patches_remaining':4,'checks_remaining':4})
    assert 'LineHandleEdit' in request['response_format']['json_schema']['schema']['$defs']
    assert context['allowed_actions']==['final_result','propose_patch','read_file','search']
    assert context['selection']['budgets']['calls_remaining']==10
    assert context['selection']['source_blocks'][0]['numbered_original_source']=='1: value = 1\n'
    assert request['max_tokens']==1024


def test_four_accepted_candidates_are_checked_immediately(registry):
    provider=Provider([2,3,4,5])
    result,_=run(registry,provider)
    assert result['outcome']=='verified_repair'
    assert (result['model_calls'],result['patch_count'],result['check_count'])==(4,4,4)
    assert provider.observed_checks==[0,1,2,3]
    assert [item['checks_remaining'] for item in provider.budgets]==[4,3,2,1]


def test_failed_fourth_candidate_stops_without_fifth_check_or_dispatch(registry):
    provider=Provider([2,3,4,6,5])
    result,_=run(registry,provider)
    assert result['outcome']=='failed_checks'
    assert provider.calls==4 and result['check_count']==4 and result['patch_count']==4
    assert 'verification budget' in result['summary']


def test_duplicate_candidate_uses_captured_check_without_spending_a_slot(registry):
    provider=Provider([2,2,3,4,5])
    result,_=run(registry,provider)
    assert result['outcome']=='verified_repair' and provider.calls==5
    assert result['patch_count']==result['check_count']==4
    duplicate=[item for item in result['steps'] if item['name']=='propose_patch'
               and item['result']['body'].get('duplicate_candidate')]
    assert len(duplicate)==1 and duplicate[0]['result']['body']['cached_verification']['passed'] is False


@pytest.mark.parametrize('configuration,expected',[('loop-v7',6),('loop-v8',10),('baseline-v8',1)])
def test_actual_worker_call_ceiling_counts_distinct_rejections(registry,configuration,expected):
    class Invalid(Provider):
        def __call__(self,request,seconds):
            self.calls+=1
            return response({'action':'propose_patch','edits':[{'source_id':self.handle,
                'start_line':1,'end_line':100+self.calls,'new':'value = 5\n'}]})
    provider=Invalid([])
    result,_=run(registry,provider,configuration)
    assert provider.calls==expected and result['model_calls']==expected
    assert result['patch_count']==result['check_count']==0
    assert result['outcome']=='invalid_patch'


def test_identical_rejection_still_stops_after_two_under_longer_profile(registry):
    class Repeating(Provider):
        def __call__(self,request,seconds):
            self.calls+=1
            return response({'action':'propose_patch','edits':[{'source_id':self.handle,
                'start_line':1,'end_line':999,'new':'value = 5\n'}]})
    provider=Repeating([])
    result,_=run(registry,provider)
    assert provider.calls==2 and result['patch_count']==result['check_count']==0
    assert 'Two identical rejected' in result['summary']


def test_captured_response_recovers_without_another_provider_call(registry):
    repository=MemoryRepository(registry);workspace=IndependentFixtureChecks(registry,registry.get('fixture'))
    worker=InvestigationWorker(repository,provider=object()); current=job()
    try:
        _,observations,_,_,_=worker._state(current,workspace)
        context=context_for(observations);handle=next(iter(context['reference_bindings']))
        worker._record(current,'context','selection',{},context)
        seq=repository.begin(current,'model','dispatch',{'captured_fixture':True})
        repository.capture(current,seq,response({'action':'propose_patch','edits':[
            {'source_id':handle,'start_line':1,'end_line':1,'new':'value = 5\n'}]}))
    finally:workspace.close()
    class NoDispatch:
        def prepare(self,*args):raise AssertionError('No new context/dispatch after captured response')
        def __call__(self,*args):raise AssertionError('No redispatch')
    recovered=IndependentFixtureChecks(registry,registry.get('fixture'))
    try:result=InvestigationWorker(repository,NoDispatch())._run(current,recovered)
    finally:recovered.close()
    assert result['outcome']=='verified_repair'
    assert (result['model_calls'],result['patch_count'],result['check_count'])==(1,1,1)


def test_transport_failure_remains_unknown_with_pending_intent(registry):
    class Unknown(Provider):
        def __call__(self,*args):
            self.calls+=1;raise ConnectionError('Response unavailable')
    provider=Unknown([])
    result,_=run(registry,provider)
    assert result['outcome']=='unknown_dispatch' and provider.calls==1
    assert result['steps'][-1]['state']=='pending'


@pytest.mark.parametrize('configuration,seconds,lease',[('loop-v1',600,660),('loop-v7',600,660),
    ('baseline-v8',600,660),('loop-v8',900,960)])
def test_claim_sql_uses_database_clock_and_registered_deadline(configuration,seconds,lease):
    row={'id':'fixture','configuration':configuration}
    captured=[]
    class Cursor:
        def __init__(self,value):self.value=value
        def fetchone(self):return self.value
        def fetchall(self):return []
    class Connection:
        def execute(self,query,params=None):
            if 'WHERE status=\'queued\'' in query:return Cursor(row)
            if 'RETURNING *' in query:
                captured.append((query,params));return Cursor(row)
            return Cursor(None)
    class Repository(InvestigationRepository):
        @contextmanager
        def connect(self):yield Connection()
    assert Repository.__new__(Repository).claim('owned-worker')==row
    query,params=captured[0]
    assert params==('owned-worker',lease,seconds,'fixture')
    assert 'clock_timestamp()' in query and 'coalesce(deadline_at' in query
    assert "interval '1 second'" in query
