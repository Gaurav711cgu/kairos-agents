"""V7 source authority, complete feedback and preserved historical protocol."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from kairos_api.investigations.contracts import ActionV7,generation_for,GENERATION
from kairos_api.investigations.context_v7 import failure_feedback,initial_sources
from test_edits_v5 import workspace,binding
from test_context_v5 import tokenizer,excerpt,CASE,BUDGET
from kairos_api.investigations.model import LocalInvestigator


def test_line_handle_replacement_keeps_original_and_indentation(workspace):
    handle,sources=binding(workspace)
    result=workspace.propose_line_edits([{'source_id':handle,'start_line':2,'end_line':2,'new':'    value = 7'}],sources)
    assert '    value = 7\n' in workspace.root.joinpath('source/value.py').read_text()
    assert 'value = 1' in workspace.read_original('source/value.py')['text']
    assert result['construction']=='captured-source-line-handles-v7'


def test_explicit_preserve_restores_only_original_whitespace(workspace):
    handle,sources=binding(workspace)
    result=workspace.propose_line_edits([{'source_id':handle,'start_line':2,'end_line':2,
                                        'new':'value = 7','indentation':'preserve'}],sources)
    assert workspace.root.joinpath('source/value.py').read_text()=='class Value:\n    value = 7\n    other = 2\n'
    assert result['edits'][0]['new']=='value = 7'
    with pytest.raises(ValueError,match='relative column zero'):
        workspace.propose_line_edits([{'source_id':handle,'start_line':2,'end_line':2,
                                      'new':'    value = 7','indentation':'preserve'}],sources)
    with pytest.raises(ValueError,match='syntax rejected'):
        workspace.propose_line_edits([{'source_id':handle,'start_line':2,'end_line':2,
                                      'new':'value = (','indentation':'preserve'}],sources)


@pytest.mark.parametrize('alteration',['bounds','digest','path','overlap','syntax'])
def test_invalid_line_edits_do_not_relax_authority(workspace,alteration):
    handle,sources=binding(workspace,2,2);sources=deepcopy(sources)
    edits=[{'source_id':handle,'start_line':2,'end_line':2,'new':'    value = 9\n'}]
    if alteration=='bounds': edits[0]['end_line']=3
    elif alteration=='digest':sources[handle]['source_digest']='0'*64
    elif alteration=='path':sources[handle]['path']='../reference.patch'
    elif alteration=='overlap':edits.append(dict(edits[0]))
    else:edits[0]['new']='  def broken(\n'
    with pytest.raises(ValueError):workspace.propose_line_edits(edits,sources)


def test_feedback_contains_middle_assertion_with_exact_byte_offsets():
    text='prefix λ\n'*40+'E   AssertionError: expected 2, got 1\n'+'tail\n'*30
    feedback,omissions=failure_feedback({'stdout':text,'stderr':'','passed':False,'tests_run':4})
    assert any('expected 2, got 1' in item['text'] for item in feedback['excerpts'])
    for item in feedback['excerpts']:
        assert text.encode()[item['byte_start']:item['byte_end']].decode()==item['text']
    assert omissions and feedback['tests_run']==4


def test_v7_schema_and_source_survive_tool_history(tokenizer):
    request,context=LocalInvestigator().prepare(CASE,'loop-v7',[{'action':'initial_source','result':excerpt()}],BUDGET)
    assert context['selection']['source_blocks'][0]['numbered_original_source']=='1: value = 1\n'
    edit=request['response_format']['json_schema']['schema']['$defs']['LineHandleEdit']
    assert 'indentation' in edit['required'] and edit['properties']['indentation']['enum']==['preserve']
    assert 'run_checks' not in context['allowed_actions']
    assert generation_for('loop-v7')['max_tokens']==1024
    assert generation_for('loop-v1')==GENERATION


def test_explicit_function_and_direct_helper_precede_indirect_usage(tmp_path):
    directory=tmp_path/'case';source=directory/'source/package';source.mkdir(parents=True)
    (source/'value.py').write_text('def indirect():\n    target = 1\n    return target\n\ndef target():\n    return helper()\n\ndef helper():\n    return 1\n')
    from kairos_api.investigations.sandbox import Workspace
    registry=SimpleNamespace(verify=lambda _:None,directory=lambda _:directory)
    case={'issue':'target() must return 2','approved_prefix':'package/','entry_files':['package/value.py']}
    instance=Workspace(registry,case)
    try:
        regions=initial_sources(instance)
        assert 'def target()' in regions[0]['text']
        assert any('def helper()' in region['text'] for region in regions)
    finally:instance.close()
