"""Package genuine follow-up captures and their separate development/validation totals."""
from __future__ import annotations
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from kairos_api.model_runtime import canonical

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/build006'


def fingerprint(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def main():
    records=[]
    for directory in sorted(OUT.glob('pilot-*'))+[OUT/'validation']:
        for path in sorted(directory.glob('*.json')):
            value=json.loads(path.read_text())
            if isinstance(value,dict) and 'steps' in value:
                if value['status'] in {'queued','running'}:raise RuntimeError('Follow-up still active; cannot publish complete totals')
                records.append((path,value))
    if len({r['id'] for _,r in records})!=len(records):raise ValueError('Duplicate follow-up record')
    destination=ROOT/'dashboard/evidence';manifest_path=destination/'manifest.json';manifest=json.loads(manifest_path.read_text())
    original_ids=set()
    for name in ('investigation-cohort.json','study004-cohort.json'):
        original_ids.update(json.loads((ROOT/'dashboard/lib'/name).read_text())['ids'])
    if len(original_ids)!=48 or not original_ids.issubset(manifest['records']):raise ValueError('Historical cohort missing')
    blobs=ROOT/'.runtime/study006/blobs'
    def add_blob(key,data):
        if hashlib.sha256(data).hexdigest()!=key:raise ValueError('Captured bytes changed: '+key)
        target=destination/'blobs'/key
        if target.exists() and target.read_bytes()!=data:raise ValueError('Existing public object differs')
        if not target.exists():target.write_bytes(data)
        manifest['blobs'][key]={'path':'blobs/'+key,**fingerprint(target)}
    for path,record in records:
        if not record['published'] or not record['integrity']['verified']:raise ValueError('Only integrity-verified published captures are packaged')
        for artifact in record['artifacts']:add_blob(artifact['sha256'],(blobs/artifact['sha256']).read_bytes())
        for step in record['steps']:
            for kind in ('request','result'):
                capture=step[kind]
                if capture:add_blob(capture['sha256'],(blobs/capture['sha256']).read_bytes())
        version=record.get('registry_version','repository-cases-v1')
        add_blob(record['task_digest'],canonical({'case':record['task_snapshot'],'registry_version':version}).encode())
        add_blob(record['config_digest'],canonical(record['config_snapshot']).encode())
        target=destination/'records'/(record['id']+'.json');target.write_bytes(path.read_bytes())
        manifest['records'][record['id']]={'path':'records/'+target.name,**fingerprint(target),'task_snapshot_blob':record['task_digest'],'config_snapshot_blob':record['config_digest'],'registry_version':version}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    def summarize(values):
        counters=Counter(r['outcome'] for r in values);tokens=0;elapsed=0
        for r in values:
            elapsed+=(datetime.fromisoformat(r['updated_at'])-datetime.fromisoformat(r['started_at'])).total_seconds()
            for step in r['steps']:
                if step['kind']=='model' and step['result']:tokens+=step['result']['body'].get('usage',{}).get('total_tokens',0)
        return {'attempts':len(values),'verified':counters['verified_repair'],'outcomes':dict(counters),'calls':sum(r['model_calls'] for r in values),'checks':sum(r['check_count'] for r in values),'tokens':tokens,'elapsed_seconds':round(elapsed,3)}
    validation=[r for p,r in records if p.parent.name=='validation']
    cohort={'complete':len(validation)==10,'ids':[r['id'] for r in validation],'task_by_id':{r['id']:r['task_id'] for r in validation},'cases':5,'strategies':2,
            'featured_id':next((r['id'] for p,r in records if p.parent.name=='pilot-qwen3-r1' and r['configuration']=='baseline-v5' and r['outcome']=='verified_repair'),None)}
    result={'complete':cohort['complete'],'historical_study':{'verified':0,'attempts':36,'preserved':True},'qualification':{'target':6,'actual':5,'target_met':False,'excluded':'The remaining Requests regression did not reproduce on Python 3; it requires Python 2.'},
            'validation':{s:summarize([r for r in validation if r['configuration']==s]) for s in ('baseline-v5','loop-v5')},
            'development':{directory.name:summarize([r for p,r in records if p.parent==directory]) for directory in sorted(OUT.glob('pilot-*'))},
            'attempts':[{'id':r['id'],'task_id':r['task_id'],'configuration':r['configuration'],'outcome':r['outcome'],'split':'validation' if p.parent.name=='validation' else 'development'} for p,r in records],
            'limits':['Frozen v5 validation remains 0/10; no replacement or retuning.','Development demonstrations are not fresh validation performance.','V6 is a separately recorded reasoning experiment, not a validation rerun.','Token totals contain captured usage only. Unknown dispatch consumption is unavailable, not zero.','Public historical cases may be contaminated; source entry files were human-localized.','No production-scale, leaderboard or loop-superiority claim.']}
    (ROOT/'dashboard/lib/followup006-cohort.json').write_text(json.dumps(cohort,indent=2)+'\n')
    (ROOT/'dashboard/lib/followup006-results.json').write_text(json.dumps(result,indent=2)+'\n')
    public=ROOT/'dashboard/public/follow-up';public.mkdir(parents=True,exist_ok=True);(public/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'presentation.json').write_text(json.dumps({'passed':True,'new_captures':len(records),'records':len(manifest['records']),'blobs':len(manifest['blobs']),'original_records_preserved':len(original_ids),'manifest':fingerprint(manifest_path)},indent=2)+'\n')
    print(json.dumps({'records':len(manifest['records']),'new':len(records),'validation':result['validation']}))


if __name__=='__main__':main()
