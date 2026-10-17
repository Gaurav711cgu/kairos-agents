"""Qualification refuses skips, incomplete output and missing existing tests."""
import json,copy
import pytest
from scripts.coding_verifier014 import verifier,qualifies


def row():return {'FAIL_TO_PASS':['tests/test_x.py::test_regression'],'PASS_TO_PASS':['tests/test_x.py::test_existing']}


def result(passed):
    summary={'tests_run':2,'execution_complete':True,'complete':passed,'regression_failed':[] if passed else ['tests/test_x.py::test_regression'],'existing_required':1,'existing_passed':['tests/test_x.py::test_existing'],'skipped':[]}
    return {'passed':passed,'returncode':0 if passed else 1,'environment_error':False,'raw_output':{'complete':True},'stdout':'KAIROS_VERIFIER_RESULT '+json.dumps(summary)}


def test_generator_preserves_all_declared_tests_and_no_shell():
    code,scope=verifier(row());compile(code,'registered-verifier','exec')
    assert len(scope['selected'])==2 and not scope['omissions']
    assert 'subprocess' not in code and 'pytest.main' in code
    for bad in ['../test_x.py::x','/test_x.py::x','tests/../test_x.py::x','tests/not_python.txt::x']:
        value=row();value['FAIL_TO_PASS']=[bad]
        with pytest.raises(ValueError):verifier(value)


def test_complete_baseline_failure_and_reference_pass_qualify():
    assert qualifies(result(False),result(True))
    assert not qualifies(result(True),result(True))


@pytest.mark.parametrize('field,value',[('execution_complete',False),('tests_run',0),('existing_passed',[]),('skipped',['test_existing'])])
def test_incomplete_or_skipped_baseline_is_not_qualified(field,value):
    before=result(False);summary=json.loads(before['stdout'].split(' ',1)[1]);summary[field]=value;before['stdout']='KAIROS_VERIFIER_RESULT '+json.dumps(summary)
    assert not qualifies(before,result(True))


def test_raw_output_loss_is_not_qualified():
    before=result(False);before['raw_output']['complete']=False
    assert not qualifies(before,result(True))


def test_timeout_or_success_exit_cannot_be_a_baseline_regression():
    for code in [0,2,124,125,126,127,None]:
        before=result(False);before['returncode']=code
        assert not qualifies(before,result(True))
