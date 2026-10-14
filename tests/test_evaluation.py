import os
import math
import json
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


@pytest.mark.parametrize("changes", [
    {"alpha": 0}, {"alpha": 1}, {"alpha": float("nan")}, {"alpha": True},
    {"noninferiority_margin": -0.1}, {"noninferiority_margin": float("inf")},
    {"minimum_independent_tasks": 0}, {"minimum_independent_tasks": 1.5},
    {"minimum_independent_tasks": True}, {"optional_stopping": True},
])
def test_invalid_release_plan_rejected(changes):
    with pytest.raises(ValueError):
        paired_gate(rows(), HARD, {**PLAN, **changes})


def test_empty_plan_and_task_identity_rejected():
    with pytest.raises(ValueError):
        paired_gate(rows(), HARD, {})
    with pytest.raises(ValueError):
        paired_gate([{"task_id": "", "baseline_passed": True, "candidate_passed": True}], HARD)


@pytest.mark.parametrize("scenario_id,raw", [
    ("late-order-standard", '{"disposition":"zero","disposition":"refund","reason":"x","evidence_ids":["policy.base","order.receipt"]}'),
    ("late-order-standard", '{"disposition":"refund","reason":NaN,"evidence_ids":["policy.base"]}'),
    ("late-order-standard", '{"disposition":"refund","reason":Infinity,"evidence_ids":["policy.base"]}'),
    ("late-order-standard", json.dumps({"disposition":"refund","reason":" " * 2000 + "x","evidence_ids":["policy.base"]})),
    ("insufficient-evidence", '{"disposition":"abstain","reason":"Missing","evidence_ids":["order.receipt"]}'),
    ("late-order-exception", '{"disposition":"zero","reason":"Exception","evidence_ids":["order.receipt"]}'),
])
def test_evaluation_and_durable_job_reject_same_raw_contract(scenario_id,raw):
    from kairos_api.evaluation import grade
    from kairos_api.model_runtime import classify_and_grade
    from kairos_api.scenarios import get_scenario, assemble_context
    task = get_scenario(scenario_id)
    blocks = assemble_context(task, "preserve")
    evaluation_grade = grade(task, raw, blocks)
    durable_grade = classify_and_grade(scenario_id, blocks, {"raw_response": raw})
    assert not evaluation_grade["schema_valid"]
    assert not evaluation_grade["passed"]
    assert durable_grade["parse_error"]


def test_duplicate_key_model_observation_is_hard_failure(monkeypatch):
    raw = '{"disposition":"zero","disposition":"refund","reason":"x","evidence_ids":["policy.base","order.receipt"]}'
    monkeypatch.setattr('kairos_api.evaluation.call_model', lambda request: {"raw_response": raw})
    report = evaluate('model', 'development')
    assert report['candidate_passes'] == 0
    assert report['gate']['verdict'] == 'fail'
    assert next(check for check in report['hard_checks'] if check['name'] == 'candidate_strict_schema')['passed'] is False


def test_source_dependencies_and_mixed_model_revisions_block(monkeypatch):
 from kairos_api.evaluation import grade,reference
 import json
 counter=[0]
 def response(request):
  counter[0]+=1
  # Valid transport metadata with a changing revision; semantic failures remain explicit.
  return {"raw_response":json.dumps({"disposition":"zero","reason":"test","evidence_ids":["policy.base"]}),"model":"fixture","model_revision":str(counter[0]%2)}
 monkeypatch.setattr('kairos_api.evaluation.call_model',response)
 report=evaluate('model','development')
 assert set(report['source_digests'])=={'evaluation.py','model_runtime.py','scenarios.py','grading.py'}
 assert next(x for x in report['hard_checks'] if x['name']=='one_explicit_model_revision')['passed'] is False
 assert report['gate']['verdict']=='fail'
