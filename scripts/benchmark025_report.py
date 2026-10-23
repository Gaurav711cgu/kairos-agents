"""Build the website's benchmark data from the scored F025 runs in ``evidence/benchmark025``.

Only independent Docker verdicts (``scores.json``) count as repairs; static acceptance during the run never does.

    python -m scripts.benchmark025_report   # writes dashboard/lib/benchmark025.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE, OUTPUT = ROOT / 'evidence/benchmark025', ROOT / 'dashboard/lib/benchmark025.json'


def run_report(directory):
    scores = json.loads((directory / 'scores.json').read_text())
    meta = json.loads((directory / 'run.json').read_text())
    cases = {}
    for result in scores['results']:
        _, instance, sample = result['chain_id'].split('/')
        record_path = directory / 'results/chains' / (result['chain_id'] + '.json')
        record = json.loads(record_path.read_text()) if record_path.exists() else {}
        cases.setdefault(instance, {'instance_id': instance, 'samples': []})['samples'].append(
            {'sample': sample, 'outcome': result['outcome'], 'verified': bool(result.get('verified_repair')),
             'calls': record.get('calls', 0), 'patch': record.get('patch')})
    for instance, pick in scores['fair_pick'].items():
        cases[instance]['fair_pick_verified'] = bool(pick['verified'])
    return {'run': directory.name, **meta, 'cases_total': len(cases), 'cases_verified': scores['fair_pick_verified'],
            'attempts_total': scores['attempts'], 'attempts_verified': sum(s['verified'] for c in cases.values() for s in c['samples']),
            'model_calls': sum(s['calls'] for c in cases.values() for s in c['samples']),
            'cases': sorted(cases.values(), key=lambda c: c['instance_id'])}


def build(evidence=EVIDENCE):
    return {'benchmark': 'SWE-bench Verified, Django development cases, oracle code regions, F025 repair loop',
            'scoring': 'hidden FAIL_TO_PASS and PASS_TO_PASS tests in the pinned Docker image',
            'runs': [run_report(d) for d in sorted(evidence.iterdir()) if (d / 'scores.json').exists()]}


if __name__ == '__main__':
    report = build(Path(sys.argv[1]) if len(sys.argv) > 1 else EVIDENCE)
    OUTPUT.write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps([{k: r[k] for k in ['run', 'cases_verified', 'cases_total', 'attempts_verified', 'attempts_total']} for r in report['runs']]))
