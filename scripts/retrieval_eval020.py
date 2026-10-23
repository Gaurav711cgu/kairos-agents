"""Issue-only, equal-token retrieval diagnostic; never a repair benchmark.

Historical cohort labels are visible development material. Target annotations are
passed only to scoring after both retrieval arms have completed. This command
never writes old receipts, calls a model, launches Docker or updates the index.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote

import networkx as nx

VERSION = 'issue-only-retrieval020-v1'
REPOSITORIES = {
 'pytest-dev/pytest':'13f45074-dd7f-435e-a7b7-a49e102299fb',
 'psf/requests':'47f23611-92ad-4fce-973c-220302662b97',
 'pallets/flask':'dfa6d778-ab20-4f4f-8208-e5b4df98b25b',
 'mwaskom/seaborn':'d0733592-e1d9-4b4c-87a8-41abad37f40e',
}


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()


def lexical_ranking(issue, chunks):
    # Use one shared lexical scorer for graph seeds and the baseline arm.
    from scripts.eval_swebench_batch import compute_bm25_scores, tokenize
    values=compute_bm25_scores(tokenize(issue),list(chunks.values()))
    return [(score,c['id']) for score,c in sorted(values,key=lambda pair:(-pair[0],pair[1]['id'])) if score>0]


def rank_candidates(issue, chunks, graph, *, graph_enabled, max_nodes=20, max_degree=15):
    """Only issue/source enter ranking; there is no target or caller parameter."""
    if not 1<=max_nodes<=20 or not 1<=max_degree<=15:
        raise ValueError('Invalid retrieval bound')
    ranked=lexical_ranking(issue,chunks)
    if not graph_enabled:
        return [cid for _,cid in ranked[:max_nodes]]
    scores={cid:score for score,cid in ranked}
    seeds=[cid for _,cid in ranked[:min(3,max_nodes)]]
    distance={cid:0 for cid in seeds}
    frontier=seeds
    for depth in (1,2):
        candidates=set()
        for cid in frontier:
            if cid not in graph:continue
            adjacent=set(graph.successors(cid))|set(graph.predecessors(cid))
            candidates.update(sorted(adjacent,key=lambda n:(-scores.get(n,0),n))[:max_degree])
        candidates.difference_update(distance)
        frontier=sorted(candidates,key=lambda n:(-scores.get(n,0),n))
        for cid in frontier:
            if cid in chunks:distance[cid]=depth
    # Deterministic lexical relevance first, structural proximity as tie breaker.
    # The policy is fixed before this diagnostic is executed; never use labels.
    ordered=sorted(distance,key=lambda cid:(-scores.get(cid,0),distance[cid],cid))
    return ordered[:max_nodes]


def pack_context(ordered, chunks, count_tokens, budget):
    if type(budget) is not int or budget<1:raise ValueError('Invalid token budget')
    selected=[];omitted=[];text=''
    for cid in ordered:
        chunk=chunks[cid]
        block=f"File: {chunk.get('file','')}\nSymbol: {chunk.get('name','')}\n{chunk.get('source','')}\n"
        candidate=text+block
        size=count_tokens(candidate)
        if size<=budget:
            selected.append(cid);text=candidate
        else:omitted.append({'id':cid,'reason':'Complete chunk exceeds remaining token budget'})
    return {'ids':selected,'context':text,'tokens':count_tokens(text),'omitted':omitted}


def score_result(result, chunks, target_file, target_symbol):
    target_file=target_file.replace('\\','/').lstrip('./')
    for rank,cid in enumerate(result['ids'],1):
        c=chunks[cid];name=re.sub(r'::part_\d+$','',c.get('name',''))
        path=c.get('file','').replace('\\','/').lstrip('./')
        if (path==target_file or path.endswith('/'+target_file)) and (name==target_symbol or name.endswith('.'+target_symbol)):
            return {'localized':True,'rank':rank,'reciprocal_rank':1/rank}
    return {'localized':False,'rank':None,'reciprocal_rank':0.0}


def load_index(codesage_root, repository):
    identifier=REPOSITORIES[repository]
    manifest=codesage_root/'.chroma/manifests'/f'{identifier}_manifest.json'
    records=json.loads(manifest.read_text())
    chunks={c['id']:c for file in records.values() for c in file.get('chunks_data',[])}
    graph=nx.DiGraph();graph.add_nodes_from(chunks)
    database=codesage_root/'app.db'
    with sqlite3.connect('file:'+quote(str(database.resolve()))+'?mode=ro',uri=True) as conn:
        graph.add_edges_from(conn.execute('SELECT source,target FROM graph_edges WHERE repo_id=? OR repo_id=?',(identifier,identifier.replace('-',''))))
        row=conn.execute('SELECT github_url FROM repos WHERE id=? OR id=?',(identifier,identifier.replace('-',''))).fetchone()
        source_kind='installed_python_package' if row and '/site-packages/' in row[0] else 'unbound_index'
    classes={(c.get('file'),c.get('name')):cid for cid,c in chunks.items() if c.get('type')=='class'}
    for cid,c in chunks.items():
        parent=classes.get((c.get('file'),c.get('parent_class')))
        if parent:graph.add_edge(parent,cid)
    return chunks,graph,{'repository':repository,'manifest_sha256':sha(manifest),'nodes':len(chunks),'edges':graph.number_of_edges(),'source_kind':source_kind,'case_revision_bound':False}


def evaluate(cohort, codesage_root, tokenizer_path, tokenizer_sha256, budget=1024):
    from tokenizers import Tokenizer
    if sha(tokenizer_path)!=tokenizer_sha256:raise ValueError('Tokenizer identity changed')
    tokenizer=Tokenizer.from_file(str(tokenizer_path))
    count=lambda text:len(tokenizer.encode(text,add_special_tokens=False).ids)
    indexes={repo:load_index(codesage_root,repo) for repo in sorted({c['repo'] for c in cohort['instances']})}
    cases=[]
    for case in cohort['instances']:
        chunks,graph,_=indexes[case['repo']]
        arms={}
        for arm,enabled in [('lexical',False),('graph',True)]:
            started=time.perf_counter()
            ranked=rank_candidates(case['problem_statement'],chunks,graph,graph_enabled=enabled)
            result=pack_context(ranked,chunks,count,budget)
            elapsed=(time.perf_counter()-started)*1000
            # Scoring is deliberately downstream of context selection.
            scoring=score_result(result,chunks,case['ground_truth_file'],case['ground_truth_symbol'])
            arms[arm]={**scoring,'selected_ids':result['ids'],'context_sha256':hashlib.sha256(result['context'].encode()).hexdigest(),'context_tokens':result['tokens'],'omissions':result['omitted'],'selection_and_packing_ms':elapsed}
        cases.append({'instance_id':case['instance_id'],'issue_sha256':hashlib.sha256(case['problem_statement'].encode()).hexdigest(),'arms':arms,'repair_outcome':'not_executed'})
    return {'version':VERSION,'scope':'Exposed development-cohort retrieval diagnostic on existing index snapshots; not a SWE-bench repair score',
        'token_budget_per_arm':budget,'tokenizer_sha256':tokenizer_sha256,'candidate_limit_including_seeds':20,
        'hidden_annotations_used_in_retrieval':False,'model_calls':0,'verification_runs':0,'mcp_latency_measured':False,
        'source_revisions_bound_to_cases':False,'benchmark_eligible':False,
        'eligibility_reason':'Index snapshots are not bound to each historical case base revision; symbol matches are diagnostics, not benchmark recall', 'timing_scope':'In-process ranking and token packing; excludes index loading and MCP transport',
        'summary':{arm:{'benchmark_recall':None,'benchmark_mrr':None,'diagnostic_symbol_matches':sum(c['arms'][arm]['localized'] for c in cases),'cases':len(cases)} for arm in ('lexical','graph')},
        'indexes':[value[2] for value in indexes.values()],'cases':cases}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',type=Path,required=True)
    parser.add_argument('--codesage-root',type=Path,required=True)
    parser.add_argument('--tokenizer',type=Path,required=True)
    parser.add_argument('--tokenizer-sha256',required=True)
    parser.add_argument('--budget',type=int,default=1024)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Preserve prior diagnostic; choose a new output path')
    if not 1<=args.budget<=2048:raise ValueError('Diagnostic context budget must be 1..2048')
    cohort=json.loads(args.cohort.read_text())
    if not cohort.get('instances'):raise ValueError('Empty cohort')
    result=evaluate(cohort,args.codesage_root,args.tokenizer,args.tokenizer_sha256,args.budget)
    result['cohort_sha256']=sha(args.cohort);result['runner_sha256']=sha(Path(__file__))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as out:json.dump(result,out,indent=2)
    print(json.dumps(result['summary']))


if __name__=='__main__':main()
