"""Bounded local repair study; frozen historical outcomes are never rewritten."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time

from scripts.study007_runtime import (ROOT,finish_model,load_environment,locations,
    profile,save,sha,source_manifest,start_model,stop,storage_guard,verify_model)

PILOT_IDS=['django__django-11066','pytest-dev__pytest-6197','psf__requests-2931']


def frozen_configuration(paths,name,registry):
    from kairos_api.investigations.contracts import CONFIGURATIONS,generation_for
    return {'version':'study007-v1','profile_name':name,'profile':profile(name),
            'registry':json.loads(Path(registry).read_text()),'source_hashes':source_manifest(),
            'configurations':{strategy:{'budgets':CONFIGURATIONS[strategy],'generation':generation_for(strategy)}
                              for strategy in ('baseline-v7','loop-v7')},
            'scope':'Small Python source repairs; public cases may be contaminated; feedback visible; no broad repair or loop-superiority claim'}


def collect(directory):
    rows=[]
    for path in sorted(directory.glob('*.json')):
        value=json.loads(path.read_text())
        if isinstance(value,dict) and 'steps' in value:
            rows.append({'id':value['id'],'task_id':value['task_id'],'configuration':value['configuration'],
                         'outcome':value['outcome'],'calls':value['model_calls'],'patches':value['patch_count'],
                         'checks':value['check_count'],'repository':value['task_snapshot']['repository']})
    return {'attempts':len(rows),'verified':sum(r['outcome']=='verified_repair' for r in rows),
            'records':rows,'api_spend_usd':0}


def execute(paths,name,revision,evaluation=False):
    from kairos_api.investigations.registry import CaseRegistry
    from kairos_api.investigations.repository import InvestigationRepository
    from kairos_api.investigations.worker import InvestigationWorker
    registry_path=paths['out']/'registry.json' if evaluation else ROOT/'cases/study004.json'
    case_root=paths['cases'] if evaluation else paths['cache']
    registry=CaseRegistry(registry_path,case_root)
    configuration=frozen_configuration(paths,name,registry_path)
    if evaluation:
        lock=paths['out']/'validation-lock.json'
        if not lock.exists() or json.loads(lock.read_text())!=configuration:
            raise RuntimeError('Frozen evaluation source/profile/cases differ')
    label='validation' if evaluation else f'pilot-{name}-r{revision}'
    directory=paths['out']/label
    save(directory/'configuration.json',configuration,immutable=True)
    for relative,expected in configuration['source_hashes'].items():
        target=directory/'source'/relative
        raw=(ROOT/relative).read_bytes()
        if target.exists() and sha(target)!=expected: raise ValueError('Captured source differs')
        target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(raw)
    load_environment(paths)
    manifest=paths['state']/f'profile-{name}.json';save(manifest,profile(name),private=True)
    os.environ['KAIROS_INVESTIGATION_MODEL_MANIFEST']=str(manifest)
    cases=registry.cases() if evaluation else [registry.get(identifier) for identifier in PILOT_IDS]
    for case in cases: registry.verify(case)
    repository=InvestigationRepository(blob_root=paths['state']/'blobs',registry=registry)
    repository.initialize()
    process=log=None
    try:
        process,log=start_model(paths,name);worker=InvestigationWorker(repository)
        for case in cases:
            for strategy in ('baseline-v7','loop-v7'):
                key=f'study007:{label}:{case["id"]}:{strategy}'
                record=repository.enqueue('study007',key,case['id'],strategy)
                save(directory/(case['id']+'-'+strategy+'-command.json'),
                     {'id':record['id'],'task_id':case['id'],'configuration':strategy,'command_key':key},immutable=True)
                started=time.monotonic()
                if record['status']=='queued':
                    expected=record['id'];record=worker.run_once()
                    if not record or record['id']!=expected: raise RuntimeError('Study queue contained unexpected work')
                if record['status'] in {'queued','running'}: raise RuntimeError('Attempt active; uncertain dispatch must not be retried')
                if not record['published']: record=repository.publish(record['id'],'study007')
                save(directory/(case['id']+'-'+strategy+'.json'),record,immutable=True)
                save(directory/(case['id']+'-'+strategy+'-measurement.json'),
                     {'id':record['id'],'elapsed_seconds':time.monotonic()-started,'scope':'Command-to-terminal elapsed; resumed records are not new inference'},immutable=False)
                save(directory/'summary.json',collect(directory))
                print(json.dumps({'task':case['id'],'strategy':strategy,'outcome':record['outcome'],
                                  'calls':record['model_calls'],'checks':record['check_count']}),flush=True)
    finally:
        if process is not None: finish_model(process,log)
        repository.close()
    return collect(directory)


def report(paths):
    pilots=[]
    for directory in sorted(paths['out'].glob('pilot-*-r*')):
        summary=collect(directory)
        save(directory/'summary.json',summary)
        pilots.append({'label':directory.name,**summary})
    validation=collect(paths['out']/'validation') if (paths['out']/'validation').exists() else {'attempts':0,'verified':0,'records':[]}
    loops=[r for r in validation['records'] if r['configuration']=='loop-v7']
    repaired=[r for r in loops if r['outcome']=='verified_repair']
    result={'version':'study007-report-v1','pilots':pilots,'validation':validation,
            'quality_target':{'required_cases':6,'required_loop_repairs':3,'required_repositories':2,
              'qualified_cases':len(loops),'verified_loop_cases':len(repaired),
              'verified_repositories':sorted({r['repository'] for r in repaired}),
              'met':len(loops)==6 and len(repaired)>=3 and len({r['repository'] for r in repaired})>=2},
            'historical_results':{'build004':'0/36','build006':'0/10'},'api_spend_usd':0}
    save(paths['out']/'study-report.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['doctor','qualify','pilot','freeze','evaluate','report','stop'])
    for name in ('runtime','model-cache','dataset','case-root','environment-file'):
        parser.add_argument('--'+name)
    parser.add_argument('--profile',choices=['qwen3','coder'],default='qwen3')
    parser.add_argument('--revision',type=int,choices=[1,2],default=1)
    parser.add_argument('--execute',action='store_true',help='Execute baseline/reference qualification after freezing candidates')
    args=parser.parse_args();paths=locations(args)
    if args.action=='doctor':
        verify_model(paths,args.profile)
        if not paths['dataset'].is_file(): raise ValueError('Dataset missing; pass --dataset explicitly')
        result={'passed':True,'read_only':True,'profile':args.profile,'storage':storage_guard(paths),
                'inference_calls':0,'docker_started':False,'platform_scope':'Pinned macOS ARM64 inference only'}
    elif args.action=='qualify':
        from scripts.study007_qualification import qualify
        result=qualify(paths,args.execute)
    elif args.action=='pilot': result=execute(paths,args.profile,args.revision)
    elif args.action=='freeze':
        qualification=json.loads((paths['out']/'qualification.json').read_text())
        if qualification['model_calls']!=0: raise ValueError('Qualification contains inference')
        if not qualification['qualified']: raise ValueError('No qualified cases')
        result=frozen_configuration(paths,args.profile,paths['out']/'registry.json')
        save(paths['out']/'validation-lock.json',result,immutable=True)
        result={'frozen':True,'cases':qualification['qualified'],'qualification_target_met':qualification['complete']}
    elif args.action=='evaluate': result=execute(paths,args.profile,args.revision,True)
    elif args.action=='report': result=report(paths)
    else: result=stop(paths)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__': main()
