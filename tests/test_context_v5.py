"""Protocol-v5 regressions preserve actionable source across tool decisions."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from kairos_api.investigations.context_v5 import compact_issue, initial_sources, source_block, source_handle
from kairos_api.investigations.model import LocalInvestigator
from kairos_api.investigations.sandbox import Workspace
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.model_runtime import digest
from test_investigations import registry


def excerpt(text='value = 1\n',path='source/value.py',start=1):
    reference={'path':path,'source_digest':hashlib.sha256(text.encode()).hexdigest(),
               'start_line':start,'end_line':start+len(text.splitlines())-1}
    reference['excerpt_id']=digest({**reference,'text':text})
    return {'reference':reference,'text':''.join(f'{n}: {line}' for n,line in enumerate(text.splitlines(True),start)),
            'source':'original_snapshot'}


@pytest.fixture
def tokenizer(monkeypatch):
    real=httpx.Client
    def install(constant=None):
        def handle(request):
            body=json.loads(request.content)
            if request.url.path=='/apply-template':
                return httpx.Response(200,json={'prompt':json.dumps(body['messages'],ensure_ascii=False)})
            assert request.url.path=='/tokenize'
            count=constant if constant is not None else len(body['content'])//4
            return httpx.Response(200,json={'tokens':[1]*count})
        monkeypatch.setattr(httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    install()
    return install


CASE={'id':'fixture','title':'Fix value','issue':'Fix value behavior.','revision':'frozen','approved_prefix':'source/'}
BUDGET={'calls_remaining':6,'patches_remaining':2,'checks_remaining':2}


def prepare(observations,configuration='loop-v5',budgets=None):
    return LocalInvestigator().prepare(CASE,configuration,observations,budgets or BUDGET)


def test_initial_source_survives_six_search_events(tokenizer):
    original=excerpt()
    observations=[{'action':'initial_source','result':original}]+[
        {'action':'search','result':{'matches':[]}} for _ in range(6)]
    request,context=prepare(observations)
    assert context['selection']['source_blocks'][0]['original_source']=='value = 1\n'
    assert context['reference_bindings']=={source_handle(original['reference']):original['reference']}
    assert 'propose_patch' in context['allowed_actions']
    assert set(context['allowed_actions'])=={'propose_patch','final_result'}
    assert request['temperature']==0 and request['presence_penalty']==0 and request['max_tokens']==1024


@pytest.mark.parametrize('configuration,budgets',[
    ('baseline-v5',BUDGET),('loop-v5',{**BUDGET,'calls_remaining':1}),
])
def test_baseline_and_last_call_offer_a_draft_or_abstention(tokenizer,configuration,budgets):
    request,context=prepare([{'action':'initial_source','result':excerpt()}],configuration,budgets)
    assert set(request['response_format']['json_schema']['schema']['discriminator']['mapping'])=={'propose_patch','final_result'}
    assert set(context['allowed_actions'])=={'propose_patch','final_result'}


def test_feedback_retains_candidate_verdict_and_rejected_edit(tokenizer):
    patch='--- a/source/value.py\n+++ b/source/value.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    observations=[{'action':'initial_source','result':excerpt()},
                  {'action':'propose_patch','result':{'patch':patch,'edits':[{'source_id':'S123456789abc','old':'1','new':'2'}]}},
                  {'action':'run_checks','result':{'passed':False,'returncode':1,'patch_digest':digest(patch),'stdout':'assert value == 3\n'}},
                  {'action':'propose_patch','result':{'error':'Old text must match exactly once'}}]
    _,context=prepare(observations)
    value=context['selection']
    assert value['latest_verification']['passed'] is False
    assert value['latest_verification']['patch_digest']==value['current_candidate']['patch_digest']
    assert value['latest_error']['error']=='Old text must match exactly once'
    assert value['source_blocks'] and value['phase']=='revise'


def test_context_pruning_never_discards_every_actionable_source(tokenizer):
    a=excerpt('left = "'+'a'*6000+'"\n')
    b=excerpt('right = "'+'b'*6000+'"\n',path='source/other.py')
    _,context=prepare([{'action':'initial_source','result':a},{'action':'initial_source','result':b}])
    assert len(context['selection']['source_blocks'])==1
    assert context['selection']['source_blocks'][0]['source_id']==source_handle(a['reference'])
    assert any('source_id' in item for item in context['omissions'])
    assert context['rendered_input_tokens']+context['output_tokens']+32<=4096


def test_context_that_cannot_fit_fails_instead_of_dropping_last_source(tokenizer):
    tokenizer(constant=5000)
    with pytest.raises(ValueError,match='Actionable source'):
        prepare([{'action':'initial_source','result':excerpt()}])


def test_missing_source_and_compact_handle_collisions_are_rejected(tokenizer):
    with pytest.raises(ValueError,match='actionable'):
        prepare([{'action':'search','result':{'matches':[]}}])
    a=excerpt();b=copy.deepcopy(a)
    b['reference']['excerpt_id']=a['reference']['excerpt_id'][:12]+'f'*52
    with pytest.raises(ValueError,match='collision'):
        prepare([{'action':'initial_source','result':a},{'action':'read_file','result':b}])


def test_compact_issue_keeps_complete_lines_and_records_exact_omission():
    issue='Issue title\n\n'+('Long complete detail line.\n'*200)
    compact,omissions=compact_issue(issue,100)
    assert issue.startswith(compact) and compact.endswith('\n')
    assert omissions[0]['start_character']==len(compact)
    assert omissions[0]['end_character']==len(issue)
    assert compact_issue('x'*3000,100)[0]==''


def test_source_block_preserves_indentation_colons_and_line_separators():
    source=excerpt('def value():\r\n    return "a: b"\r\n')
    assert source_block(source)['original_source']=='def value():\r\n    return "a: b"\r\n'


def test_generation_snapshot_cannot_silently_drift(tokenizer):
    from kairos_api.investigations.contracts import generation_for
    observations=[{'action':'initial_source','result':excerpt()}]
    generation=generation_for('loop-v5')
    request,_=LocalInvestigator().prepare(CASE,'loop-v5',observations,BUDGET,generation)
    assert all(request[key]==value for key,value in generation.items())
    generation['temperature']=0.7
    with pytest.raises(ValueError,match='Captured generation configuration'):
        LocalInvestigator().prepare(CASE,'loop-v5',observations,BUDGET,generation)


def test_issue_symbol_localizer_reads_only_original_source(tmp_path,monkeypatch):
    root=tmp_path/'source';(root/'package').mkdir(parents=True)
    (root/'package/entry.py').write_text('unrelated = 1\n')
    (root/'package/engine.py').write_text('class Engine:\n    def render_to_string(self):\n        return "original"\n')
    case={'issue':'Engine.render_to_string() should honor the setting.','approved_prefix':'package/',
          'entry_files':['package/entry.py']}
    workspace=Workspace.__new__(Workspace)
    workspace.case=case;workspace.references={}
    workspace.registry=SimpleNamespace(directory=lambda _:tmp_path)
    original=Path.read_text
    def guarded(path,*args,**kwargs):
        assert path.is_relative_to(root)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',guarded)
    results=initial_sources(workspace)
    assert results[0]['reference']['path']=='package/engine.py'
    assert results[0]['reference']['start_line']==2 and results[0]['reference']['end_line']==3
    assert 'public issue identifier' in results[0]['selection_reason']


def test_issue_call_identifier_and_argument_prioritize_registered_source(tmp_path):
    root=tmp_path/'source';(root/'package').mkdir(parents=True)
    (root/'package/entry.py').write_text('def prepare_method(method):\n    return to_native_string(method)\n\ndef prepare_body(data):\n    return to_native_string(data)\n')
    (root/'package/api.py').write_text('def put(value):\n    return value\n')
    workspace=Workspace.__new__(Workspace);workspace.references={}
    workspace.case={'issue':'Binary payload fails in to_native_string. package.put(data=b"payload")','approved_prefix':'package/','entry_files':['package/entry.py']}
    workspace.registry=SimpleNamespace(directory=lambda _:tmp_path)
    results=initial_sources(workspace)
    assert results[0]['reference']['path']=='package/entry.py'
    assert 'def prepare_body' in results[0]['text']


class MemoryRepository:
    """Exercise ordering and recovery without pretending to test PostgreSQL."""
    def __init__(self,registry):
        self.registry=registry
        self.record={'id':'fixture','tenant_id':'tenant','integrity':{'verified':True},'steps':[],
                     'model_calls':0,'check_count':0,'patch_count':0}
    def read(self,*args): return copy.deepcopy(self.record)
    def begin(self,job,kind,name,request):
        seq=len(self.record['steps'])+1
        self.record['steps'].append({'seq':seq,'kind':kind,'name':name,'state':'pending',
                                     'request':{'body':copy.deepcopy(request)},'result':None})
        if kind=='model':self.record['model_calls']+=1
        if name=='run_checks':self.record['check_count']+=1
        return seq
    def capture(self,job,seq,result):
        step=self.record['steps'][seq-1];step['state']='captured';step['result']={'body':copy.deepcopy(result)}
        if step['name']=='propose_patch' and 'patch' in result:self.record['patch_count']+=1
    def remaining(self,job):return 600
    def finish(self,job,outcome,summary):
        self.record.update(outcome=outcome,summary=summary)
        return self.read()


class PassingWorkspace(Workspace):
    def checks(self,timeout=120):
        return {'passed':(self.root/'source/value.py').read_text()=='value = 2\n',
                'returncode':0,'environment_error':False}


def job():
    return {'id':'fixture','tenant_id':'tenant','configuration':'loop-v5',
            'config_snapshot':{'budgets':{'max_calls':6,'max_patches':2,'max_checks':2}}}


def response(action):
    return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(action)}}]}


def test_worker_first_search_does_not_erase_code_or_disable_patch(registry,tokenizer):
    repo=MemoryRepository(registry)
    class Provider(LocalInvestigator):
        calls=0
        def __call__(self,request,seconds):
            self.calls+=1
            if self.calls==1:return response({'action':'search','query':'value'})
            value=json.loads(request['messages'][1]['content'])
            assert value['source_blocks'][0]['original_source']=='value = 1\n'
            return response({'action':'propose_patch','edits':[{'source_id':value['source_blocks'][0]['source_id'],'old':'value = 1','new':'value = 2'}]})
    provider=Provider();workspace=PassingWorkspace(registry,registry.get('fixture'))
    try:
        result=InvestigationWorker(repo,provider)._run(job(),workspace)
        assert result['outcome']=='verified_repair' and provider.calls==2
        assert result['model_calls']==2 and result['patch_count']==1 and result['check_count']==1
        assert result['steps'][0]['name']=='initial_source'
    finally:workspace.close()


def test_recovery_uses_captured_context_handle_without_model_redispatch(registry,tokenizer):
    repo=MemoryRepository(registry);worker=InvestigationWorker(repo)
    workspace=PassingWorkspace(registry,registry.get('fixture'))
    _,observations,_,_,_=worker._state(job(),workspace)
    request,context=LocalInvestigator().prepare(workspace.case,'loop-v5',observations,BUDGET)
    worker._record(job(),'context','selection',{},context)
    seq=repo.begin(job(),'model','dispatch',request)
    handle=next(iter(context['reference_bindings']))
    repo.capture(job(),seq,response({'action':'propose_patch','edits':[{'source_id':handle,'old':'value = 1','new':'value = 2'}]}))
    workspace.close()
    class NeverDispatch:
        def __call__(self,*args):raise AssertionError('Captured dispatch must not repeat')
    workspace=PassingWorkspace(registry,registry.get('fixture'))
    try:
        result=InvestigationWorker(repo,NeverDispatch())._run(job(),workspace)
        assert result['outcome']=='verified_repair' and result['model_calls']==1
        assert result['check_count']==1
    finally:workspace.close()


@pytest.mark.parametrize('configuration', ['baseline-v6', 'loop-v6'])
def test_reasoning_protocol_has_separate_generation_and_context_budget(tokenizer, configuration):
    from kairos_api.investigations.contracts import GENERATION, generation_for
    historical = copy.deepcopy(GENERATION)
    request, context = prepare([{'action': 'initial_source', 'result': excerpt()}], configuration)
    assert request['temperature'] == 0.6
    assert request['top_p'] == 0.95
    assert request['presence_penalty'] == 0.5
    assert request['max_tokens'] == 2048
    assert request['chat_template_kwargs'] == {'enable_thinking': True}
    assert context['rendered_input_tokens'] + context['output_tokens'] + 32 <= 8192
    assert generation_for('loop-v4') == historical
    assert generation_for('loop-v5')['max_tokens'] == 1024
    assert generation_for('loop-v5')['chat_template_kwargs'] == {'enable_thinking': False}
    assert GENERATION == historical

@pytest.mark.parametrize('configuration,context,output', [('loop-v5',4096,1024),('loop-v6',8192,2048)])
def test_runtime_attestation_binds_protocol_context_and_single_slot(tmp_path,monkeypatch,configuration,context,output):
    manifest=tmp_path/'profile.json'
    manifest.write_text(json.dumps({'files':[{'path':'models/pinned.gguf'}],'settings':{'context':context,'max_output_tokens':output,'parallel':1}}))
    monkeypatch.setenv('KAIROS_INVESTIGATION_MODEL_MANIFEST',str(manifest))
    real=httpx.Client;calls=[]
    def handler(request):
        calls.append(request.url.path)
        if request.url.path=='/v1/models':return httpx.Response(200,json={'data':[{'id':'pinned.gguf'}]})
        assert request.url.path=='/props'
        return httpx.Response(200,json={'default_generation_settings':{'n_ctx':context},'total_slots':1,'model_path':'/models/pinned.gguf'})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    attestation=LocalInvestigator().verify_profile(configuration)
    assert attestation['server_context']==context and attestation['server_slots']==1
    assert calls==['/v1/models','/props']

@pytest.mark.parametrize('mismatch',['manifest_context','manifest_output','server_context','server_slots','server_path'])
def test_incompatible_runtime_fails_before_model_dispatch(tmp_path,monkeypatch,mismatch):
    settings={'context':8192,'max_output_tokens':2048,'parallel':1}
    if mismatch=='manifest_context':settings['context']=4096
    if mismatch=='manifest_output':settings['max_output_tokens']=1024
    manifest=tmp_path/'profile.json';manifest.write_text(json.dumps({'files':[{'path':'models/pinned.gguf'}],'settings':settings}))
    monkeypatch.setenv('KAIROS_INVESTIGATION_MODEL_MANIFEST',str(manifest))
    real=httpx.Client;calls=[]
    def handler(request):
        calls.append(request.url.path)
        assert request.method=='GET', 'A mismatched runtime must not dispatch inference'
        if request.url.path=='/v1/models':return httpx.Response(200,json={'data':[{'id':'pinned.gguf'}]})
        assert request.url.path=='/props'
        return httpx.Response(200,json={'default_generation_settings':{'n_ctx':4096 if mismatch=='server_context' else 8192},'total_slots':2 if mismatch=='server_slots' else 1,'model_path':'other.gguf' if mismatch=='server_path' else 'pinned.gguf'})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(ValueError,match='runtime settings|Loaded inference'):
        LocalInvestigator().verify_profile('loop-v6')
    if mismatch.startswith('manifest_'):assert calls==[]


def test_legacy_v4_exhausted_context_returns_bounded_error(tokenizer):
    tokenizer(constant=5000)
    with pytest.raises(ValueError,match='Complete issue and required context exceed'):
        LocalInvestigator().prepare(CASE,'loop-v4',[],BUDGET)
