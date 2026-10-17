"""Candidate/environment admission is independent of model success."""
import hashlib
import pytest
from scripts.coding_data014 import canonical,patch_scope
from scripts.coding_qualify014 import selected_row


def fixture():
    row={'instance_id':'Project-MONAI__MONAI-1012','repo':'Project-MONAI/MONAI','version':'0.2','patch':'diff --git a/monai/a.py b/monai/a.py\n--- a/monai/a.py\n+++ b/monai/a.py\n@@ -1 +1 @@\n-old\n+new\n'}
    screen={'candidate_ids':[row['instance_id']],'ledger':[{'instance_id':row['instance_id'],'row_sha256':hashlib.sha256(canonical(row)).hexdigest(),'scope':patch_scope(row['patch'])}]}
    return row,screen


def test_only_exact_frozen_candidate_is_admitted():
    row,screen=fixture()
    assert selected_row([row],screen,row['instance_id'])==(row,'MONAI0.2')
    with pytest.raises(ValueError,match='frozen'):selected_row([row],screen,'other-1')
    row['version']='0.3'
    with pytest.raises(ValueError,match='differs'):selected_row([row],screen,row['instance_id'])


def test_unknown_environment_stays_pending_instead_of_using_wrong_image():
    row,screen=fixture();row['version']='9.9';screen['ledger'][0]['row_sha256']=hashlib.sha256(canonical(row)).hexdigest()
    with pytest.raises(ValueError,match='pending'):selected_row([row],screen,row['instance_id'])


def test_changed_reference_or_scope_is_rejected():
    row,screen=fixture();screen['ledger'][0]['scope']['changed_lines']=3
    with pytest.raises(ValueError,match='scope'):selected_row([row],screen,row['instance_id'])


def test_revision_cannot_replace_a_success_or_completed_behavioral_failure(tmp_path):
    import json
    from scripts.coding_qualify014 import revision_gate
    from scripts.qualify014 import sha
    folder=tmp_path/'case';previous=folder/'qualification-v1';previous.mkdir(parents=True)
    for stage in ['baseline','reference']:(previous/(stage+'.json')).write_text('{}')
    receipt={'qualified':True,'model_calls':0,'original_source_unchanged':True,'checks_sha256':{stage:sha(previous/(stage+'.json')) for stage in ['baseline','reference']},'baseline':{'execution_complete':False},'reference':{'execution_complete':False}}
    path=previous/'receipt.json';path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='environment failure'):revision_gate(folder,'v2')
    receipt['qualified']=False;path.write_text(json.dumps(receipt));revision_gate(folder,'v2')
    receipt['baseline']['execution_complete']=True;receipt['reference']['execution_complete']=True;path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='behavioral failure'):revision_gate(folder,'v2')


def test_monai03_requires_its_own_reviewed_environment():
    row,screen=fixture();row['version']='0.3'
    screen['ledger'][0]['row_sha256']=hashlib.sha256(canonical(row)).hexdigest()
    assert selected_row([row],screen,row['instance_id'])==(row,'MONAI0.3')
    # Version matching cannot silently reuse the earlier 0.2 image.
    assert selected_row([row],screen,row['instance_id'])[1]!='MONAI0.2'


def test_moto30_uses_its_own_reviewed_image_and_source_prefix():
    from scripts.coding_qualify014 import SOURCE_PREFIXES
    row, screen = fixture()
    row.update(instance_id='getmoto__moto-4792', repo='getmoto/moto', version='3.0')
    row['patch'] = row['patch'].replace('monai/a.py', 'moto/cloudfront/models.py')
    screen['candidate_ids'] = [row['instance_id']]
    screen['ledger'][0].update(instance_id=row['instance_id'], row_sha256=hashlib.sha256(canonical(row)).hexdigest(), scope=patch_scope(row['patch']))
    assert selected_row([row], screen, row['instance_id']) == (row, 'Moto3.0')
    assert SOURCE_PREFIXES['getmoto/moto'] == 'moto/'
    row['version'] = '3.1'
    screen['ledger'][0]['row_sha256'] = hashlib.sha256(canonical(row)).hexdigest()
    with pytest.raises(ValueError, match='pending'):
        selected_row([row], screen, row['instance_id'])
