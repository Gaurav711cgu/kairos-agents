"""Frozen 14B adapter comparison: public prompts out, complete generations back.

This comparison reuses already exposed, independently qualified measurement014
cases. It is new to this adapter, not a new benchmark holdout. Reference fixes,
hidden verification and earlier model responses are never included in prompts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

VERSION='coding-repair-comparison020-v1'
BASE='unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit'
REVISION='ecfc63c083900ce4f19daad695e711f38ab98fcf'
SYSTEM='Repair Python source. Return one JSON object with action="propose_patch" and edits containing source_id, start_line, end_line and new. Replace inclusive original source lines. Preserve indentation. Use only the provided source handles. Do not edit tests.'
GENERATION={'do_sample':False,'max_new_tokens':1024,'context_tokens':4096,'seed':42,'max_time_seconds':180,'calls_per_arm_case':1}


def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save_new(path,value):
 with Path(path).open('xb') as f:
  f.write(canonical(value)+b'\n');f.flush()
  import os
  os.fsync(f.fileno())


def prepare(root, corpus, adapter, output):
 from kairos_api.investigations.context_v5 import source_block
 from kairos_api.model_runtime import digest as captured_digest
 from scripts.prepare_hf_model import verify_bundle
 root,output=Path(root),Path(output)
 if output.exists():raise ValueError('Preserve frozen comparison; choose new output')
 trained=verify_bundle(adapter);data=json.loads(Path(corpus).read_text())
 train_ids={r['instance_id'] for r in data['train']};dev_ids={r['instance_id'] for r in data['development']}
 study=json.loads((root/'evidence/measurement014/comparison/study.json').read_text())
 cases=[];excluded=[];bindings=[]
 for item in study['cases']:
  if item['split']!='holdout':continue
  identifier=item['instance_id'];folder=root/'evidence/measurement014/qualification'/identifier
  receipt=json.loads((folder/'receipt.json').read_text())
  if receipt.get('qualified') is not True:
   excluded.append({'instance_id':identifier,'reason':'Original pre-model qualification failed','receipt_sha256':sha(folder/'receipt.json')});continue
  if identifier in train_ids|dev_ids:raise ValueError('Comparison case overlaps training or adapter development')
  if not all(receipt.get(k) is True for k in ['baseline_regression_reproduced','reference_complete_pass','raw_outputs_complete']):raise ValueError('Incomplete independent qualification')
  record_path=root/'evidence/measurement014/comparison/records'/identifier/'baseline/bundle.json'
  record=json.loads(record_path.read_text());case=json.loads((folder/'case-definition.json').read_text())
  if (record['task_id'],record['task_snapshot']['revision'],record['task_snapshot']['source_digest'])!=(identifier,case['revision'],case['source_digest']):raise ValueError('Source revision differs from qualification')
  regions=[]
  for step in record['steps']:
   if step['kind']=='model':break
   if step['name']=='initial_source':
    captured=step['result']
    if captured_digest(captured['body'])!=captured['sha256']:raise ValueError('Captured source body differs')
    body=captured['body']
    if body.get('source')!='original_snapshot':raise ValueError('Context is not original source')
    # truncated means the rest of the file is omitted, not a partial excerpt.
    block=source_block(body);ref=body['reference']
    if len(block['original_source'].splitlines())!=ref['end_line']-ref['start_line']+1:raise ValueError('Incomplete source excerpt')
    if captured_digest({**{k:v for k,v in ref.items() if k!='excerpt_id'},'text':block['original_source']})!=ref['excerpt_id']:raise ValueError('Original excerpt binding differs')
    regions.append(body)
  blocks=[source_block(r) for r in regions]
  messages=[{'role':'system','content':SYSTEM},{'role':'user','content':canonical({'issue':case['issue'],'original_source':blocks}).decode()}]
  cases.append({'instance_id':identifier,'repository':case['repository'],'revision':case['revision'],'source_digest':case['source_digest'],'messages':messages,'source_handles':[b['source_id'] for b in blocks],'context_available':bool(blocks),'unavailable_reason':None if blocks else 'Historical issue-only localization selected no source; retain case and count unavailable without model dispatch'})
  bindings.append({'instance_id':identifier,'record_sha256':sha(record_path),'qualification_sha256':sha(folder/'receipt.json'),'original_regions':regions})
 if not cases:raise ValueError('No qualified comparison cases')
 package={'version':VERSION,'base_model':BASE,'base_revision':REVISION,'generation':GENERATION,'adapter_files':trained['files'],'source_archive_sha256':trained['source_archive_sha256'],'corpus_sha256':sha(corpus),'cases':cases,'exclusions':excluded,'scope':'Previously exposed qualified cases, excluded from this adapter training/development. Not a fresh holdout or official SWE-bench result.','reference_material_included':False,'repair_checks_location':'Separate local disposable verification; no model self-grading'}
 output.mkdir(parents=True)
 save_new(output/'prompts.json',package)
 save_new(output/'private-bindings.json',{'version':VERSION,'prompts_sha256':sha(output/'prompts.json'),'bindings':bindings})
 return package


def parse_action(text, handles):
 """Only syntactic normalization; never infer a path, range or replacement."""
 if not isinstance(text,str) or len(text.encode())>128*1024:raise ValueError('Missing or oversized generation')
 text=text.strip()
 if text.startswith('```'):
  match=re.fullmatch(r'```(?:json)?\s*\n(.*)\n```',text,re.S)
  if not match:raise ValueError('Ambiguous fenced action')
  text=match.group(1)
 raw=json.loads(text)
 if not isinstance(raw,dict):raise ValueError('Action must be an object')
 normalized=False
 if raw.get('action') in {'replace','insert'}:
  if set(raw)-{'action','source_id','start_line','end_line','new','replacement'}:raise ValueError('Unknown collapsed edit fields')
  if ('new' in raw)==('replacement' in raw):raise ValueError('Exactly one replacement field required')
  raw={'action':'propose_patch','edits':[{k:raw[k] for k in ['source_id','start_line','end_line']}|{'new':raw.get('new',raw.get('replacement'))}]};normalized=True
 if set(raw)!={'action','edits'} or raw['action']!='propose_patch' or not isinstance(raw['edits'],list) or not 1<=len(raw['edits'])<=8:raise ValueError('Invalid patch action')
 for edit in raw['edits']:
  if not isinstance(edit,dict) or set(edit)!={'source_id','start_line','end_line','new'}:raise ValueError('Invalid edit fields')
  if edit['source_id'] not in handles:raise ValueError('Unknown source handle')
  if any(type(edit[k]) is not int for k in ['start_line','end_line']) or not 1<=edit['start_line']<=edit['end_line']:raise ValueError('Invalid inclusive bounds')
  if not isinstance(edit['new'],str) or len(edit['new'].encode())>16000:raise ValueError('Invalid replacement text')
 return raw,normalized


def summarize(records, expected):
 """Include every expected pair; missing checks never become failures or passes."""
 indexed={}
 for r in records:
  key=(r['instance_id'],r['arm'])
  if key in indexed or r['instance_id'] not in expected or r['arm'] not in {'base','adapter'}:raise ValueError('Duplicate or unexpected result')
  if r.get('verified_repair') is True:
   c=r.get('checks',{})
   if not all(c.get(k) is True for k in ['baseline_failed','regression_passed','existing_passed','execution_complete','independent']):raise ValueError('Unverified repair cannot be scored')
  indexed[key]=r
 output={'scope':'Small historically exposed comparison; no fresh holdout claim','expected_cases':len(expected),'arms':{},'paired':{'adapter_only':0,'base_only':0,'both':0,'neither':0,'incomplete':0}}
 for arm in ['base','adapter']:
  values=[indexed[(i,arm)] for i in expected if (i,arm) in indexed]
  output['arms'][arm]={'attempts':len(values),'verified_repairs':sum(v.get('verified_repair') is True for v in values),'unverified_or_unavailable':sum(v.get('verified_repair') is not True for v in values),'missing_attempts':len(expected)-len(values)}
 for i in expected:
  a=indexed.get((i,'adapter'));b=indexed.get((i,'base'))
  if a is None or b is None or any(x.get('verification_complete') is not True for x in [a,b]):key='incomplete'
  elif a.get('verified_repair') and b.get('verified_repair'):key='both'
  elif a.get('verified_repair'):key='adapter_only'
  elif b.get('verified_repair'):key='base_only'
  else:key='neither'
  output['paired'][key]+=1
 return output


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare']);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--adapter',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 d=prepare(a.root,a.corpus,a.adapter,a.output);print(json.dumps({'cases':len(d['cases']),'exclusions':len(d['exclusions']),'model_calls':0,'frozen_prompts_sha256':sha(a.output/'prompts.json')}))


if __name__=='__main__':main()
