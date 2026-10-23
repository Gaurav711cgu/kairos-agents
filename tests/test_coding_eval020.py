import json
from pathlib import Path
import pytest
from scripts.coding_eval020 import parse_action,summarize,prepare

HANDLE='S123456789abc'

def action(**updates):
 edit={'source_id':HANDLE,'start_line':1,'end_line':2,'new':'    return 3\n'};edit.update(updates)
 return {'action':'propose_patch','edits':[edit]}

def test_canonical_action_preserves_replacement_exactly():
 value=action();assert parse_action(json.dumps(value),[HANDLE])==(value,False)

def test_collapsed_edit_only_changes_envelope():
 value={'action':'replace',**action()['edits'][0]};value['replacement']=value.pop('new')
 parsed,changed=parse_action('```json\n'+json.dumps(value)+'\n```',[HANDLE])
 assert changed and parsed==action()

@pytest.mark.parametrize('value',[
 action(source_id='S000000000000'),action(start_line=True),action(start_line='1'),action(start_line=3),action(new=123),
 {'action':'replace','source_id':HANDLE,'start_line':1,'end_line':2},
 {'action':'replace',**action()['edits'][0],'file_path':'../../private'},
 {'action':'replace',**action()['edits'][0],'replacement':'conflict'},
])
def test_invalid_edits_are_not_repaired_by_the_parser(value):
 with pytest.raises(ValueError):parse_action(json.dumps(value),[HANDLE])

def test_no_repair_is_counted_without_independent_check_verdicts():
 with pytest.raises(ValueError):summarize([{'instance_id':'a','arm':'adapter','verified_repair':True}],['a'])


def test_missing_pair_is_incomplete_not_a_model_loss():
 result=summarize([{'instance_id':'a','arm':'base','verified_repair':False,'verification_complete':True}],['a'])
 assert result['paired']['incomplete']==1 and result['paired']['base_only']==0
 assert result['arms']['adapter']['missing_attempts']==1


def test_duplicate_attempt_cannot_inflate_denominator():
 row={'instance_id':'a','arm':'base'}
 with pytest.raises(ValueError):summarize([row,row],['a'])


def test_complete_paired_outcomes_require_complete_independent_checks():
 checks={k:True for k in ['baseline_failed','regression_passed','existing_passed','execution_complete','independent']}
 result=summarize([{'instance_id':'a','arm':'base','verified_repair':False,'verification_complete':True},
 {'instance_id':'a','arm':'adapter','verified_repair':True,'verification_complete':True,'checks':checks}],['a'])
 assert result['paired']['adapter_only']==1 and result['arms']['adapter']['verified_repairs']==1
