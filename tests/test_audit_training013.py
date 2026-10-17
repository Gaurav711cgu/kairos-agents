"""New positive evidence must not erase historical failures or held-out guards."""
from pathlib import Path
from scripts.audit_training013 import audit


def test_current_audit_includes_frozen_candidates_and_original_successes():
    result=audit(Path(__file__).resolve().parents[1])
    assert result['audit']['public_records']==123
    assert result['audit']['verified_unique_tasks']==3
    assert result['audit']['verified_unique_rendered_patches']==4
    assert result['audit']['record_model_calls']==286
    assert not result['audit']['training_data_ready']
    exposed={row['instance_id'] for row in result['exposures']}
    assert {'django__django-11211','django__django-11239','django__django-11265'}<=exposed
    assert result['exposed_task_count']==91
