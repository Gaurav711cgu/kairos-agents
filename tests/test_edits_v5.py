"""Exact source bindings reject ambiguous or unsafe model edits without execution."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from kairos_api.investigations.contracts import ActionV5, GENERATION, generation_for
from kairos_api.investigations.routes import CreateInvestigation, ForkInvestigation
from kairos_api.investigations.sandbox import Workspace


@pytest.fixture
def workspace(tmp_path):
    directory=tmp_path/'case';source=directory/'source'/'source';source.mkdir(parents=True)
    (source/'value.py').write_text('class Value:\n    value = 1\n    other = 2\n')
    registry=SimpleNamespace(verify=lambda _:None,directory=lambda _:directory)
    instance=Workspace(registry,{'approved_prefix':'source/'})
    try: yield instance
    finally: instance.close()


def binding(workspace,start=1,end=None):
    reference=workspace.read_original('source/value.py',start,end)['reference']
    handle='S'+reference['excerpt_id'][:12]
    return handle,{handle:reference}


def test_exact_fragment_preserves_assignment_indentation_and_original(workspace):
    handle,sources=binding(workspace)
    result=workspace.propose_handle_edits([{'source_id':handle,'old':'value = 1','new':'value = 3'}],sources)
    assert workspace.root.joinpath('source/value.py').read_text()=='class Value:\n    value = 3\n    other = 2\n'
    assert workspace.read_original('source/value.py')['text']=='1: class Value:\n2:     value = 1\n3:     other = 2\n'
    assert result['added']==1 and result['removed']==1
    assert result['reference_bindings']==sources
    assert result['rendering']=='Exact model-authored replacements; no indentation or semantic correction'


def test_region_reference_restores_without_expanding_its_authority(workspace):
    handle,sources=binding(workspace,2,2)
    workspace.references.clear()
    workspace.propose_handle_edits([{'source_id':handle,'old':'value = 1','new':'value = 4'}],sources)
    assert workspace.references[sources[handle]['excerpt_id']]['end_line']==2
    with pytest.raises(ValueError,match='escapes captured excerpt'):
        workspace.propose_handle_edits([{'source_id':handle,'old':'other = 2','new':'other = 4'}],sources)


def test_ambiguous_fragment_rejected_even_when_excerpt_has_one_occurrence(workspace):
    source=workspace.registry.directory(workspace.case)/'source/source/value.py'
    source.write_text('first = 1\nsecond = 1\n')
    handle,sources=binding(workspace,1,1)
    with pytest.raises(ValueError,match='exactly once'):
        workspace.propose_handle_edits([{'source_id':handle,'old':' = 1','new':' = 2'}],sources)


@pytest.mark.parametrize('alteration',['digest','range','excerpt','handle','path'])
def test_forged_or_stale_binding_rejected(workspace,alteration):
    handle,sources=binding(workspace,2,2);sources=deepcopy(sources)
    if alteration=='digest':sources[handle]['source_digest']='0'*64
    elif alteration=='range':sources[handle]['end_line']=3
    elif alteration=='excerpt':sources[handle]['excerpt_id']='0'*64
    elif alteration=='handle':handle='S'+'0'*12
    else:sources[handle]['path']='../reference.patch'
    with pytest.raises(ValueError):
        workspace.propose_handle_edits([{'source_id':handle,'old':'value = 1','new':'value = 5'}],sources)


def test_changed_original_source_rejected(workspace):
    handle,sources=binding(workspace)
    source=workspace.registry.directory(workspace.case)/'source/source/value.py'
    source.write_text('class Value:\n    value = 9\n    other = 2\n')
    with pytest.raises(ValueError,match='reference changed'):
        workspace.propose_handle_edits([{'source_id':handle,'old':'value = 1','new':'value = 5'}],sources)


def test_overlapping_and_unchanged_fragments_rejected(workspace):
    handle,sources=binding(workspace)
    with pytest.raises(ValueError,match='Overlapping'):
        workspace.propose_handle_edits([
            {'source_id':handle,'old':'value = 1','new':'value = 5'},
            {'source_id':handle,'old':'1','new':'7'},
        ],sources)
    with pytest.raises(ValueError,match='no change'):
        workspace.propose_handle_edits([{'source_id':handle,'old':'value = 1','new':'value = 1'}],sources)


def test_bad_python_is_rejected_without_automatic_code_correction(workspace):
    handle,sources=binding(workspace)
    with pytest.raises(ValueError,match='syntax rejected'):
        workspace.propose_handle_edits([{'source_id':handle,'old':'    value = 1\n    other = 2','new':'unindented'}],sources)
    assert workspace.root.joinpath('source/value.py').read_text()=='class Value:\n    value = 1\n    other = 2\n'


def test_changed_line_limit_remains_enforced(workspace):
    handle,sources=binding(workspace)
    with pytest.raises(ValueError,match='200 changed lines'):
        workspace.propose_handle_edits([{'source_id':handle,'old':'class Value:\n    value = 1\n    other = 2\n','new':''.join(f'v{i} = {i}\n' for i in range(201))}],sources)


def test_region_bounds_and_complete_byte_budget(workspace):
    with pytest.raises(ValueError,match='one to 80'):
        workspace.read_original('source/value.py',2,4)
    source=workspace.registry.directory(workspace.case)/'source/source/value.py'
    source.write_text('value = '+repr('x'*8100)+'\n')
    with pytest.raises(ValueError,match='excerpt budget'):
        workspace.read_original('source/value.py',1,1)


def test_action_schema_rejects_raw_paths_and_forged_handle_shape():
    action={'action':'propose_patch','edits':[{'source_id':'S'+'a'*12,'old':'value = 1','new':'value = 2'}]}
    assert ActionV5.validate_python(action).model_dump()==action
    action['edits'][0]['path']='source/value.py'
    with pytest.raises(ValidationError):ActionV5.validate_python(action)
    del action['edits'][0]['path'];action['edits'][0]['source_id']='S1'
    with pytest.raises(ValidationError):ActionV5.validate_python(action)


def test_new_generation_does_not_mutate_historical_defaults():
    before=deepcopy(GENERATION)
    assert generation_for('loop-v4')==before
    new=generation_for('loop-v5')
    assert new['temperature']==0 and new['presence_penalty']==0 and new['top_p']==1
    assert new['max_tokens']==1024 and new['chat_template_kwargs']=={'enable_thinking':False}
    new['chat_template_kwargs']['enable_thinking']=True
    assert GENERATION==before


def test_api_accepts_new_versions_and_preserves_defaults():
    assert CreateInvestigation(task_id='registered',configuration='loop-v5').configuration=='loop-v5'
    assert ForkInvestigation(configuration='baseline-v5').configuration=='baseline-v5'
    assert CreateInvestigation(task_id='registered').configuration=='loop-v3'
    with pytest.raises(ValidationError):ForkInvestigation(configuration='drafts-v5')
