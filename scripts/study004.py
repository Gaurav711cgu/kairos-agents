"""Recorded profile pilots, bounded development and one frozen evaluation.
No evaluation is allowed until all 18 cases qualify. Existing attempts never rerun.
"""
import argparse,hashlib,json,os,random
from datetime import datetime
from pathlib import Path
from kairos_api.investigations.contracts import CONFIGURATIONS,GENERATION
from kairos_api.investigations.registry import CaseRegistry
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.model_runtime import digest
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/build004';STRATEGIES=['baseline-v4','loop-v4','drafts-v4']
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def environment():
 for line in (ROOT/'.env.kairos.local').read_text().splitlines():
  if line and not line.startswith('#'):
   key,value=line.split('=',1);os.environ[key]=value

def frozen(profile):
 return {'protocol':'study004-v1','registry':json.loads((ROOT/'cases/study004.json').read_text()),'configurations':{k:CONFIGURATIONS[k] for k in STRATEGIES},'generation':GENERATION,'profile_manifest':json.loads(profile.read_text()),'profile_digest':digest(json.loads(profile.read_text())),
  'source_hashes':{name:hashlib.sha256((ROOT/'kairos_api/investigations'/name).read_bytes()).hexdigest() for name in ['worker.py','model.py','contracts.py','patches.py','sandbox.py']},'draft_seed_policy':'73 + draft index; all six before verification','development_revision_limit':3,'evaluation_repetitions':1}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['pilot','development','freeze','evaluation','report']);parser.add_argument('--profile',type=Path,required=True);parser.add_argument('--label',required=True);parser.add_argument('--revision',type=int,default=1);parser.add_argument('--case');parser.add_argument('--strategy',choices=STRATEGIES);args=parser.parse_args();environment()
 if not args.label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.label):raise ValueError('Use a simple release label')
 profile=args.profile.resolve();os.environ['KAIROS_INVESTIGATION_MODEL_MANIFEST']=str(profile)
 plan=frozen(profile);directory=OUT/('study-'+args.label);directory.mkdir(exist_ok=True)
 registry=CaseRegistry(ROOT/'cases/study004.json');cases=registry.cases();lock=directory/'evaluation-lock.json'
 if args.phase=='freeze':
  if not plan['registry']['selection']['complete']:raise RuntimeError('Qualification incomplete; evaluation remains locked')
  if lock.exists() and json.loads(lock.read_text())!=plan:raise RuntimeError('Existing evaluation lock differs; preserve it')
  write(lock,plan);print('Evaluation configuration frozen. No model execution.');return
 if args.phase=='report':return report(directory,plan)
 if args.phase=='evaluation':
  if args.case:raise RuntimeError('Evaluation cannot select individual cases')
  if not lock.exists() or json.loads(lock.read_text())!=plan:raise RuntimeError('Evaluation source/configuration differs from frozen lock')
  if not plan['registry']['selection']['complete']:raise RuntimeError('Qualification incomplete')
  chosen=[c for c in cases if c['split']=='evaluation'];configurations=STRATEGIES;run_label='evaluation'
 elif args.phase=='development':
  if lock.exists():raise RuntimeError('Development is closed after evaluation freeze')
  if not 1<=args.revision<=3:raise RuntimeError('At most three recorded development revisions')
  revisions=OUT/'development-revisions.json'
  recorded=json.loads(revisions.read_text()) if revisions.exists() else {}
  fingerprint=plan['source_hashes']
  key=str(args.revision)
  if key in recorded and recorded[key]['source_hashes']!=fingerprint:raise RuntimeError('Global development revision source changed')
  if key not in recorded:
   recorded[key]={'source_hashes':fingerprint,'reason':'Correct source-line representation, baseline grammar, syntax validation, complete verification and database outage backoff' if args.revision==1 else 'Recorded bounded revision'}
   write(revisions,recorded)
  chosen=[c for c in cases if c['split']=='development'];configurations=STRATEGIES;run_label='development-'+str(args.revision)
 else:
  if lock.exists():raise RuntimeError('Model-profile pilot is closed after evaluation freeze')
  chosen=[c for c in cases if c['split']=='development'];configurations=['baseline-v4'];run_label='profile-pilot'
 if args.strategy:
  if args.phase=='evaluation':raise RuntimeError('Evaluation always runs all three frozen strategies')
  configurations=[args.strategy]
 if args.case:chosen=[c for c in chosen if c['id']==args.case]
 if not chosen:raise RuntimeError('No matching development/evaluation case')
 run=directory/run_label;run.mkdir(exist_ok=True);manifest=run/'configuration.json'
 if manifest.exists() and json.loads(manifest.read_text())!=plan:raise RuntimeError('Recorded revision changed; use the next allowed revision')
 write(manifest,plan)
 source=run/'source';source.mkdir(exist_ok=True)
 for name,expected in plan['source_hashes'].items():
  target=source/name;content=(ROOT/'kairos_api/investigations'/name).read_bytes()
  if hashlib.sha256(content).hexdigest()!=expected:raise RuntimeError('Source changed during run setup')
  if target.exists() and target.read_bytes()!=content:raise RuntimeError('Archived revision differs')
  target.write_bytes(content)
 repo=InvestigationRepository(registry=registry);repo.initialize();worker=InvestigationWorker(repo)
 attempts=json.loads((run/'attempts.json').read_text()) if (run/'attempts.json').exists() else []
 for case in chosen:
  for configuration in configurations:
   key='study004:'+args.label+':'+run_label+':'+case['id']+':'+configuration
   record=repo.enqueue('local-review',key,case['id'],configuration)
   if record['status']=='queued':
    value=worker.run_once()
    if not value or value['id']!=record['id']:raise RuntimeError('Queue order differs; inspect existing jobs before continuing')
    record=value
   if record['status'] in ['queued','running']:raise RuntimeError('Attempt still active; do not create a replacement')
   record=repo.publish(record['id'],'local-review');path=run/(case['id']+'-'+configuration+'.json');write(path,record)
   responses=[s['result']['body'] for s in record['steps'] if s['kind']=='model' and s['state']=='captured']
   summary={k:record[k] for k in ['id','task_id','configuration','status','outcome','model_calls','patch_count','check_count','started_at','updated_at']}
   summary.update(elapsed_seconds=max(0,(datetime.fromisoformat(record['updated_at'])-datetime.fromisoformat(record['started_at'])).total_seconds()) if record['started_at'] else None,repository=case['repository'],split=case['split'],tokens=sum(r.get('usage',{}).get('total_tokens',r.get('usage',{}).get('prompt_tokens',0)+r.get('usage',{}).get('completion_tokens',0)) for r in responses),api_spend_usd=0,evidence_file=str(path.relative_to(ROOT)),profile_digest=plan['profile_digest'])
   recoveries=OUT.glob('infrastructure/evaluation-*-recovery.json')
   recovery=next((path for path in recoveries if json.loads(path.read_text()).get('record_id')==record['id']),None)
   if recovery:
    summary.update(elapsed_seconds=None,elapsed_complete=False,elapsed_note='Interrupted infrastructure; stored update time predates recovery. See '+recovery.name+'.')
   attempts=[a for a in attempts if a['id']!=record['id']]+[summary];write(run/'attempts.json',attempts);print(json.dumps(summary),flush=True)
 repo.close()

