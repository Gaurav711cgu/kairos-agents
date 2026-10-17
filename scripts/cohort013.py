"""Freeze metadata-only, issue-disjoint candidates before qualification or inference."""
from pathlib import Path
import argparse
import hashlib
import json

from scripts.retrieval_study011 import load, canonical, issue_digest

DATASET = 'princeton-nlp/SWE-bench_Lite'
REVISION = '6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2'
REPOSITORIES = ('django/django', 'pytest-dev/pytest')
FIELDS = {'instance_id','repo','base_commit','problem_statement','version','created_at','environment_setup_commit'}


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def freeze(metadata, history, seed='013'):
    records = metadata.get('records')
    if (metadata.get('dataset') != DATASET or metadata.get('revision') != REVISION
            or not isinstance(records,list) or len(records)!=300):
        raise ValueError('Use the pinned 300-row sanitized Lite test metadata')
    identifiers=set()
    for row in records:
        if (not isinstance(row,dict) or set(row)!=FIELDS
                or any(not isinstance(row[key],str) for key in FIELDS)
                or not row['problem_statement'].strip()
                or row['instance_id'] in identifiers
                or len(row['base_commit'])!=40
                or any(c not in '0123456789abcdef' for c in row['base_commit'])):
            raise ValueError('Invalid or duplicated metadata row; reference/test columns are prohibited')
        identifiers.add(row['instance_id'])
    exposed = {row['instance_id'] for row in history['exposures']}
    digests = set(history['exposed_issue_digests'])
    candidates=[]; exclusions=[]; counts={}; seen=set()
    for row in sorted(records,key=lambda row:row['instance_id']):
        if row['repo'] not in REPOSITORIES:
            continue
        digest=issue_digest(row['problem_statement'])
        reason=('Prior task exposure' if row['instance_id'] in exposed else
                'Prior issue-text exposure' if digest in digests else
                'Duplicate issue text in the candidate pool' if digest in seen else None)
        if reason:
            exclusions.append({'instance_id':row['instance_id'],'reason':reason})
        else:
            candidates.append(row);seen.add(digest)
    selected=[]
    for repo in REPOSITORIES:
        pool=sorted((row for row in candidates if row['repo']==repo),
            key=lambda row:hashlib.sha256((str(seed)+'\0'+row['instance_id']).encode()).hexdigest())
        counts[repo]=len(pool)
        if len(pool)<12:
            raise ValueError('Insufficient eligible metadata; do not silently replace repositories or cases')
        selected += [{'instance_id':row['instance_id'],'repository':repo,'base_commit':row['base_commit'],
                      'issue':row['problem_statement'],'split':'development' if i<4 else 'holdout'}
                     for i,row in enumerate(pool[:12])]
    return {'version':'cohort013-metadata-v1','dataset':DATASET,'revision':REVISION,'split':'test',
        'seed':str(seed),'metadata_sha256':sha(metadata),'history_sha256':sha(history),
        'candidate_counts_by_repository':counts,'candidates':selected,'exclusions':exclusions,
        'selection':'Per repository, SHA256(seed + NUL + instance_id) ascending; first four development, next eight holdout',
        'qualification':{'performed':False,'qualified':0,'source_scope':'unknown','baseline_failure':'unknown','reference_success':'unknown'},
        'model_calls':0,'scope':'Frozen candidate metadata, not qualified cases or a repair score; public pretraining exposure unknown'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('freeze','verify'))
    for name in ('metadata','history','cohort'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--seed',default='013')
    args=parser.parse_args(argv)
    try:
        value=freeze(load(args.metadata),load(args.history),args.seed)
        if args.operation=='verify':
            if load(args.cohort)!=value:
                raise ValueError('Frozen cohort differs; preserve it and create a new version before inference')
        else:
            with args.cohort.open('x') as output:
                output.write(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
    except (ValueError,OSError,KeyError,TypeError) as error:
        parser.exit(1,'Cohort refused: '+str(error)+'\n')
    print(json.dumps({'passed':True,'cases':len(value['candidates']),'qualified':0,'model_calls':0}))


if __name__=='__main__':
    main()
