"""Coalescing changes target representation, never source authority or semantics."""
import difflib
from pathlib import Path
import pytest
from scripts.coding_actions014 import convert_action
from test_coding_context014 import make_workspace


def fixture(tmp_path):
    before='class Target:\n'+''.join('    value_'+str(i)+' = '+str(i)+'\n' for i in range(12))
    after=before
    for i in [1,4,7,10]:after=after.replace('value_'+str(i)+' = '+str(i)+'\n','value_'+str(i)+' = 99\n')
    workspace=make_workspace(tmp_path,before,'Target values are wrong')
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/package/value.py',tofile='b/package/value.py'))
    return workspace,before,after,patch


def test_four_hunks_merge_inside_one_previously_read_region(tmp_path):
    workspace,before,after,patch=fixture(tmp_path)
    try:
        region=workspace.read_original('package/value.py')
        with pytest.raises(ValueError):convert_action(workspace,patch,[region],anchor_policy='captured-neighbor-v2')
        action,_=convert_action(workspace,patch,[region],anchor_policy='captured-neighbor-coalesced-v3')
        assert len(action['edits'])==1
        assert workspace.root.joinpath('package/value.py').read_text()==after
        assert (workspace.registry.directory(workspace.case)/'source/package/value.py').read_text()==before
    finally:workspace.close()


def test_separate_source_handles_remain_separate_edits(tmp_path):
    workspace,before,after,patch=fixture(tmp_path)
    try:
        regions=[workspace.read_original('package/value.py',1,7),workspace.read_original('package/value.py',8,13)]
        action,_=convert_action(workspace,patch,regions,anchor_policy='captured-neighbor-coalesced-v3')
        assert len(action['edits'])==2
        assert {e['source_id'] for e in action['edits']}.__len__()==2
        assert workspace.root.joinpath('package/value.py').read_text()==after
    finally:workspace.close()


def test_coalescing_never_fills_an_unread_gap(tmp_path):
    workspace,before,after,patch=fixture(tmp_path)
    try:
        regions=[workspace.read_original('package/value.py',1,4),workspace.read_original('package/value.py',8,13)]
        with pytest.raises(ValueError,match='outside issue-only selected context'):
            convert_action(workspace,patch,regions,anchor_policy='captured-neighbor-coalesced-v3')
    finally:workspace.close()
