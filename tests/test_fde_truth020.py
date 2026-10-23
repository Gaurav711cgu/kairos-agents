"""Isolated diagnostics must never manufacture a repair or overwrite history."""
from pathlib import Path
import json
import pytest
from scripts import fde_repair_loop as m


class ContextOnlyPeer:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def export_kairos_context(self,**kwargs):return 'Callers: entry\nCallees: helper\nRepository context only'
 def retrieve_code_context(self,**kwargs):return [{'name':'helper'}]
 def get_call_graph(self,**kwargs):return {'callers':[],'callees':[]}


def test_unknown_trace_never_invents_circuit_breaker():
 assert m.parse_traceback('ValueError: bad input').target_symbol=='unknown'


def test_retrieval_only_is_not_a_repair_and_does_not_overwrite(tmp_path):
 harness=m.FDERepairHarness(receipt_directory=tmp_path)
 harness.mcp_client=ContextOnlyPeer()
 a=harness.execute_loop('ValueError: invalid data')
 b=harness.execute_loop('ValueError: invalid data')
 assert a['status']=='CAPTURED' and a['repair_verified'] is False
 assert a['model_calls']==a['verification_runs']==0
 assert a['receipt_path']!=b['receipt_path']
 assert all(Path(r['receipt_path']).exists() for r in (a,b))


def test_handwritten_example_is_explicitly_not_verified_repair(tmp_path,monkeypatch):
 monkeypatch.setattr(m,'KAIROS_ROOT',tmp_path)
 task='pytest-dev__pytest-5221'
 folder=tmp_path/'evidence/measurement014/comparison/records'/task/'loop'
 folder.mkdir(parents=True)
 (folder/'bundle.json').write_text(json.dumps({'task_snapshot':{'issue':'Fixture output omits scope'},'outcome':'no_patch'}))
 historical=tmp_path/'evidence/retrieval011/swebench_pytest5221_mcp_receipt.json'
 historical.parent.mkdir(parents=True);historical.write_text('preserved original bytes')
 harness=m.FDERepairHarness(receipt_directory=tmp_path/'new-captures')
 harness.mcp_client=ContextOnlyPeer()
 result=harness.execute_swebench_case(task)
 assert result['repair_verified'] is False and result['verification_runs']==0
 augmented=result['codesage_augmented']
 assert augmented['patch_origin']=='handwritten_demo'
 assert augmented['target_annotation_supplied'] is True
 assert augmented['tests_executed'] is False
 assert augmented['example_function_syntax_valid'] is True
 assert augmented['patch_syntax_verified'] is False
 assert historical.read_text()=='preserved original bytes'
