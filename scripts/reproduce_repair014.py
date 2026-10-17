"""Recheck the published held-out Django patch without any model execution."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

from scripts import qualify014 as q, qualify006
from scripts.comparison014 import raw_complete014
from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.sandbox import Workspace

ROOT = Path(__file__).resolve().parents[1]
TASK = 'django__django-14752'


def checked_materials(case, scope, row):
    if (row.get('instance_id'), row.get('repo'), row.get('base_commit'), row.get('problem_statement')) != (TASK, case['repository'], case['revision'], case['issue']):
        raise ValueError('External dataset row differs from the registered case')
    original = qualify006.added_test_selectors
    qualify006.added_test_selectors = lambda *_: scope['added_hidden_tests']
    try:
        script, regenerated = qualify006.verifier(row, Path('/unavailable-source'))
    finally:
        qualify006.added_test_selectors = original
    if regenerated != scope:
        raise ValueError('Regenerated verifier scope differs')
    reference = row['patch'].encode()
    verification = (row['test_patch'] + script).encode()
    if hashlib.sha256(reference).hexdigest() != case['reference_digest'] or hashlib.sha256(verification).hexdigest() != case['verification_digest']:
        raise ValueError('External reference/test material differs from qualified hashes')
    return {'reference.patch': reference, 'test.patch': row['test_patch'].encode(), 'verify.py': script.encode()}


def package(root, hidden_records):
    folder = root/'evidence/measurement014/qualification'/TASK
    case = {**q.load(folder/'case-definition.json'), 'qualified': True}
    qualification = q.load(folder/'receipt.json')
    if case.get('id') != TASK or qualification.get('qualified') is not True or case.get('split') != 'holdout':
        raise ValueError('Only the published qualified held-out case is registered')
    report = q.load(root/'evidence/measurement014/comparison/report.json')
    attempt = next(c for c in report['cases'] if c['instance_id'] == TASK)['arms']['loop']
    if report.get('execution_complete') is not True or attempt.get('verified') is not True:
        raise ValueError('A complete frozen comparison with the verified loop result is required')
    record_path = root/'evidence/measurement014/comparison/records'/TASK/'loop/bundle.json'
    if q.sha(record_path) != attempt['record_sha256']:
        raise ValueError('Published investigation digest differs')
    record = q.load(record_path)
    rows = q.load(hidden_records)
    if not isinstance(rows, list):raise ValueError('Provide an external JSON list of original Lite dataset rows')
    candidates = [row for row in rows if row.get('instance_id') == TASK]
    if len(candidates) != 1:raise ValueError('External dataset must contain exactly one matching issue row')
    materials = checked_materials(case,q.load(folder/'test-scope.json'),candidates[0])
    from kairos_api.model_runtime import digest
    winner = next(s['result']['body'] for s in record['steps'] if s['name']=='run_checks' and s.get('result') and s['result']['body'].get('passed') is True)
    patch = next(s['result']['body']['patch'] for s in record['steps'] if s['name']=='propose_patch' and s.get('result') and isinstance(s['result']['body'].get('patch'),str) and digest(s['result']['body']['patch'])==winner['patch_digest'])
    materials['candidate.patch'] = patch.encode()
    return {'case':case,'source':q.load(folder/'source.json'),'materials':materials,'public_provenance_sha256':digest({'qualification':q.sha(folder/'receipt.json'),'record':q.sha(record_path)})}


def run(runtime, roots, hidden_records, root=ROOT):
    value = package(root, hidden_records)
    if runtime.is_symlink():raise ValueError("Use a new reproduction runtime inside a counted storage root")
    runtime = runtime.resolve(strict=False)
    if not any(runtime.is_relative_to(p.resolve(strict=False)) for p in roots) or runtime.exists():
        raise ValueError('Use a new reproduction runtime inside a counted storage root')
    case = value['case']
    engine = subprocess.run(['docker','info','--format','{{.ServerVersion}}'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    actual_image = subprocess.run(['docker','image','inspect',case['image'],'--format','{{.Id}}'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    if actual_image != case['image']:
        raise ValueError('Prepared image differs; record any rebuilt environment separately')
    q.storage_guard(roots, 0)
    runtime.mkdir(parents=True, mode=0o700)
    q.immutable(runtime/'owner.json', {'version':'saved-repair014-runtime-v1','task_id':TASK,'model_dispatches':0})
    source, receipt = q.pinned_source({'instance_id':TASK,'repo':case['repository'],'base_commit':case['revision']},runtime,roots,True,tree_hash)
    if receipt['source_digest'] != case['source_digest']:
        raise ValueError('Fresh source content differs from the qualified revision')
    directory = runtime/'registry/cases'/TASK
    directory.mkdir(parents=True)
    source.rename(directory/'source')
    for name in ['reference.patch','test.patch','verify.py']:
        (directory/name).write_bytes(value['materials'][name])
    q.immutable(runtime/'registry.json', {'version':'repository-cases-v1','cases':[case]})
    registry = CaseRegistry(runtime/'registry.json',runtime/'registry')
    registry.verify(case)
    source_bytes = sum(p.stat().st_size for p in (directory/'source').rglob('*') if p.is_file() and not p.is_symlink())
    q.storage_guard(roots,source_bytes*2)
    captures = {}; workspace = None
    with q.counted_temporary(runtime/'temporary'):
        try:
            workspace = Workspace(registry,case)
            for name, patch in [('baseline',None),('reference',value['materials']['reference.patch'].decode()),('candidate',value['materials']['candidate.patch'].decode())]:
                if patch is None:workspace.reset()
                else:workspace.propose(patch)
                captures[name] = q.captured_check(runtime/(name+'.json'),name,lambda:workspace.checks(timeout=120),value['public_provenance_sha256'],roots,source_bytes)
        finally:
            if workspace is not None:workspace.close()
    qualification = q.check_qualified(captures['baseline'],captures['reference'],qualify006)
    candidate = captures['candidate']; summary = qualify006.summary(candidate)
    registry.verify(case)
    passed = bool(qualification['qualified'] and raw_complete014(candidate) and candidate.get('passed') is True
        and summary.get('execution_complete') is True and summary.get('complete') is True and summary.get('tests_run',0)>0)
    result = {'version':'saved-repair014-reproduction-v1','task_id':TASK,'passed':passed,'model_dispatches':0,
        'baseline':qualification['baseline_summary'],'reference':qualification['reference_summary'],'candidate':summary,
        'image':actual_image,'image_matches_recorded':True,'engine':engine,'original_source_unchanged':True,
        'public_provenance_sha256':value['public_provenance_sha256'],'fresh_source_sha256':receipt['source_digest'],
        'archive_matches_original':receipt['archive_sha256']==value['source']['archive_sha256']}
    q.immutable(runtime/'receipt.json',result)
    q.immutable(runtime/'source-preservation.json',{'source':receipt,'files':q.material_manifest(directory/'source'),'ephemeral_reconstruction':True})
    shutil.rmtree(directory/'source')
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--budget-root',type=Path,action='append')
    p.add_argument('--hidden-records',type=Path,required=True,help='External reviewed Lite rows; never copied into public evidence')
    a=p.parse_args()
    result=run(a.runtime,a.budget_root or [ROOT/'.runtime/investigations'],a.hidden_records)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