def report(directory,plan):
 path=directory/'evaluation/attempts.json';attempts=json.loads(path.read_text()) if path.exists() else []
 by_case={}
 for attempt in attempts:by_case.setdefault(attempt['task_id'],{})[attempt['configuration']]=attempt
 complete=len(by_case)==12 and all(set(value)==set(STRATEGIES) for value in by_case.values())
 report={'elapsed_scope':'Captured completed durations only; interrupted attempts with incomplete timing are excluded from duration sums.', 'incomplete_duration_attempts':sum(a.get('elapsed_complete') is False for a in attempts),'complete':complete,'scope':'Small curated historical sample; descriptive results. Bootstrap intervals describe resampling of these cases, not general repair competence. No leaderboard claim.','attempts':attempts,'strategies':{},'paired_differences':[]}
 for strategy in STRATEGIES:
  group=[a for a in attempts if a['configuration']==strategy]
  report['strategies'][strategy]={'attempts':len(group),'verified':sum(a['outcome']=='verified_repair' for a in group),'calls':sum(a['model_calls'] for a in group),'tokens':sum(a['tokens'] for a in group),'elapsed_seconds':sum(a.get('elapsed_seconds') or 0 for a in group),'repositories':{repository:{'attempts':len(rows:=[a for a in group if a['repository']==repository]),'verified':sum(a['outcome']=='verified_repair' for a in rows),'tokens':sum(a['tokens'] for a in rows),'elapsed_seconds':sum(a.get('elapsed_seconds') or 0 for a in rows)} for repository in sorted({a['repository'] for a in group})},'outcomes':{outcome:sum(a['outcome']==outcome for a in group) for outcome in sorted({a['outcome'] for a in group})}}
 if complete:
  rng=random.Random(741903)
  for left,right in [('loop-v4','baseline-v4'),('drafts-v4','baseline-v4'),('loop-v4','drafts-v4')]:
   strata={repo:[int(v[left]['outcome']=='verified_repair')-int(v[right]['outcome']=='verified_repair') for v in by_case.values() if v[left]['repository']==repo] for repo in sorted({v[left]['repository'] for v in by_case.values()})}
   differences=[x for values in strata.values() for x in values];samples=[]
   for _ in range(10000):samples.append(sum(sum(rng.choices(values,k=len(values))) for values in strata.values())/len(differences))
   samples.sort();report['paired_differences'].append({'left':left,'right':right,'difference':sum(differences)/len(differences),'interval_95':[samples[249],samples[9749]],'method':'Paired bootstrap, stratified by repository; fixed sample only','n_pairs':len(differences),'discordant_pairs':sum(value!=0 for value in differences),'uncertainty_note':'A degenerate interval when all observed pairs agree does not establish equivalence or safe future performance. The suite is curated, not a random population sample.'})
  repaired=[v for v in by_case.values() if any(a['outcome']=='verified_repair' for a in v.values())]
  report['declared_quality_target']={'target_cases':6,'target_repositories':2,'actual_cases':len(repaired),'actual_repositories':len({next(iter(v.values()))['repository'] for v in repaired}),'met':len(repaired)>=6 and len({next(iter(v.values()))['repository'] for v in repaired})>=2}
 write(directory/'comparison.json',report);print(json.dumps({k:v for k,v in report.items() if k!='attempts'},indent=2))
if __name__=='__main__':main()
