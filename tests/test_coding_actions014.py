"""Verified supervision uses the actual bounded edit renderer, never model guesses."""
from copy import deepcopy
import difflib
import pytest
from scripts.coding_actions014 import convert_action, normalize_action_payload
from kairos_api.investigations.contracts import ActionV7
from test_edits_v5 import workspace


def patch(workspace,new):
    original=workspace.registry.directory(workspace.case)/'source/source/value.py'
    before=original.read_text()
    return ''.join(difflib.unified_diff(before.splitlines(True),new.splitlines(True),fromfile='a/source/value.py',tofile='b/source/value.py'))


def test_conversion_replays_exact_verified_bytes_and_preserves_original(workspace):
    original=workspace.read_original('source/value.py');new='class Value:\n    value = 7\n    other = 2\n'
    action,rendered=convert_action(workspace,patch(workspace,new),[original])
    assert ActionV7.validate_python(action).action=='propose_patch'
    assert workspace.root.joinpath('source/value.py').read_text()==new
    assert workspace.read_original('source/value.py')==original
    assert rendered['construction']=='captured-source-line-handles-v7'
    assert set(action['edits'][0])=={'source_id','start_line','end_line','new'}


@pytest.mark.parametrize('new',['# inserted\nclass Value:\n    value = 1\n    other = 2\n','class Value:\n    value = 1\n    other = 2\n# inserted\n','class Value:\n    other = 2\n'])
def test_insertions_and_deletions_use_valid_inclusive_original_lines(workspace,new):
    region=workspace.read_original('source/value.py')
    action,_=convert_action(workspace,patch(workspace,new),[region])
    assert workspace.root.joinpath('source/value.py').read_text()==new
    assert all(1<=item['start_line']<=item['end_line']<=3 for item in action['edits'])


def test_missing_context_is_rejected_instead_of_expanding_from_answer(workspace):
    region=workspace.read_original('source/value.py',1,1)
    with pytest.raises(ValueError,match='issue-only selected context'):
        convert_action(workspace,patch(workspace,'class Value:\n    value = 7\n    other = 2\n'),[region])
    assert region['reference']['end_line']==1


def test_stale_reference_cannot_become_a_training_target(workspace):
    region=deepcopy(workspace.read_original('source/value.py'));region['reference']['source_digest']='0'*64
    with pytest.raises(ValueError,match='reference changed'):
        convert_action(workspace,patch(workspace,'class Value:\n    value = 7\n    other = 2\n'),[region])


def test_invalid_python_is_not_repaired_by_label_conversion(workspace):
    region=workspace.read_original('source/value.py')
    with pytest.raises(ValueError,match='syntax rejected'):
        convert_action(workspace,patch(workspace,'class Value:\n    value = (\n    other = 2\n'),[region])


def test_protected_paths_never_become_labels(workspace):
    region=workspace.read_original('source/value.py')
    text=patch(workspace,'class Value:\n    value = 7\n    other = 2\n').replace('source/value.py','../tests/test_secret.py')
    with pytest.raises(ValueError,match='Unsafe source path'):
        convert_action(workspace,text,[region])


def test_v2_insertion_uses_already_captured_following_anchor(workspace):
    region=workspace.read_original('source/value.py',2,2)
    new='class Value:\n    added = 3\n    value = 1\n    other = 2\n'
    text=patch(workspace,new)
    with pytest.raises(ValueError,match='issue-only selected context'):
        convert_action(workspace,text,[region])
    action,_=convert_action(workspace,text,[region],anchor_policy='captured-neighbor-v2')
    assert action['edits'][0]['start_line']==2
    assert action['edits'][0]['end_line']==2
    assert workspace.root.joinpath('source/value.py').read_text()==new


def test_v2_never_adds_an_uncaptured_anchor(workspace):
    region=workspace.read_original('source/value.py',1,1)
    text=patch(workspace,'class Value:\n    value = 1\n    added = 3\n    other = 2\n')
    with pytest.raises(ValueError,match='issue-only selected context'):
        convert_action(workspace,text,[region],anchor_policy='captured-neighbor-v2')


def test_normalize_action_payload_preserves_canonical():
    canonical_action = {
        'action': 'propose_patch',
        'edits': [
            {
                'source_id': 'S9686710219d2',
                'start_line': 1606,
                'end_line': 1627,
                'new': '        return True\n',
            }
        ],
    }
    normalized = normalize_action_payload(canonical_action)
    assert normalized == canonical_action


def test_normalize_action_payload_lifts_root_replace():
    raw_replace = {
        'action': 'replace',
        'source_id': 'S9686710219d2',
        'start_line': 1606,
        'end_line': 1627,
        'replacement': '        return True\n',
    }
    normalized = normalize_action_payload(raw_replace)
    assert normalized['action'] == 'propose_patch'
    assert len(normalized['edits']) == 1
    assert normalized['edits'][0] == {
        'source_id': 'S9686710219d2',
        'start_line': 1606,
        'end_line': 1627,
        'new': '        return True\n',
    }


def test_normalize_action_payload_lifts_root_insert_with_new():
    raw_insert = {
        'action': 'insert',
        'source_id': 'Sfbd65545836a',
        'start_line': 632,
        'end_line': 632,
        'new': '    pass\n',
    }
    normalized = normalize_action_payload(raw_insert)
    assert normalized['action'] == 'propose_patch'
    assert normalized['edits'][0]['source_id'] == 'Sfbd65545836a'
    assert normalized['edits'][0]['start_line'] == 632
    assert normalized['edits'][0]['end_line'] == 632
    assert normalized['edits'][0]['new'] == '    pass\n'


def test_normalize_action_payload_unpacks_nested_edit():
    raw_nested = {
        'action': 'replace',
        'source_id': 'Sab4aa9c80b95',
        'edit': {
            'start_line': 46,
            'end_line': 46,
            'new': '    return 42\n',
        },
    }
    normalized = normalize_action_payload(raw_nested)
    assert normalized['action'] == 'propose_patch'
    assert normalized['edits'][0]['source_id'] == 'Sab4aa9c80b95'
    assert normalized['edits'][0]['start_line'] == 46


def test_normalize_action_payload_rejects_invalid_bounds_or_input():
    with pytest.raises(ValueError, match='JSON object'):
        normalize_action_payload('not a dict')
    with pytest.raises(ValueError, match='Invalid line bounds'):
        normalize_action_payload({
            'action': 'replace',
            'source_id': 'Sab4aa9c80b95',
            'start_line': 100,
            'end_line': 50,
            'new': 'foo\n',
        })
    with pytest.raises(Exception):
        # Invalid source_id pattern
        normalize_action_payload({
            'action': 'replace',
            'source_id': 'invalid-handle',
            'start_line': 1,
            'end_line': 2,
            'new': 'foo\n',
        })

