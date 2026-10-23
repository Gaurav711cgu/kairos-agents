"""The website benchmark data counts only independent Docker verdicts."""
import json

from scripts.benchmark025_report import build


def test_report_counts_scored_repairs_per_case_and_attempt(tmp_path):
    run = tmp_path / 'model-a-dev'
    (run / 'results/chains/dev/case-1').mkdir(parents=True)
    (run / 'results/chains/dev/case-1/oracle-s0.json').write_text(json.dumps({'calls': 2, 'patch': 'diff --git a b'}))
    (run / 'run.json').write_text(json.dumps({'model': 'a', 'split': 'development'}))
    (run / 'scores.json').write_text(json.dumps({
        'attempts': 2, 'fair_pick_verified': 1, 'fair_pick': {'case-1': {'verified': True}},
        'results': [{'chain_id': 'dev/case-1/oracle-s0', 'outcome': 'verified_repair', 'verified_repair': True},
                    {'chain_id': 'dev/case-1/oracle-s1', 'outcome': 'behavioral_mismatch', 'verified_repair': False}]}))
    [report] = build(tmp_path)['runs']
    assert (report['cases_verified'], report['cases_total'], report['attempts_verified'], report['attempts_total']) == (1, 1, 1, 2)
    [case] = report['cases']
    assert case['fair_pick_verified'] and [s['calls'] for s in case['samples']] == [2, 0] and case['samples'][0]['patch']
