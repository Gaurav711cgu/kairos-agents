"""Qualify registered training candidates with independent sandbox checks, never inference."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import shutil
import subprocess

from scripts import qualify014 as q, qualify006
from scripts.coding_data014 import SHA256, canonical, patch_scope
from scripts.coding_verifier014 import verifier, qualifies
from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.sandbox import Workspace
from kairos_api.model_runtime import digest

ROOT=Path(__file__).resolve().parents[1]
SOURCE_PREFIXES={'Project-MONAI/MONAI':'monai/','getmoto/moto':'moto/'}
SUPPORTED_ENVIRONMENTS={('Project-MONAI/MONAI','0.2'):'MONAI0.2',('Project-MONAI/MONAI','0.3'):'MONAI0.3',('getmoto/moto','3.0'):'Moto3.0'}


def selected_row(rows,screen,identifier):
    if identifier not in screen['candidate_ids']:raise ValueError('Task is not in the frozen training candidate list')
    matches=[r for r in rows if r['instance_id']==identifier]
    if len(matches)!=1:raise ValueError('Dataset row is absent or duplicated')
    row=matches[0];entry=next(r for r in screen['ledger'] if r['instance_id']==identifier)
    if hashlib.sha256(canonical(row)).hexdigest()!=entry['row_sha256']:raise ValueError('Frozen dataset row differs')
    expected=SUPPORTED_ENVIRONMENTS.get((row['repo'],row['version']))
    if expected is None:raise ValueError('No reviewed environment for this repository/version; preserve candidate as pending')
    if patch_scope(row['patch'])!=entry['scope']:raise ValueError('Frozen source scope differs')
    return row,expected


def image_identity(receipt_path,expected):
    image=q.load(receipt_path);review_path=receipt_path.parent/'review.json';review=q.load(review_path)
    if (image['review_sha256']!=q.sha(review_path) or review['repository_version']!=expected
            or image['user']!='10001:10001' or image['architecture']!='arm64' or image['os']!='linux'
            or not q.re.fullmatch(r'sha256:[a-f0-9]{64}',image['id'])):
        raise ValueError('Reviewed environment identity differs')
    actual=subprocess.run(['docker','image','inspect',image['id'],'--format','{{.Id}}'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    if actual!=image['id']:raise ValueError('Prepared image differs')
    return image


def revision_gate(folder,revision):
    if revision not in {'v1','v2'}:raise ValueError('Unsupported qualification revision')
    if revision=='v1':return
    previous=folder/'qualification-v1';receipt=q.load(previous/'receipt.json')
    if receipt.get('qualified') is not False or receipt.get('model_calls')!=0 or not receipt.get('original_source_unchanged'):
        raise ValueError('Only a captured pre-model environment failure may receive a dependency revision')
    for stage in ['baseline','reference']:
        if q.sha(previous/(stage+'.json'))!=receipt['checks_sha256'][stage]:raise ValueError('Prior failed capture changed')
    if not any(receipt[stage].get('execution_complete') is False for stage in ['baseline','reference']):
        raise ValueError('A completed behavioral failure cannot be replaced by a dependency retry')


def qualify(runtime,identifier,image_receipt,roots,allow_download=False,revision='v1'):
    runtime=q.no_symlinks(runtime)
    if not q.covered(runtime,roots):raise ValueError('Runtime must be inside counted storage roots')
    if q.sha(runtime/'swe-gym.parquet')!=SHA256:raise ValueError('Pinned dataset differs')
    import pyarrow.parquet as pq
    rows=pq.read_table(runtime/'swe-gym.parquet').to_pylist();screen=q.load(runtime/'screen.json')
    row,environment=selected_row(rows,screen,identifier)
    image=image_identity(image_receipt,environment)
    folder=runtime/'qualification-preparation'/identifier;folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    original=dict(q.PREFIXES)
    try:
        q.PREFIXES.update(SOURCE_PREFIXES)
        source,source_receipt=q.pinned_source(row,folder,roots,allow_download,tree_hash)
    finally:
        q.PREFIXES.clear();q.PREFIXES.update(original)
    q.storage_guard(roots,q.tree_bytes(source)*3+q.CHECK_RESERVATION)
    revision_gate(folder,revision)
    output=folder/('qualification-'+revision);output.mkdir(exist_ok=True,mode=0o700)
    script,scope=verifier(row);logical_id='coding014-'+identifier.lower()
    case={'id':logical_id,'dataset_instance_id':identifier,'repository':row['repo'],'revision':row['base_commit'],'issue':row['problem_statement'],'split':'training_candidate','qualified':False,'approved_prefix':SOURCE_PREFIXES[row['repo']],'entry_lines':patch_scope(row['patch'])['paths'],'command':['python','/verification/verify.py'],'image':image['id'],'source_digest':source_receipt['source_digest'],'reference_digest':hashlib.sha256(row['patch'].encode()).hexdigest(),'verification_digest':hashlib.sha256((row['test_patch']+script).encode()).hexdigest()}
    binding=digest({'case':case,'scope':scope,'screen_sha256':q.sha(runtime/'screen.json'),'image_receipt_sha256':q.sha(image_receipt)})
    final=output/'receipt.json'
    if final.exists():
        receipt=q.load(final)
        if receipt.get('binding')!=binding or receipt.get('instance_id')!=identifier or receipt.get('image')!=image['id']:
            raise ValueError('Captured qualification identity differs')
        captured={}
        for key,expected in receipt['checks_sha256'].items():
            if key not in {'baseline','reference'} or q.sha(output/(key+'.json'))!=expected:raise ValueError('Captured check differs')
            item=q.load(output/(key+'.json'))
            if item['binding']!=binding or item['stage']!=key:raise ValueError('Captured check binding differs')
            captured[key]=item['result']
        if set(captured)!={'baseline','reference'} or qualifies(captured['baseline'],captured['reference'])!=receipt['qualified']:
            raise ValueError('Captured qualification verdict differs')
        return receipt
    case_dir=output/'registry/cases'/logical_id;case_dir.mkdir(parents=True,exist_ok=True)
    if not (case_dir/'source').exists():shutil.copytree(source,case_dir/'source',symlinks=True)
    if tree_hash(case_dir/'source')!=case['source_digest']:raise ValueError('Registry source differs')
    for name,data in [('reference.patch',row['patch']),('test.patch',row['test_patch']),('verify.py',script)]:
        target=case_dir/name
        if target.exists():
            if target.read_text()!=data:raise ValueError('Verification material changed')
        else:target.write_text(data)
    q.immutable(output/'registry.json',{'version':'repository-cases-v1','cases':[case]});q.immutable(output/'scope.json',scope)
    q.immutable(output/'binding.json',{'version':'coding-qualification-binding014-v1','binding':binding,'model_calls':0,'case':case,'scope':scope})
    registry=CaseRegistry(output/'registry.json',output/'registry');registry.verify(case)
    captures={};workspace=None;size=q.tree_bytes(source)
    with q.counted_temporary(output/'temporary'):
        try:
            workspace=Workspace(registry,case)
            captures['baseline']=q.captured_check(output/'baseline.json','baseline',lambda:workspace.checks(timeout=120),binding,roots,size)
            workspace.propose(row['patch'])
            captures['reference']=q.captured_check(output/'reference.json','reference',lambda:workspace.checks(timeout=120),binding,roots,size)
        finally:
            if workspace is not None:workspace.close()
    registry.verify(case)
    if tree_hash(source)!=case['source_digest']:raise ValueError('Original source changed')
    receipt={'version':'coding-qualification014-v1','instance_id':identifier,'logical_case_id':logical_id,'binding':binding,'qualified':qualifies(captures['baseline'],captures['reference']),'model_calls':0,'training_admitted':False,'remaining_admission':['case-specific issue/source rights review','issue-family and near-duplicate resolution','complete action conversion and corpus/split gates'],'original_source_unchanged':True,'image':image['id'],'baseline':qualify006.summary(captures['baseline']),'reference':qualify006.summary(captures['reference']),'checks_sha256':{key:q.sha(output/(key+'.json')) for key in captures}}
    q.immutable(final,receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--task-id',required=True)
    parser.add_argument('--image-receipt',type=Path,required=True);parser.add_argument('--budget-root',type=Path,action='append',required=True)
    parser.add_argument('--allow-source-download',action='store_true');parser.add_argument('--revision',choices=['v1','v2'],default='v1');args=parser.parse_args()
    lock_path=ROOT/'.runtime/coding-qualification014.lock';lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open('a+b') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another coding-data qualifier is active') from None
        result=qualify(args.runtime,args.task_id,args.image_receipt,args.budget_root,args.allow_source_download,args.revision)
    print(json.dumps({'instance_id':result['instance_id'],'qualified':result['qualified'],'model_calls':0,'training_admitted':False,'baseline_tests':result['baseline'].get('tests_run'),'reference_tests':result['reference'].get('tests_run')},indent=2))


if __name__=='__main__':main()
