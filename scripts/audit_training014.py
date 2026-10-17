"""Refresh repair evidence counts without admitting held-out results for training."""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib

from scripts.audit_training013 import audit as prior_audit
from scripts.retrieval_study011 import load, save, fingerprint, issue_digest
from kairos_api.model_runtime import digest

ARMS = {'baseline', 'loop', 'drafts'}


def matched_verified_patches(record):
    """Return only proposed bytes bound to captured passing independent checks."""
    proposed = {}
    checks = set()
    for step in record.get('steps', []):
        body = (step.get('result') or {}).get('body', {})
        if step.get('name') == 'propose_patch' and not body.get('error') and isinstance(body.get('patch'), str):
            patch = body['patch']
            proposed[digest(patch)] = hashlib.sha256(patch.encode()).hexdigest()
        if step.get('name') == 'run_checks' and body.get('passed') is True:
            checks.add(body.get('patch_digest'))
    winners = {proposed[key] for key in checks if key in proposed}
    if record.get('outcome') == 'verified_repair' and not winners:
        raise ValueError('Verified record lacks a patch bound to a captured passing check')
    return winners if record.get('outcome') == 'verified_repair' else set()


def audit(root):
    root = Path(root).resolve(strict=True)
    prior = prior_audit(root)
    report_path = root/'evidence/measurement014/comparison/report.json'
    report = load(report_path)
    frozen = load(root/'evidence/evaluation013/cohort/cohort.json')['candidates']
    cases = report.get('cases', [])
    if report.get('execution_complete') is not True or [c['instance_id'] for c in cases] != [c['instance_id'] for c in frozen]:
        raise ValueError('Complete original frozen cohort is required')
    ledger = {row['instance_id']: set(row['reasons']) for row in prior['exposures']}
    issues = set(prior['exposed_issue_digests'])
    records = []; patches = defaultdict(set)
    for case, original in zip(cases, frozen):
        if case.get('split') != original['split']:
            raise ValueError('Frozen split differs')
        identifier = case['instance_id']
        ledger.setdefault(identifier, set()).add('Reserved014 cohort: excluded from coding-adapter training and selection')
        issues.add(issue_digest(original['issue']))
        arms = case.get('arms', {})
        if set(arms) != (ARMS if case.get('qualified') is True else set()):
            raise ValueError('Missing or unexpected comparison arms')
        for arm, attempt in arms.items():
            path = root/'evidence/measurement014/comparison/records'/identifier/arm/'bundle.json'
            if fingerprint(path)['sha256'] != attempt['record_sha256']:
                raise ValueError('Captured record hash differs')
            record = load(path)
            if record.get('task_id') != identifier or record.get('outcome') != attempt['outcome']:
                raise ValueError('Captured record identity/outcome differs')
            if attempt.get('verified') != (record.get('outcome') == 'verified_repair'):
                raise ValueError('Verified outcome differs')
            records.append(record)
            patches[identifier].update(matched_verified_patches(record))
    if len(records) != report['attempts']:
        raise ValueError('Attempt count differs')
    old = prior['audit']
    historical = old['verified_patch_counts_by_task']
    fresh = {task: len(value) for task, value in patches.items() if value}
    if set(historical) & set(fresh):
        raise ValueError('Historical overlap requires exact cross-release patch deduplication')
    counts = Counter(old['record_outcomes']); counts.update(r['outcome'] for r in records)
    combined_patches = {**historical, **fresh}
    return {
        'version': 'training-exposure014-v1',
        'scope': 'Public repair evidence and exposure inventory; not a licensed or admitted coding-model training corpus',
        'prior_audit': old,
        'audit': {
            'public_records': old['public_records'] + len(records),
            'record_outcomes': dict(sorted(counts.items())),
            'record_model_calls': old['record_model_calls'] + sum(r['model_calls'] for r in records),
            'verified_trajectories': old['verified_trajectories'] + sum(r['outcome']=='verified_repair' for r in records),
            'verified_unique_tasks': len(combined_patches),
            'verified_unique_rendered_patches': sum(combined_patches.values()),
            'verified_patch_counts_by_task': dict(sorted(combined_patches.items())),
            'new_comparison_records': len(records),
            'new_verified_tasks': len(fresh),
            'new_training_eligible_tasks': 0,
            'training_data_ready': False,
            'training_use': 'All24 current cohort IDs and related issue families remain excluded from training and selection. Additional licensed, independently verified data is required. Task IDs do not prove independent issue families.',
        },
        'exposed_task_count': len(ledger),
        'exposures': [{'instance_id': task, 'reasons': sorted(reasons)} for task, reasons in sorted(ledger.items())],
        'exposed_issue_digests': sorted(issues),
        'reserved014_ids': [c['instance_id'] for c in frozen],
        'inputs': {str(report_path.relative_to(root)): fingerprint(report_path)},
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.root);save(args.output,result)
    import json
    print(json.dumps(result['audit'],indent=2))


if __name__=='__main__':main()
