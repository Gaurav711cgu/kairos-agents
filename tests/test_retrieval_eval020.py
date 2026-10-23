import importlib.util
from pathlib import Path
import sys
import networkx as nx
import pytest
spec=importlib.util.spec_from_file_location('retrieval020',Path(__file__).parents[1]/'scripts/retrieval_eval020.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def chunks():
 return {f'n{i}':{'id':f'n{i}','name':'send' if i==0 else f'helper{i}','file':'src/session.py','source':f'def function{i}(): return {i}','docstring':'redirect' if i==0 else ''} for i in range(30)}


def test_retrieval_has_no_target_annotation_input_and_stable_ties():
 c=chunks();g=nx.DiGraph((('n0',f'n{i}') for i in range(1,30)))
 result=m.rank_candidates('redirect',c,g,graph_enabled=True)
 assert len(result)<=20
 assert result==m.rank_candidates('redirect',dict(reversed(list(c.items()))),g,graph_enabled=True)
 with pytest.raises(TypeError):m.rank_candidates('redirect',c,g,graph_enabled=True,caller_symbol='helper29')


def test_exact_joint_packing_includes_headers_and_records_oversized_chunks():
 c=chunks();count=lambda s:len(s.encode())
 result=m.pack_context(['n0','n1','n2'],c,count,150)
 assert result['tokens']<=150 and count(result['context'])==result['tokens']
 assert result['omitted'] and len(result['ids'])<3


def test_ranking_records_actual_position_and_requires_target_file():
 c=chunks();r={'ids':['n0','n1','n2']}
 assert m.score_result(r,c,'src/session.py','helper2')['rank']==3
 assert m.score_result(r,c,'other.py','helper2')['localized'] is False
 assert m.score_result(r,c,'src/session.py','not_found')['rank'] is None


def test_source_and_labels_do_not_change_selected_context():
 c=chunks();g=nx.DiGraph([('n0','n1')])
 selected=m.rank_candidates('redirect',c,g,graph_enabled=True)
 result=m.pack_context(selected,c,len,1000)
 original=list(result['ids'])
 m.score_result(result,c,'src/session.py','helper1')
 m.score_result(result,c,'private/reference.py','secret_answer')
 assert result['ids']==original


@pytest.mark.parametrize('nodes,degree',[(0,10),(21,10),(5,0),(5,16)])
def test_unbounded_expansion_rejected(nodes,degree):
 with pytest.raises(ValueError):m.rank_candidates('redirect',chunks(),nx.DiGraph(),graph_enabled=True,max_nodes=nodes,max_degree=degree)


def test_unbound_index_never_produces_a_benchmark_score(tmp_path,monkeypatch):
 from tokenizers import Tokenizer, models
 tokenizer=Tokenizer(models.WordLevel({"[UNK]":0,"redirect":1},unk_token="[UNK]"))
 path=tmp_path/'tokenizer.json';tokenizer.save(str(path))
 c=chunks();graph=nx.DiGraph([('n0','n1')])
 monkeypatch.setattr(m,'load_index',lambda root,repo:(c,graph,{'repository':repo,'source_kind':'unbound_index','case_revision_bound':False}))
 cohort={'instances':[{'instance_id':'isolated-fixture','repo':'fixture','problem_statement':'redirect','ground_truth_file':'src/session.py','ground_truth_symbol':'send'}]}
 result=m.evaluate(cohort,tmp_path,path,m.sha(path),128)
 assert result['benchmark_eligible'] is False
 assert result['summary']['graph']['benchmark_recall'] is None
 assert result['model_calls']==result['verification_runs']==0
 assert result['cases'][0]['repair_outcome']=='not_executed'


def test_retired_evaluator_cannot_overwrite_historical_receipts():
 from scripts.eval_swebench_batch import run_empirical_batch_evaluation
 with pytest.raises(RuntimeError,match='retired'):
  run_empirical_batch_evaluation()
