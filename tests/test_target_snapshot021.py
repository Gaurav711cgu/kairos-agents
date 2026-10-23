import difflib
import pytest
from test_edits_v5 import workspace
from kairos_api.investigations.registry import tree_hash
from scripts.coding_target_completeness021 import audit_row, audit_workspace


def prepared(workspace):
    source = workspace.registry.directory(workspace.case)/'source/source/value.py'
    before = '# base header\n\nclass Value:\n    value = 1\n    other = 2\n\n# tail\n# tail2\n'
    source.write_text('# unchanged prefix\n'+before)
    workspace.reset(); workspace.case.update(repository='example/repo', revision='a'*40)
    captured = workspace.read_original('source/value.py', 1, 9)
    handle = 'S'+captured['reference']['excerpt_id'][:12]
    row = {'instance_id':'example-1','repository':'example/repo','source_commit':'a'*40,
           'source_digest':tree_hash(source.parents[1]),'input':{'original_source':[
               {'path':'source/value.py','start_line':1,'end_line':9,'source_id':handle,
                'numbered_original_source':captured['text']}]},
           'assistant_target':{'action':'propose_patch','edits':[
               {'source_id':handle,'start_line':5,'end_line':5,'new':'    value = 7\n'}]}}
    patch = ''.join(difflib.unified_diff(before.splitlines(True),before.replace('value = 1','value = 7').splitlines(True),fromfile='a/source/value.py',tofile='b/source/value.py',n=1))
    return row, patch


def test_shifted_reference_hunk_uses_real_snapshot_without_weakening_sparse_audit(workspace):
    row, patch = prepared(workspace)
    with pytest.raises(ValueError, match='Conflicting'): audit_row(row, patch)
    result = audit_workspace(row, patch, workspace)
    assert result['complete_reference_equivalence'] is True
    assert result['independent_repair_reproduced'] is False


def test_wrong_target_is_not_reference_equivalent(workspace):
    row, patch = prepared(workspace)
    row['assistant_target']['edits'][0]['new'] = '    value = 8\n'
    assert audit_workspace(row, patch, workspace)['complete_reference_equivalence'] is False


def test_missing_behavioral_edit_is_not_reference_equivalent(workspace):
    row, patch = prepared(workspace)
    original = (workspace.registry.directory(workspace.case)/'source/source/value.py').read_text().splitlines(True)[1:]
    changed = ''.join(original).replace('value = 1', 'value = 7').replace('other = 2', 'other = 4')
    patch = ''.join(difflib.unified_diff(original, changed.splitlines(True), fromfile='a/source/value.py', tofile='b/source/value.py', n=1))
    assert audit_workspace(row, patch, workspace)['complete_reference_equivalence'] is False


@pytest.mark.parametrize('failure',['identity','digest','excerpt','handle'])
def test_stale_snapshot_authority_is_rejected(workspace, failure):
    row, patch = prepared(workspace)
    if failure=='identity': row['source_commit']='b'*40
    elif failure=='digest': row['source_digest']='0'*64
    elif failure=='excerpt': row['input']['original_source'][0]['numbered_original_source']='wrong'
    elif failure=='handle': row['input']['original_source'][0]['source_id']='S000000000000'
    with pytest.raises(ValueError): audit_workspace(row, patch, workspace)
