"""Export complete captured study outcomes; never dispatch, select or repair work."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import math
import random
import statistics

from scripts.batch_comparison014 import checked_result, load
from scripts.comparison014 import ARMS, sha
from kairos_api.model_runtime import canonical


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def paired_interval(rows, left, right, *, seed=1401402, count=2000):
    deltas = [float(r['arms'][left]['verified']) - float(r['arms'][right]['verified']) for r in rows]
    if not deltas: return {'pairs': 0, 'difference': None, 'interval95': None}
    randomizer = random.Random(seed)
    draws = sorted(statistics.fmean(randomizer.choices(deltas, k=len(deltas))) for _ in range(count))
    return {'pairs':len(deltas),'difference':statistics.fmean(deltas),'interval95':[draws[int(.025*(count-1))],draws[int(.975*(count-1))]],
        'method':'Descriptive paired issue bootstrap; percentile, 2000 replicates', 'seed':seed,
        'scope':'Small curated sample; conditional intervals do not establish broad superiority or a release safety gate'}


def usage_totals(usages, captured, dispatched):
    """Sum observed integer counters; missing counters never imply complete usage."""
    keys = ['prompt_tokens', 'completion_tokens']
    totals = {key: 0 for key in keys}
    complete = captured == dispatched and len(usages) == captured
    for usage in usages:
        for key in keys:
            value = usage.get(key) if isinstance(usage, dict) else None
            if type(value) is int and value >= 0:
                totals[key] += value
            else:
                complete = False
    return totals, complete


def summarize(rows):
    return {'cases':len(rows),'verified':sum(r['verified'] for r in rows),
        'outcomes':dict(Counter(r['outcome'] for r in rows)),
        'calls':sum(r['calls'] for r in rows),'checks_admitted':sum(r['checks'] for r in rows),'checks_captured':sum(r['captured_checks'] for r in rows),
        'input_tokens_observed':sum(r['input_tokens'] for r in rows),'output_tokens_observed':sum(r['output_tokens'] for r in rows),
        'token_measurements_complete':all(r['token_measurements_complete'] for r in rows),
        'elapsed_seconds':sum(r['elapsed_seconds'] for r in rows)}


def assert_public_capture(record, public_issue):
    """An upstream issue may quote its author's path; never allow ours or keys."""
    issue_forms = [public_issue, json.dumps(public_issue, ensure_ascii=False)[1:-1], json.dumps(public_issue, ensure_ascii=True)[1:-1]]
    def visit(value):
        if isinstance(value, dict):
            for item in value.values():visit(item)
        elif isinstance(value, list):
            for item in value:visit(item)
        elif isinstance(value, str):
            if any(m in value for m in ['OPENAI_API_KEY=', 'GEMINI_API_KEY=', 'Bearer ', '/Users/gauravkumarnayak', '/private/tmp/kairos-qualification014']):
                raise ValueError('Private path or credential marker in investigation capture')
            remaining = value
            for issue in issue_forms:
                if issue:remaining=remaining.replace(issue, '')
            if '/Users/' in remaining:
                raise ValueError('Unbound machine path in investigation capture')
    visit(record)


def attempt(args, study, identifier, arm):
    runtime = args.runtime/'attempts'/identifier/arm
    result = checked_result(args,runtime,identifier,arm,study)
    record_path = runtime/'record.json'
    record = load(record_path) if record_path.exists() else None
    if record:
        for step in record['steps']:
            for kind in ['request', 'result']:
                capture = step.get(kind)
                if capture is None: continue
                blob = runtime / 'blobs' / capture['sha256']
                raw = blob.read_bytes()
                if hashlib.sha256(raw).hexdigest() != capture['sha256'] or raw != canonical(capture['body']).encode():
                    raise ValueError('Captured request/result artifact bytes differ from their recorded body')
    models = [s for s in record.get('steps',[]) if s['kind']=='model'] if record else []
    captured = [s for s in models if s['state']=='captured']
    usages = [s.get('result',{}).get('body',{}).get('usage') for s in captured]
    totals, complete_usage = usage_totals(usages, len(captured), result['cli_dispatches'])
    checks = [s for s in record.get('steps',[]) if s['name']=='run_checks' and s['state']=='captured'] if record else []
    verified = result['outcome']=='verified_repair'
    if verified and (result.get('source_unchanged') is not True or not record or record.get('integrity',{}).get('verified') is not True
        or not any(s.get('result',{}).get('body',{}).get('passed') is True for s in checks)):
        raise ValueError('Verified repair lacks independent passing evidence and unchanged original source')
    value = {'status':result['status'],'outcome':result['outcome'],'verified':verified,'calls':result['cli_dispatches'],
        'patches':result['patches'],'checks':result['checks'],'captured_checks':len(checks),'captured_model_calls':len(captured),'elapsed_seconds':result['elapsed_seconds'],
        'input_tokens':totals['prompt_tokens'],'output_tokens':totals['completion_tokens'],
        'token_measurements_complete':complete_usage,'source_unchanged':result.get('source_unchanged'),
        'result_sha256':sha(runtime/'result.json'),'record_sha256':sha(record_path) if record else None,
        'failure':result.get('failure'),'cleanup_errors':result.get('cleanup_errors',[])}
    return value, record


