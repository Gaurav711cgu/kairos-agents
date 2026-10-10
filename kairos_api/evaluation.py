"""Fixed-sample paired synthetic evaluation. No p-value release inference."""
from __future__ import annotations
import hashlib
import inspect
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Literal
from .scenarios import assemble_context
from .model_runtime import model_request, call_model

VERSION = 'synthetic-refund-iid-v2'
PLAN = {'method':'paired Hoeffding bound, range [-1,1], two-sided alpha 0.05', 'alpha':0.05,'noninferiority_margin':0.10,'minimum_independent_tasks':1024,'sampling':'Precommitted independent seeded procedural draws; inference applies only to this synthetic generator, never real-world safety.','optional_stopping':False,'source':'https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def task_suite(split='holdout'):
    if split not in ('development','holdout'): raise ValueError('unknown split')
    rng=random.Random(907321 if split=='development' else 7342981)
    rows=[]
    for i in range(32 if split=='development' else 1024):
        available=rng.random()>=0.15
        row={'task_id':f'{split}-{i:04d}','order_id':f'SYN-{split}-{i:04d}', 'order_total_cents':rng.randint(100,30000) if available else None,'delay_minutes':rng.randint(0,100) if available else None,'policy_exception':rng.random()<0.3,'order_evidence_available':available}
        rows.append(row)
    return rows

def expected(task):
    if not task['order_evidence_available'] or task['order_total_cents'] is None or task['delay_minutes'] is None:return 'abstain'
    if task['policy_exception'] or task['delay_minutes']<30:return 'zero'
    return 'refund'

def reference(task,policy):
    visible=dict(task)
    if policy=='compact':visible['policy_exception']=False
    disposition=expected(visible)
    return {'disposition':disposition,'reason':'Deterministic policy execution.','evidence_ids':['policy.evidence'] if disposition=='abstain' else ['policy.base','order.receipt']+(['policy.exception'] if visible['policy_exception'] else [])}

def grade(task,raw,blocks):
    try:
        value=json.loads(raw)
        valid=isinstance(value,dict) and set(value)=={'disposition','reason','evidence_ids'} and value['disposition'] in ('refund','zero','abstain') and isinstance(value['reason'],str) and 0<len(value['reason'].strip())<=2000 and isinstance(value['evidence_ids'],list) and len(value['evidence_ids'])>0 and all(isinstance(x,str) and x in {b['id'] for b in blocks if b['included']} for x in value['evidence_ids']) and len(value['evidence_ids'])==len(set(value['evidence_ids']))
        if not valid:return {'passed':False,'schema_valid':False,'policy_match':False,'error':'strict_schema'}
        policy_match=value['disposition']==expected(task)
        provenance=('policy.exception' in value['evidence_ids']) if task['policy_exception'] and task['order_evidence_available'] else ('policy.evidence' in value['evidence_ids'] if expected(task)=='abstain' else True)
        return {'passed':policy_match and provenance,'schema_valid':True,'policy_match':policy_match,'evidence_valid':provenance,'error':None if policy_match and provenance else 'policy_or_evidence'}
    except (ValueError,TypeError,KeyError):return {'passed':False,'schema_valid':False,'policy_match':False,'error':'strict_json'}

def paired_gate(rows,hard_checks,plan=None):
    p=plan or PLAN
    n=len(rows)
    if not n:raise ValueError('empty evaluation')
    if len({r['task_id'] for r in rows})!=n:raise ValueError('duplicate task identities')
    if any(type(r[k]) is not bool for r in rows for k in ('baseline_passed','candidate_passed')):raise ValueError('outcomes must be boolean')
    delta=sum(int(r['candidate_passed'])-int(r['baseline_passed']) for r in rows)/n
    radius=math.sqrt(2*math.log(2/p['alpha'])/n)
    lower,upper=max(-1,delta-radius),min(1,delta+radius)
    if not hard_checks or not all(type(x['passed']) is bool and x['passed'] for x in hard_checks):verdict='fail';reason='hard invariant blocked'
    elif n<p['minimum_independent_tasks']:verdict='inconclusive';reason='below predeclared independent task count'
    elif lower > -p['noninferiority_margin']:verdict='pass';reason='lower bound exceeds noninferiority boundary'
    elif upper < -p['noninferiority_margin']:verdict='fail';reason='upper bound below noninferiority boundary'
    else:verdict='inconclusive';reason='interval crosses noninferiority boundary'
    return {'verdict':verdict,'reason':reason,'n':n,'paired_success_delta':delta,'lower':lower,'upper':upper,'radius':radius,'plan':p}

def evaluate(mode='null-calibration',split='holdout',endpoint=None):
    if mode not in ('null-calibration','planted-regression','reference-repair','model'):raise ValueError('unknown mode')
    tasks=task_suite(split); rows=[]
    for task in tasks:
        blocks=assemble_context(task,'preserve')
        baseline=reference(task,'compact' if mode=='reference-repair' else 'preserve')
        baseline_raw=json.dumps(baseline)
        provider_error=None; request=None; response=None
        if mode=='model':
            request=model_request(blocks)
            try:
                response=call_model(request)
                candidate_raw=response['raw_response']
            except Exception as exc:provider_error=type(exc).__name__;candidate_raw=''
        else:
            candidate=reference(task,'preserve')
            if mode=='planted-regression':candidate['disposition']='refund' if expected(task)!='refund' else 'zero'
            candidate_raw=json.dumps(candidate)
        bgrade=grade(task,baseline_raw,assemble_context(task,'compact' if mode=='reference-repair' else 'preserve'))
        cgrade=grade(task,candidate_raw,blocks)
        rows.append({'task_id':task['task_id'],'input':task,'context':blocks,'baseline_raw':baseline_raw,'candidate_raw':candidate_raw,'baseline_passed':bgrade['passed'],'candidate_passed':cgrade['passed'],'baseline_grade':bgrade,'candidate_grade':cgrade,'request':request,'response':response,'provider_error':provider_error})
    hard=[{'name':'no_external_effects','passed':True,'detail':'Evaluation has no effect dispatcher.'},{'name':'all_planned_tasks_retained','passed':len(rows)==len(tasks),'detail':'Provider errors retained as failed outcomes.'},{'name':'candidate_strict_schema','passed':all(r['candidate_grade']['schema_valid'] for r in rows),'detail':'Every candidate must validate without repair or markdown stripping.'}]
    report={'id':str(uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),'mode':mode,'split':split,'suite_version':VERSION,'task_set_digest':digest(tasks),'code_digest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'grader_digest':hashlib.sha256((inspect.getsource(grade)+inspect.getsource(expected)).encode()).hexdigest(),'config_digest':digest({'mode':mode,'split':split,'plan':PLAN,'max_tokens':128}),'baseline_passes':sum(r['baseline_passed'] for r in rows),'candidate_passes':sum(r['candidate_passed'] for r in rows),'provider_failures':sum(r['provider_error'] is not None for r in rows),'hard_checks':hard,'gate':paired_gate(rows,hard),'rows':rows,'limits':['Synthetic procedural task distribution only; no production/adoption claim.','Calibration executions are deterministic and are not model quality evidence.','Each row one predeclared paired task; no repeated-seed pseudo-replication.','Original separate build001 model probe 0/4 remains unchanged.','Model mode is direct evaluation, separate from durable job execution.']}
    report['report_digest']=digest(report)
    return report

class EvaluationRepository:
    def __init__(self,database_url):self.database_url=database_url
    def connect(self):return psycopg.connect(self.database_url,row_factory=dict_row,connect_timeout=5)
    def initialize(self):
        with self.connect() as c:c.execute(Path(__file__).with_name('schema_evaluation.sql').read_text())
    def save(self,tenant,report,publish=False):
        with self.connect() as c:c.execute('INSERT INTO kairos_evaluations(id,tenant_id,published,report) VALUES (%s,%s,%s,%s)',(report['id'],tenant,publish,Jsonb(report)))
        return report
    def list(self,tenant=None):
        with self.connect() as c:
            rows=c.execute('SELECT report FROM kairos_evaluations WHERE '+('published=true' if tenant is None else 'tenant_id=%s')+' ORDER BY created_at DESC LIMIT 100',() if tenant is None else (tenant,)).fetchall()
        return [{k:v for k,v in r['report'].items() if k!='rows'} for r in rows]
    def get(self,id,tenant=None):
        try:
            with self.connect() as c:row=c.execute('SELECT report FROM kairos_evaluations WHERE id=%s AND '+('published=true' if tenant is None else 'tenant_id=%s'),(id,) if tenant is None else (id,tenant)).fetchone()
        except psycopg.errors.InvalidTextRepresentation:raise HTTPException(404,'Report unavailable')
        if not row:raise HTTPException(404,'Report unavailable')
        report=row['report'];claimed=report.pop('report_digest',None)
        if digest(report)!=claimed:raise HTTPException(409,'Report integrity mismatch')
        report['report_digest']=claimed
        return report

class CalibrationCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode:Literal['null-calibration','planted-regression','reference-repair']='null-calibration'

def create_evaluation_router(tenant_dependency,repository=None,repository_dependency=None):
    router=APIRouter()
    repo_dep=repository_dependency or (lambda: repository)
    @router.get('/api/public/evaluations')
    def public_list(repo=Depends(repo_dep)):return {'reports':repo.list()}
    @router.get('/api/public/evaluations/{id}')
    def public_detail(id:str,repo=Depends(repo_dep)):return repo.get(id)
    @router.get('/api/evaluations')
    def private_list(tenant=Depends(tenant_dependency),repo=Depends(repo_dep)):return {'reports':repo.list(tenant)}
    @router.get('/api/evaluations/{id}')
    def private_detail(id:str,tenant=Depends(tenant_dependency),repo=Depends(repo_dep)):return repo.get(id,tenant)
    @router.post('/api/evaluations',status_code=201)
    def calibration(command:CalibrationCommand,tenant=Depends(tenant_dependency),repo=Depends(repo_dep)):return repo.save(tenant,evaluate(command.mode))
    return router
