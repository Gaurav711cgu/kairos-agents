"""Predeclared fresh-case selection and hermetic baseline/reference qualification."""
import json
from pathlib import Path
import subprocess

from scripts import qualify006 as recipes
from scripts.study007_runtime import ROOT,save,sha,storage_guard
from kairos_api.investigations.registry import CaseRegistry,tree_hash
from kairos_api.investigations.sandbox import Workspace

REPOSITORIES=('django/django','pytest-dev/pytest')


def historical_ids():
    """Exclude prior studies and actual model attempts, not unused preflight candidates."""
    result=set()
    for name in ('provenance.json','investigations.json','study004.json'):
        value=json.loads((ROOT/'cases'/name).read_text())
        for row in value.get('cases',value.get('records',[])):
            identifier=row.get('id') or row.get('instance_id')
            if identifier: result.add(identifier)
    for path in (ROOT/'evidence/build004/qualification').glob('*.json'):
        result.add(path.stem)
    for path in (ROOT/'evidence/build006').rglob('*.json'):
        value=json.loads(path.read_text())
        if isinstance(value,dict) and 'steps' in value and value.get('task_id'):
            result.add(value['task_id'])
    return result


def plan(rows):
    history=historical_ids();selected={};exclusions=[]
    for repository in REPOSITORIES:
        candidates=[]
        for row in sorted((r for r in rows if r['repo']==repository),key=lambda r:r['instance_id']):
            identifier=row['instance_id']
            if identifier in history:
                exclusions.append({'id':identifier,'reason':'Previously designated build003/build004 case or actual model attempt'})
                continue
            candidates.append(identifier)
            if len(candidates)==5: break
        selected[repository]=candidates
    return {'version':'qualification007-v1','candidate_ids':selected,'historical_exclusions':exclusions,
            'ordering':'Instance ID ascending','target_per_repository':3,'maximum_candidates_per_repository':5,
            'eligibility':{'source_files':2,'changed_lines':40,'memory_bytes':1024**3,'check_seconds':120},
            'preflight_retries':'Unused build006 preflight candidates may be independently requalified; no prior model attempt is allowed',
            'source_localization':'Registered entry files disclose maintainer-localized paths, never patch text or line hints',
            'contamination':'Public historical cases may have appeared in training'}


def qualify(paths,execute=False):
    rows=json.loads(paths['dataset'].read_text());selection={**plan(rows),'dataset_sha256':sha(paths['dataset'])}
    out=paths['out'];save(out/'qualification-plan.json',selection,immutable=True)
    if not execute: return {'planned':True,'model_calls':0,'selection':selection}
    storage_guard(paths);paths['cases'].mkdir(parents=True,exist_ok=True)
    tags={'django/django':'kairos-investigation-django:build003','pytest-dev/pytest':'kairos-investigation-pytest:build006'}
    images={repo:subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for repo,tag in tags.items()}
    save(out/'qualification-images.json',{'images':images,'network':'none','user':'10001:10001','memory':'1g','cpus':2,'check_seconds':120},immutable=True)
    index={r['instance_id']:r for r in rows};cases=[];receipts=[]
    for repository in REPOSITORIES:
        accepted=0
        for identifier in selection['candidate_ids'][repository]:
            if accepted>=3: break
            row=index[identifier];receipt_path=out/'qualification'/(identifier+'.json')
            if receipt_path.exists(): receipt=json.loads(receipt_path.read_text())
            else:
                workspace=None
                try:
                    entry,prefix,changed=recipes.scope(row)
                    if len(set(entry))>2 or changed>40: raise ValueError('Reference repair exceeds declared two-file/40-line source scope')
                    directory=paths['cases']/'cases'/identifier
                    storage_guard(paths,250*1024**2)
                    source,origin=recipes.prepare_source(row,directory,paths['state'])
                    script,scope=recipes.verifier(row,source)
                    (directory/'reference.patch').write_text(row['patch'])
                    (directory/'test.patch').write_text(row['test_patch'])
                    (directory/'verify.py').write_text(script)
                    case={'id':identifier,'title':row['problem_statement'].splitlines()[0],
                          'issue':row['problem_statement'],'repository':repository,'revision':row['base_commit'],
                          'source_url':'https://github.com/'+repository+'/tree/'+row['base_commit'],
                          'issue_url':'https://github.com/'+repository+'/pull/'+identifier.rsplit('-',1)[1],
                          'entry_files':entry,'approved_prefix':prefix,'split':'evaluation','qualified':True,
                          'provenance':selection['source_localization']+'; '+selection['contamination'],
                          'image':images[repository],'command':['python','/verification/verify.py'],
                          'source_digest':tree_hash(source),'reference_digest':sha(directory/'reference.patch'),
                          'verification_digest':recipes.sha(directory/'test.patch')}
                    import hashlib
                    case['verification_digest']=hashlib.sha256((row['test_patch']+script).encode()).hexdigest()
                    manifest=paths['state']/'preflight.json';save(manifest,{'version':'repository-cases-v1','cases':[case]})
                    registry=CaseRegistry(manifest,paths['cases']);workspace=Workspace(registry,case)
                    baseline=workspace.checks(120);before=recipes.summary(baseline)
                    workspace.propose(row['patch']);reference=workspace.checks(120);after=recipes.summary(reference)
                    qualified=bool(not baseline['passed'] and not baseline['environment_error'] and baseline.get('returncode') not in (124,125,126,127)
                                   and before.get('execution_complete') is True and before.get('regression_failed')
                                   and reference['passed'] and after.get('complete') is True and after.get('tests_run',0)>0)
                    receipt={'id':identifier,'qualified':qualified,'case':case,'source':origin,
                             'test_scope':scope,'baseline':baseline,'reference':reference,
                             'baseline_summary':before,'reference_summary':after,
                             'reason':None if qualified else 'Baseline behavioral failure and complete reference repair were not both reproduced'}
                except Exception as error:
                    receipt={'id':identifier,'qualified':False,'reason':type(error).__name__+': '+str(error)[:400]}
                finally:
                    if workspace: workspace.close()
                save(receipt_path,receipt,immutable=True)
            receipts.append(receipt)
            if receipt['qualified']: cases.append(receipt['case']);accepted+=1
            save(out/'qualification-progress.json',{'qualified':len(cases),'considered':len(receipts),'model_calls':0})
            print(identifier,receipt['qualified'],receipt.get('reason'),flush=True)
    counts={repo:sum(case['repository']==repo for case in cases) for repo in REPOSITORIES}
    complete=all(count==3 for count in counts.values())
    save(out/'registry.json',{'version':'repository-cases-v1','cases':cases,'selection':selection},immutable=True)
    result={'version':'qualification007-v1','qualified':len(cases),'qualified_by_repository':counts,'complete':complete,
            'model_calls':0,'receipts':[str(p.relative_to(ROOT)) for p in sorted((out/'qualification').glob('*.json'))],
            'storage':storage_guard(paths),'shortfalls':{repo:3-count for repo,count in counts.items() if count<3}}
    save(out/'qualification.json',result,immutable=True)
    return result