def report(args):
    if sha(args.study)!=args.study_sha256:raise ValueError('Frozen study bytes differ')
    study=load(args.study)
    ledger_path=args.runtime/'ledger.json'
    ledger=load(ledger_path)
    if ledger['study_sha256']!=args.study_sha256 or [r['instance_id'] for r in ledger['cases']]!=[r['instance_id'] for r in study['cases']]:
        raise ValueError('Complete original-order attempt ledger required')
    if args.output.exists():raise ValueError('Public report destination must be new')
    rows=[]; records={}; licenses={}; issues={}
    for frozen,entry in zip(study['cases'],ledger['cases']):
        identifier=frozen['instance_id'];qpath=args.qualification/'cases'/identifier/'receipt.json';qualification=load(qpath)
        if sha(qpath)!=frozen['qualification_receipt_sha256']:raise ValueError('Frozen qualification receipt differs')
        row={'instance_id':identifier,'repository':'django/django' if identifier.startswith('django__') else 'pytest-dev/pytest',
            'split':frozen['split'],'qualification':qualification['status'],'qualified':qualification.get('qualified',False),'arms':{},
            'qualification_receipt_sha256':frozen['qualification_receipt_sha256']}
        if row['qualified']:
            issues[identifier] = load(qpath.parent/'case-definition.json')['issue']
            material = load(qpath.parent/'material-manifest.json')['files']
            prefix = 'registry/cases/' + identifier + '/source/'
            expected = next((f['sha256'] for f in material if f.get('path') in {prefix+'LICENSE', prefix+'LICENSE.rst', prefix+'LICENSE.txt'}), None)
            license_path = args.runtime/'attribution'/identifier/'LICENSE.txt'
            if expected is None or sha(license_path) != expected:
                raise ValueError('Original upstream attribution is missing or differs from qualified source')
            licenses[identifier] = license_path.read_bytes()
            if [a['arm'] for a in entry['arms']]!=list(ARMS):raise ValueError('Every qualified case needs all three captured arms')
            for arm in ARMS:
                row['arms'][arm],record=attempt(args,study,identifier,arm)
                ledger_arm = next(a for a in entry['arms'] if a['arm'] == arm)
                if ledger_arm['result_sha256'] != row['arms'][arm]['result_sha256']:
                    raise ValueError('Terminal attempt differs from complete ledger digest')
                if record:records[identifier+'/'+arm]=record
        elif entry['arms']:raise ValueError('Excluded qualification case unexpectedly received a model attempt')
        rows.append(row)
    summaries={}; comparisons={}
    for split in ['development','holdout']:
        selected=[r for r in rows if r['split']==split and r['qualified']]
        summaries[split]={}
        for arm in ARMS:
            results=[r['arms'][arm] for r in selected]
            summaries[split][arm]=summarize(results)
        comparisons[split]={left+'-minus-'+right:paired_interval(selected,left,right) for left,right in [('loop','baseline'),('drafts','baseline'),('loop','drafts')]}
    repositories = {repository:{split:{arm:summarize([r['arms'][arm] for r in rows if r['qualified'] and r['repository']==repository and r['split']==split])
        for arm in ARMS} for split in ['development','holdout']} for repository in ['django/django','pytest-dev/pytest']}
    result={'version':'comparison014-public-report-v1','execution_complete':True,'frozen_candidates':24,
        'qualified_cases':sum(r['qualified'] for r in rows),'attempts':sum(len(r['arms']) for r in rows),
        'study_sha256':args.study_sha256,'provider':study['provider'],'profiles':study['profiles'],
        'case_substitutions':0,'model_based_case_selection':False,'summary':summaries,'by_repository':repositories,'paired_comparisons':comparisons,'cases':rows,
        'scope':'Curated independently qualified source-only repair subset; public pretraining exposure unknown; not an official SWE-bench score',
        'limitations':['Development and holdout results remain separate.','Unsuccessful and infrastructure outcomes remain in each arm denominator.',
            'Calls and checks use admitted durable slots; captured calls/checks are reported separately. Equal ceilings do not imply equal consumption; tokens may overshoot post-response admission limits.',
            'Conditional bootstrap intervals do not cover repository-level generalization or establish a safe release.',
            'Existing ChatGPT subscription used; resolved provider model identity and internal retry counts unavailable.']}
    for name, record in records.items():
        assert_public_capture(record, issues[name.split('/')[0]])
    args.output.mkdir(parents=True)
    (args.output/'report.json').write_bytes(encode(result))
    (args.output/'study.json').write_bytes(args.study.read_bytes())
    for identifier, raw in licenses.items():
        path=args.output/'attribution'/identifier/'LICENSE.txt';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    # Preserve captured public-upstream investigation bytes without publishing CLI stdout or auth state.
    for name,record in records.items():
        raw=(args.runtime/'attempts'/name/'record.json').read_bytes()
        path=args.output/'records'/name/'bundle.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return {'attempts':result['attempts'],'qualified_cases':result['qualified_cases'],'summary':summaries}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['study','qualification','runtime','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--study-sha256',required=True)
    a=p.parse_args()
    print(json.dumps(report(a)))

if __name__=='__main__':main()
