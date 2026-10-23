from copy import deepcopy
import pytest
from scripts.rebind_coding_candidate021 import rebind
from kairos_api.investigations.registry import tree_hash
from tests.test_verify_coding_candidate021 import fixture


def inputs(tmp_path):
    row, _, _ = fixture(); source = tmp_path/'source'; (source/'moto').mkdir(parents=True)
    (source/'moto/value.py').write_text('value = 0\n')
    receipt = {'repository':row['repository'], 'revision':row['source_commit'], 'source_digest':tree_hash(source)}
    return row, source, receipt


def test_rebinding_preserves_semantics_and_original(tmp_path):
    row, source, receipt = inputs(tmp_path); original = deepcopy(row)
    rebound, report = rebind(row, source, receipt)
    assert row == original
    assert rebound['source_digest'] == receipt['source_digest']
    assert rebound['input']['issue'] == row['input']['issue']
    before = row['assistant_target']['edits'][0]; after = rebound['assistant_target']['edits'][0]
    assert {k:v for k,v in before.items() if k!='source_id'} == {k:v for k,v in after.items() if k!='source_id'}
    assert after['source_id'] == rebound['input']['original_source'][0]['source_id']
    assert report['training_ready'] is False


@pytest.mark.parametrize('failure', ['revision','digest','excerpt','path','unknown_handle'])
def test_invalid_provenance_cannot_be_rebound(tmp_path, failure):
    row, source, receipt = inputs(tmp_path)
    if failure == 'revision': receipt['revision'] = '0'*40
    elif failure == 'digest': receipt['source_digest'] = '0'*64
    elif failure == 'excerpt': row['input']['original_source'][0]['numbered_original_source'] = '1: value = 9\n'
    elif failure == 'path': row['input']['original_source'][0]['path'] = 'moto/../secret.py'
    elif failure == 'unknown_handle': row['assistant_target']['edits'][0]['source_id'] = 'S000000000000'
    with pytest.raises(ValueError): rebind(row, source, receipt)


def test_pydantic_has_separate_source_authority(tmp_path):
    row, source, receipt = inputs(tmp_path)
    (source/'moto').rename(source/'pydantic')
    row['repository'] = receipt['repository'] = 'pydantic/pydantic'
    row['input']['original_source'][0]['path'] = 'pydantic/value.py'
    receipt['source_digest'] = tree_hash(source)
    rebound, _ = rebind(row, source, receipt)
    assert rebound['input']['original_source'][0]['path'] == 'pydantic/value.py'
    row['input']['original_source'][0]['path'] = 'moto/value.py'
    with pytest.raises(ValueError, match='outside approved'):
        rebind(row, source, receipt)
