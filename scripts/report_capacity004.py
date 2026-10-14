"""Add a complete quiet repeat to the preserved original capacity evidence."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/build004'


def main():
    original=json.loads((OUT/'capacity-analysis.json').read_text())
    directory=OUT/'capacity-quiet-2'
    quiet=json.loads((directory/'summary.json').read_text())
    assert quiet['complete'] and len(quiet['stages'])==5
    assert [row['clients'] for row in quiet['stages']]==[1,5,10,20,10]
    assert [row['requested_seconds'] for row in quiet['stages']]==[180,180,180,180,1800]
    stages=[]
    for row in quiet['stages']:
        operations=row['operations']
        ack=max(operations[name]['p95_ms'] for name in ('durable_ack','retry_ack'))
        reads=operations['summary_read']['p95_ms']
        stages.append({'label':row['label'],'clients':row['clients'],'seconds':row['actual_seconds'],
            'requests':row['requests'],'unexpected_errors':row['unexpected_errors'],
            'observed_quota_rejections':row['observed_quota_rejections'],'quota_expected_in_workload':False,
            'non_success_rate':row['non_success_rate'],'ack_p95_ms':ack,'read_p95_ms':reads,
            'status_counts':row['status_counts'],
            'target_met':ack<750 and reads<750 and row['non_success_rate']<.01})
    raw=directory/'requests.jsonl'
    with raw.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    with raw.open('rb') as stream:
        lines=sum(1 for _ in stream)
    assert lines==sum(row['requests'] for row in stages)
    report={**original,'original_sustained_capacity_accepted':original['sustained_capacity_accepted'],
        'sustained_capacity_accepted':all(row['target_met'] for row in stages),
        'quiet_repeat':{'complete':True,'target_met':all(row['target_met'] for row in stages),
            'scope':quiet['scope'],'host_policy':'Kairos inference, website, browser checks and builds stopped. The observed separate-project build finished before measurement; other shared-host activity was not exhaustively measured.','protocol':quiet['protocol'],
            'host_context_receipt':'evidence/build004/capacity-quiet-2-host-context.json',
            'receipt_directory':str(directory.relative_to(ROOT)),'prior_interrupted_repeat':'evidence/build004/capacity-quiet-interruption.json',
            'stages':stages,'raw_requests':lines,'raw_sha256':digest,'raw_bytes':raw.stat().st_size,
            'limits':'One quiet local repeat with fixture identity/tasks; not inference, OIDC throughput, production scale or resilience to arbitrary service shutdown.'}}
    for path in (OUT/'capacity-summary-final.json',ROOT/'dashboard/lib/capacity004.json',ROOT/'dashboard/public/capacity/results.json'):
        path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'quiet_targets_met':report['sustained_capacity_accepted'],'requests':lines,'stages':stages},indent=2))


if __name__=='__main__':
    main()
