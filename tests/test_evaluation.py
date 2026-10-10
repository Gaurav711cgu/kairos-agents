import os
import math
from uuid import uuid4
import pytest
from fastapi import HTTPException
from kairos_api.evaluation import paired_gate,evaluate,task_suite,digest,EvaluationRepository,PLAN

def rows(n=1024,baseline=True,candidate=True):return [{'task_id':str(i),'baseline_passed':baseline,'candidate_passed':candidate} for i in range(n)]
HARD=[{'name':'boundary','passed':True}]
def test_null_is_not_bootstrap_zero_width():
 result=paired_gate(rows(),HARD)
 assert result['verdict']=='pass'
 assert result['lower']<0<result['upper']
 assert result['radius']==pytest.approx(math.sqrt(2*math.log(40)/1024))
def test_small_null_is_inconclusive():assert paired_gate(rows(32),HARD)['verdict']=='inconclusive'
def test_planted_harm_blocks():assert paired_gate(rows(candidate=False),HARD)['verdict']=='fail'
def test_hard_failure_blocks_even_improvement():assert paired_gate(rows(baseline=False),[{'passed':False}])['verdict']=='fail'
def test_no_missing_or_duplicate_outcomes():
 with pytest.raises(ValueError):paired_gate([rows(1)[0]]*2,HARD)
 with pytest.raises(ValueError):paired_gate([{'task_id':'x','baseline_passed':1,'candidate_passed':True}],HARD)
def test_suite_alignment_and_separate_splits():
 assert digest(task_suite())==digest(task_suite())
 assert len(task_suite())==1024
 assert {x['task_id'] for x in task_suite()}.isdisjoint(x['task_id'] for x in task_suite('development'))
def test_calibration_reports_retain_every_pair():
 null=evaluate();planted=evaluate('planted-regression');repair=evaluate('reference-repair')
 assert null['gate']['verdict']=='pass' and null['candidate_passes']==1024
 assert planted['gate']['verdict']=='fail' and planted['candidate_passes']==0
 assert repair['candidate_passes']>repair['baseline_passes']
 assert len(null['rows'])==1024 and null['task_set_digest']==planted['task_set_digest']
def test_provider_failures_retained(monkeypatch):
 def bad(*a,**k):raise TimeoutError('injected')
 monkeypatch.setattr('kairos_api.evaluation.call_model',bad)
 report=evaluate('model','development')
 assert report['provider_failures']==32 and report['candidate_passes']==0
 assert len(report['rows'])==32 and report['gate']['verdict']=='fail'
@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='actual PostgreSQL required')
def test_report_durable_scope_and_tamper():
 repo=EvaluationRepository(os.environ['TEST_DATABASE_URL']);repo.initialize()
 tenant='eval-test-'+str(uuid4());report=evaluate('null-calibration','development');repo.save(tenant,report)
 assert repo.get(report['id'],tenant)['report_digest']==report['report_digest']
 for other in (None,tenant+'-other'):
  with pytest.raises(HTTPException) as e:repo.get(report['id'],other)
  assert e.value.status_code==404
 with repo.connect() as c:c.execute("UPDATE kairos_evaluations SET report=jsonb_set(report,'{candidate_passes}','999') WHERE id=%s",(report['id'],))
 with pytest.raises(HTTPException) as e:repo.get(report['id'],tenant)
 assert e.value.status_code==409
 with repo.connect() as c:c.execute('DELETE FROM kairos_evaluations WHERE tenant_id=%s',(tenant,))
