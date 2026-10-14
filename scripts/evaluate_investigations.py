"""Frozen descriptive comparison; actual local model attempts, never reference patches."""
import argparse
import json
import os
from pathlib import Path
import time
from kairos_api.investigations.contracts import CONFIGURATIONS, GENERATION
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.model_runtime import digest

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['development','validation','all'],default='development')
    args=parser.parse_args()
    for line in (ROOT/'.env.kairos.local').read_text().splitlines():
        if line and not line.startswith('#'):
            key,value=line.split('=',1);os.environ[key]=value
    repository=InvestigationRepository();repository.initialize()
    directory=ROOT/'evidence/build003';directory.mkdir(parents=True,exist_ok=True)
    frozen={'registry':repository.registry.manifest(),'configurations':CONFIGURATIONS,'generation':GENERATION,
            'model_manifest_digest':repository._model_digest(),
            'source_hashes':{p.name:__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'kairos_api/investigations').glob('*.py'))}}
    lock=directory/'evaluation-lock-v3.json'
    if lock.exists() and json.loads(lock.read_text())!=frozen:
        raise RuntimeError('Evaluation configuration changed; preserve old attempts and use a new version')
    lock.write_text(json.dumps(frozen,indent=2)+'\n')
    worker=InvestigationWorker(repository)
    attempts=[]
    ledger=directory/'attempts.json'
    if ledger.exists(): attempts=json.loads(ledger.read_text())
    cases=[c for c in frozen['registry']['cases'] if args.split=='all' or c['split']==args.split]
    for case in cases:
        for configuration in ['baseline-v3','loop-v3']:
            key='real-cases-v3:'+case['id']+':'+configuration
            record=repository.enqueue('local-review',key,case['id'],configuration)
            started=time.monotonic()
            if record['status']=='queued':
                result=worker.run_once()
                if not result or result['id']!=record['id']:
                    raise RuntimeError('Another queued investigation ran first; inspect queue before evaluation')
                record=result
            if record['status'] in {'queued','running'}: raise RuntimeError('Attempt still active')
            record=repository.publish(record['id'],'local-review')
            target=directory/(case['id']+'-'+configuration+'.json');target.write_text(json.dumps(record,indent=2)+'\n')
            response_steps=[s['result']['body'] for s in record['steps'] if s['kind']=='model' and s['state']=='captured']
            usage={'prompt_tokens':sum(r.get('usage',{}).get('prompt_tokens',0) for r in response_steps),
                   'completion_tokens':sum(r.get('usage',{}).get('completion_tokens',0) for r in response_steps)}
            summary={'id':record['id'],'task_id':case['id'],'split':case['split'],'configuration':configuration,
                     'status':record['status'],'outcome':record['outcome'],'model_calls':record['model_calls'],
                     'check_count':record['check_count'],'patch_count':record['patch_count'],
                     'started_at':record['started_at'],'finished_at':record['updated_at'],'tokens':usage,
                     'evidence_file':str(target.relative_to(ROOT))}
            attempts=[a for a in attempts if a['id']!=record['id']]+[summary]
            ledger.write_text(json.dumps(attempts,indent=2)+'\n')
            print(json.dumps(summary),flush=True)
    print('All requested attempts captured; no statistical superiority claim.',flush=True)

if __name__=='__main__': main()
