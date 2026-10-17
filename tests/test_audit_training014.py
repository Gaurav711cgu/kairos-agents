"""A larger positive evidence count must not contaminate future training."""
from pathlib import Path
import pytest
from scripts.audit_training014 import audit, matched_verified_patches
from kairos_api.model_runtime import digest


def test_only_passing_patch_is_counted():
    def step(name, body):return {'name':name,'result':{'body':body}}
    record={'outcome':'verified_repair','steps':[
        step('propose_patch',{'patch':'bad'}),step('run_checks',{'passed':False,'patch_digest':digest('bad')}),
        step('propose_patch',{'patch':'good'}),step('run_checks',{'passed':True,'patch_digest':digest('good')})]}
    import hashlib
    assert matched_verified_patches(record)=={hashlib.sha256(b'good').hexdigest()}
    record['steps'].pop()
    with pytest.raises(ValueError,match='bound'):matched_verified_patches(record)


def test_failed_record_never_yields_training_success():
    record={'outcome':'failed_checks','steps':[{'name':'propose_patch','result':{'body':{'patch':'x'}}}]}
    assert matched_verified_patches(record)==set()


def test_full_current_audit_keeps_every_evaluation_case_reserved():
    result=audit(Path(__file__).resolve().parents[1])
    assert result['audit']['new_comparison_records']==57
    assert result['audit']['public_records']==180
    assert result['audit']['new_verified_tasks']>0
    assert result['audit']['new_training_eligible_tasks']==0
    assert not result['audit']['training_data_ready']
    assert len(result['reserved014_ids'])==24
    assert set(result['reserved014_ids']) <= {r['instance_id'] for r in result['exposures']}
    assert result['prior_audit']['verified_unique_tasks']==3
