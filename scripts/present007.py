"""Publish every genuine build007 capture without rewriting historical bytes."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from kairos_api.model_runtime import canonical
from scripts.study007_runtime import ROOT,save,sha
from scripts.reviewer_evidence import validate_package


def summarize(records):
    outcomes=Counter(record['outcome'] for record in records)
    tokens=0;unknown_usage=0;seconds=0
    for record in records:
        if record.get('started_at') and record.get('updated_at'):
            seconds+=(datetime.fromisoformat(record['updated_at'])-datetime.fromisoformat(record['started_at'])).total_seconds()
        for step in record['steps']:
            if step['kind']!='model':continue
            if not step['result']:unknown_usage+=1;continue
            usage=step['result']['body'].get('usage')
            if not isinstance(usage,dict):unknown_usage+=1;continue
            tokens+=usage.get('total_tokens',usage.get('prompt_tokens',0)+usage.get('completion_tokens',0))
    return {'attempts':len(records),'verified':outcomes['verified_repair'],'outcomes':dict(outcomes),
            'calls':sum(r['model_calls'] for r in records),'checks':sum(r['check_count'] for r in records),
            'tokens':tokens,'uncaptured_usage_dispatches':unknown_usage,'elapsed_seconds':round(seconds,3)}


def main():
    out=ROOT/'evidence/build007';destination=ROOT/'dashboard/evidence'
    manifest_path=destination/'manifest.json';manifest=json.loads(manifest_path.read_text())
    old_records=dict(manifest['records']);old_blobs=dict(manifest['blobs'])
    captures=[]
    for directory in sorted(out.glob('pilot-*'))+[out/'validation']:
        for path in sorted(directory.glob('*.json')):
            record=json.loads(path.read_text())
            if isinstance(record,dict) and 'steps' in record:
                if record['status'] in {'queued','running'}:raise ValueError('Attempt active; cannot publish final presentation')
                captures.append((path,record))
    if len({r['id'] for _,r in captures})!=len(captures):raise ValueError('Duplicate terminal capture')
    def add_blob(key,raw):
        if hashlib.sha256(raw).hexdigest()!=key:raise ValueError('Original captured blob differs')
        target=destination/'blobs'/key
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Existing historical blob differs')
        if not target.exists():target.write_bytes(raw)
        manifest['blobs'][key]={'path':'blobs/'+key,'sha256':key,'bytes':len(raw)}
    for path,record in captures:
        if not record['published'] or not record['integrity']['verified']:raise ValueError('Private or unverified capture')
        for artifact in record['artifacts']:
            add_blob(artifact['sha256'],(ROOT/'.runtime/study007/blobs'/artifact['sha256']).read_bytes())
        for step in record['steps']:
            for kind in ('request','result'):
                capture=step[kind]
                if capture:add_blob(capture['sha256'],(ROOT/'.runtime/study007/blobs'/capture['sha256']).read_bytes())
        version=record.get('registry_version','repository-cases-v1')
        add_blob(record['task_digest'],canonical({'case':record['task_snapshot'],'registry_version':version}).encode())
        add_blob(record['config_digest'],canonical(record['config_snapshot']).encode())
        target=destination/'records'/(record['id']+'.json')
        if target.exists() and target.read_bytes()!=path.read_bytes():raise ValueError('Existing public record differs')
        target.write_bytes(path.read_bytes())
        manifest['records'][record['id']]={'path':'records/'+target.name,'sha256':sha(target),'bytes':target.stat().st_size,
           'task_snapshot_blob':record['task_digest'],'config_snapshot_blob':record['config_digest'],'registry_version':version}
    save(manifest_path,manifest)
    records,blobs=validate_package(destination)
    assert all(manifest['records'][key]==value for key,value in old_records.items())
    assert all(manifest['blobs'][key]==value for key,value in old_blobs.items())
    validation=[r for p,r in captures if p.parent.name=='validation']
    selected=json.loads((out/'profile-selection.json').read_text())
    qualification=json.loads((out/'qualification.json').read_text())
    featured=next((r['id'] for p,r in captures if r['outcome']=='verified_repair' and p.parent.name=='validation'),None)
    if not featured:featured=next((r['id'] for p,r in captures if r['outcome']=='verified_repair' and p.parent.name==selected['selected_development_configuration']),None)
    cohort={'ids':[r['id'] for r in validation],'cases':qualification['qualified'],'complete':len(validation)==2*qualification['qualified'],
            'featured_id':featured,'all_ids':[r['id'] for _,r in captures]}
    result={'complete':cohort['complete'],'qualification':qualification,'selection':selected,
            'validation':{s:summarize([r for r in validation if r['configuration']==s]) for s in ('baseline-v7','loop-v7')},
            'development':{directory.name:summarize([r for p,r in captures if p.parent==directory]) for directory in sorted(out.glob('pilot-*'))},
            'attempts':[{'id':r['id'],'task_id':r['task_id'],'configuration':r['configuration'],'outcome':r['outcome'],
                         'split':'evaluation' if p.parent.name=='validation' else 'development','cohort':p.parent.name} for p,r in captures],
            'historical_results':{'build004':'0/36','build006':'0/10'},
            'limits':['Small curated source-repair cohort; public cases may be contaminated.','Entry paths are maintainer-localized; reference text remains outside model tools.',
              'Checks expose diagnostics and share candidate Python environment; hostile test-forgery resistance is unproven.',
              'All pre-dispatch environment failures and rejected development revisions are retained.','Unavailable consumption is not zero.','No broad repair, loop superiority, staff-role or production-impact claim.']}
    save(ROOT/'dashboard/lib/study007-cohort.json',cohort)
    save(ROOT/'dashboard/lib/study007-results.json',result)
    save(ROOT/'dashboard/public/advancement/results.json',result)
    save(out/'presentation.json',{'passed':True,'new_records':len(captures),'records':len(records),'blobs':len(blobs),
         'historical_records_preserved':len(old_records),'historical_blobs_preserved':len(old_blobs)})
    print(json.dumps({'records':len(records),'new':len(captures),'validation':result['validation']}))


if __name__=='__main__':main()
