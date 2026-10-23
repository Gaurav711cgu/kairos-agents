"""Admission for the new paired comparison; never dispatch an incomplete cohort."""
import hashlib,json
from pathlib import Path
BASE='unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit'
REVISION='ecfc63c083900ce4f19daad695e711f38ab98fcf'
ADAPTER='89b75305f4e68dce0c5ea7e0123f8c9f2e4788ffb1a36135e2e67fba18eb8516'
GENERATION={'do_sample':False,'seed':42,'context_tokens':4096,'max_new_tokens':1024,'max_time_seconds':180}

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def freeze(cases,bindings,directory,*,qualification_root=None,qualification_binding=None,qualifier=None):
 if len(cases)!=20 or len({c['instance_id'] for c in cases})!=20:raise ValueError('Exactly twenty distinct qualified cases required')
 if any(sum(c['repository']==repo for c in cases)!=10 for repo in ['django/django','pytest-dev/pytest']):raise ValueError('Require ten qualified cases per repository')
 jobs=[];receipt_bindings={}
 for index,case in enumerate(cases):
  if not all(case.get(k) is True for k in ['baseline_regression_reproduced','reference_complete_pass','raw_outputs_complete','exposure_audit_complete']):raise ValueError('Incomplete independent qualification or exposure audit')
  if not case.get('messages') or not case.get('source_handles'):raise ValueError('Missing original-source prompt authority')
  if qualification_root is None or qualification_binding is None or qualifier is None:raise ValueError('Qualification artifact verification required')
  verified=admit_receipt(qualification_root,case['instance_id'],qualification_binding,qualifier)
  receipt_bindings[case['instance_id']]=verified['qualification_receipt_sha256']
  arms=['base','adapter'] if index%2==0 else ['adapter','base']
  for arm in arms:jobs.append({'job_id':case['instance_id']+'/'+arm,'instance_id':case['instance_id'],'arm':arm,'messages':case['messages'],'source_handles':case['source_handles'],'generation':GENERATION})
 if not {'implementation','verifier','source','protocol','exposure'}.issubset(bindings) or any(not isinstance(v,str) or len(v)!=64 or any(x not in '0123456789abcdef' for x in v) for v in bindings.values()):raise ValueError('Frozen implementation/verifier/source hashes required')
 package={'version':'unseen023-paired-v1','base_model':BASE,'base_revision':REVISION,'adapter_archive_sha256':ADAPTER,'bindings':bindings,'qualification_receipts':receipt_bindings,'jobs':jobs,'scope':'New to project evaluation; foundation-model pretraining exposure unknown','retries':'Uncertain dispatches remain unknown; no automatic retry'}
 output=Path(directory);output.mkdir(parents=True,exist_ok=False);payload=canonical(package)+b'\n'
 with (output/'prompts.json').open('xb') as f:f.write(payload)
 (output/'freeze.json').write_text(json.dumps({'sha256':hashlib.sha256(payload).hexdigest(),'jobs':40,'cases':20,'status':'frozen_not_executed'},indent=2)+'\n')
 return package

def admit_receipt(root,identifier,expected_binding,qualifier):
 """Recheck captured qualification evidence instead of trusting admission booleans."""
 import re
 if not re.fullmatch(r'[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-\d+',identifier):raise ValueError('Invalid case identity')
 directory=Path(root)/'cases'/identifier
 if any(p.is_symlink() for p in [Path(root),Path(root)/'cases',directory]):raise ValueError('Symlink qualification directory')
 receipt_path=directory/'receipt.json'
 if receipt_path.is_symlink():raise ValueError('Symlink qualification receipt')
 receipt=json.loads(receipt_path.read_text())
 if receipt.get('binding')!=expected_binding or receipt.get('instance_id')!=identifier or receipt.get('qualified') is not True:raise ValueError('Unqualified or differently bound receipt')
 required={'baseline.json','reference.json','case-definition.json','source.json'}
 if not required.issubset(receipt.get('evidence_sha256',{})):raise ValueError('Missing qualification artifact bindings')
 for name,expected in receipt['evidence_sha256'].items():
  if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',name):raise ValueError('Invalid artifact reference')
  path=directory/name
  if path.is_symlink() or not path.is_file():raise ValueError('Missing or symlink qualification artifact')
  with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
  if actual!=expected:raise ValueError('Qualification artifact hash differs')
 from scripts.qualify014 import check_qualified
 results=[]
 for name in ['baseline.json','reference.json']:
  capture=json.loads((directory/name).read_text())
  if capture['binding']!=expected_binding:raise ValueError('Check belongs to another qualification')
  validate_raw_output(capture['result'])
  results.append(capture['result'])
 verdict=check_qualified(*results,qualifier)
 if verdict['qualified'] is not True:raise ValueError('Captured results do not qualify')
 return verdict|{'qualification_receipt_sha256':hashlib.sha256(receipt_path.read_bytes()).hexdigest(),'case':json.loads((directory/'case-definition.json').read_text())}

def validate_raw_output(result):
 import base64
 raw=result.get('raw_output',{})
 if raw.get('complete') is not True or raw.get('encoding')!='base64':raise ValueError('Incomplete raw verification output')
 for channel in ['stdout','stderr']:
  stream=raw[channel];data=stream['data']
  if not isinstance(data,str) or len(data)>1400000 or stream.get('truncated'):raise ValueError('Oversized or truncated verification output')
  decoded=base64.b64decode(data,validate=True)
  if len(decoded)!=stream['bytes'] or len(decoded)!=stream['observed_bytes'] or hashlib.sha256(decoded).hexdigest()!=stream['sha256']:raise ValueError('Raw verification output hash or length differs')
