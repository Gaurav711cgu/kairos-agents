"""Extend the sealed historical exposure audit with declared public013 evidence."""
from collections import Counter
from pathlib import Path
import argparse
import json

from scripts.retrieval_study011 import exposure_inventory, issue_digest, load, fingerprint
from kairos_api.model_runtime import digest


def audit(root):
    root=Path(root).resolve(strict=True)
    result=exposure_inventory(root)
    ledger={row['instance_id']:set(row['reasons']) for row in result['exposures']}
    issues=set(result['exposed_issue_digests'])
    prior=load(root/'evidence/evaluation013/cohort/prior-exposures.json')
    cohort=load(root/'evidence/evaluation013/cohort/cohort.json')
    pilot=load(root/'evidence/evaluation013/pilot/bundle.json')
    proposals=load(root/'evidence/evaluation013/cohort/proposals.json')
    for row in prior['exposures']:
        ledger.setdefault(row['instance_id'],set()).update(row.get('reasons',['Prior qualification plan selection']))
    for row in cohort['candidates']:
        ledger.setdefault(row['instance_id'],set()).add('Frozen013 metadata candidate; reserved from training')
        issues.add(issue_digest(row['issue']))
    for identifier in proposals['additional_proposed_shortlist_ids']:
        ledger.setdefault(identifier,set()).add('Additional proposed013 qualification metadata; reserved from training')
    ledger.setdefault(pilot['task_id'],set()).add('Exposed013 development pilot')
    issues.add(issue_digest(pilot['task_snapshot']['issue']))
    original=result['audit']
    counts=Counter(original['record_outcomes']);counts[pilot['outcome']]+=1
    patches=dict(original['verified_patch_counts_by_task'])
    if pilot['outcome']=='verified_repair':
        target={digest(step['result']['body']['patch']) for step in pilot['steps']
                if step['name']=='propose_patch' and step.get('result') and step['result']['body'].get('patch')}
        # This pilot's pytest case had no earlier verified trajectory. Refuse
        # reuse of this narrow counting rule if a later export changes that fact.
        if pilot['task_id'] in patches:
            raise ValueError('Positive overlap requires exact cross-release patch deduplication')
        patches[pilot['task_id']]=len(target)
    result['version']='training-exposure013-v1'
    result['scope']='Legacy public collection plus explicit013 pilot and frozen metadata candidates; not a licensed training corpus'
    result['audit']={**original,'public_records':original['public_records']+1,
        'record_outcomes':dict(sorted(counts.items())),
        'record_model_calls':original['record_model_calls']+pilot['model_calls'],
        'verified_trajectories':original['verified_trajectories']+int(pilot['outcome']=='verified_repair'),
        'verified_unique_tasks':len(patches),'verified_unique_rendered_patches':sum(patches.values()),
        'verified_patch_counts_by_task':patches,'training_data_ready':False}
    result['exposures']=[{'instance_id':key,'reasons':sorted(value)} for key,value in sorted(ledger.items())]
    result['exposed_task_count']=len(ledger);result['exposed_issue_digests']=sorted(issues)
    result['inputs']={name:fingerprint(root/name) for name in (
        'evidence/evaluation013/cohort/prior-exposures.json','evidence/evaluation013/cohort/cohort.json',
        'evidence/evaluation013/cohort/proposals.json',
        'evidence/evaluation013/pilot/bundle.json')}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=audit(args.root);raw=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output.exists():
        if args.output.read_text()!=raw:raise ValueError('Preserve changed audits under a new version')
    else:
        with args.output.open('x') as output:output.write(raw)
    print(json.dumps({'positive_tasks':result['audit']['verified_unique_tasks'],
                      'exposed_tasks':result['exposed_task_count'],'training_data_ready':False}))


if __name__=='__main__':main()
