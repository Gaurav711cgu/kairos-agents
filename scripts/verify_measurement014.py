"""Verify the additive measurement release, inherited seals and metric arithmetic."""
from pathlib import Path
import argparse
import json
import math
import re
import statistics
from collections import Counter
from scripts.package_release007 import fingerprint, inventory, read_json, validate_entries
from scripts import verify_evaluation013 as parent
from scripts.verify_showcase008 import METADATA

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'evidence/measurement014/manifest.json'
PARENT_COMMIT = '32c21a9c189b46d755cf4cc9d8149a2ee41371fc'
ALLOWED = {'README.md', 'BRAIN.md', 'DECISIONS.md', 'AGENTS.md', '.github/workflows/regression-gate.yml',
    'scripts/acceptance007.py', 'requirements-training014.lock', 'dashboard/package.json',
    'dashboard/app/repair-investigation/page.tsx', 'dashboard/playwright.recorded.config.ts',
    'dashboard/lib/repair010-downloads.ts', 'dashboard/app/retrieval-training/page.tsx',
    'dashboard/app/api/training014/[...path]/route.ts', 'dashboard/app/page.tsx',
    'dashboard/app/repair-comparison/page.tsx', 'dashboard/app/repair-comparison/[caseId]/[arm]/page.tsx',
    'dashboard/app/api/comparison014/[...path]/route.ts', 'dashboard/app/layout.tsx', 'dashboard/app/how-it-works/page.tsx'}


def allowed(name):
    p = Path(name)
    if name in ALLOWED: return True
    if p.parent == Path('notebooks') and '014' in p.name and p.suffix == '.ipynb': return True
    if p.parent == Path('scripts') and p.name.endswith('014.py'): return True
    if p.parent == Path('tests') and p.name.startswith('test_') and p.name.endswith('014.py'): return True
    if p.parent == Path('docs') and p.name.endswith('_014.md'): return True
    if p.parent == Path('dashboard/lib') and p.name.startswith('training014-') and p.suffix in {'.json', '.mjs'}: return True
    if p.parent == Path('dashboard/lib') and p.name.startswith('comparison014-') and p.suffix in {'.json', '.ts', '.mjs'}: return True
    if name in {'dashboard/e2e/training014.spec.ts', 'dashboard/e2e/comparison014.spec.ts'}: return True
    if name.startswith('scripts/repair014/') and p.suffix == '.py': return True
    if name.startswith('evidence/measurement014/'):
        return p.name == 'Dockerfile' or p.suffix in {'.json', '.jsonl', '.md', '.patch', '.png', '.gz', '.zip', '.txt', '.lock', '.py', '.ipynb'} or bool(re.fullmatch('[a-f0-9]{64}', p.name))
    return False


def inherited(root):
    return {**parent.parent_inventory(root), **validate_entries(read_json(root / parent.MANIFEST)['files'])}


def verify_delta(actual, previous, changes):
    changes = validate_entries(changes)
    if MANIFEST in changes or any(not allowed(n) for n in changes):
        raise ValueError('Undeclared measurement source path')
    if actual != {**previous, **changes}:
        raise ValueError('Active source differs from sealed measurement overlay')


def metric_arithmetic(report):
    pairs = report['paired']
    if len(pairs) != report['queries'] or len({p['example_id'] for p in pairs}) != len(pairs):
        raise ValueError('Missing or duplicate paired held-out queries')
    for side in ['base', 'adapter']:
        for metric in ['mrr', 'recall@1', 'recall@5', 'recall@10']:
            values = [p[side][metric] for p in pairs]
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError('Invalid retrieval metric')
            if not math.isclose(statistics.fmean(values), report['summary'][side][metric], abs_tol=1e-12):
                raise ValueError('Published mean differs from paired outcomes')
    return True


def comparison_arithmetic(report):
    cases = report['cases']
    if len(cases) != 24 or len({c['instance_id'] for c in cases}) != 24:
        raise ValueError('Comparison must preserve all24 original candidates')
    if (report.get('execution_complete') is not True or report['attempts'] != sum(len(c['arms']) for c in cases)
            or report['qualified_cases'] != sum(c['qualified'] for c in cases)):
        raise ValueError('Comparison attempt/qualification totals differ')
    for case in cases:
        if set(case['arms']) != ({'baseline', 'loop', 'drafts'} if case['qualified'] else set()):
            raise ValueError('Missing paired arm or model execution on an excluded case')
        if case['split'] not in {'development', 'holdout'}:
            raise ValueError('Unknown frozen split')
        for result in case['arms'].values():
            if result['verified'] != (result['outcome'] == 'verified_repair'):
                raise ValueError('Repair indicator differs from verdict')
            for key in ['calls', 'checks', 'captured_checks', 'captured_model_calls', 'input_tokens', 'output_tokens']:
                if type(result[key]) is not int or result[key] < 0:
                    raise ValueError('Invalid captured comparison counter')
            if result['captured_checks'] > result['checks'] or result['captured_model_calls'] > result['calls']:
                raise ValueError('Captured counters exceed admitted slots')
            seconds = result['elapsed_seconds']
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError('Invalid elapsed measurement')
    for split in ['development', 'holdout']:
        selected = [c for c in cases if c['qualified'] and c['split'] == split]
        for arm in ['baseline', 'loop', 'drafts']:
            rows = [c['arms'][arm] for c in selected]
            expected = {'cases': len(rows), 'verified': sum(r['verified'] for r in rows),
                'outcomes': dict(Counter(r['outcome'] for r in rows)), 'calls': sum(r['calls'] for r in rows),
                'checks_admitted': sum(r['checks'] for r in rows), 'checks_captured': sum(r['captured_checks'] for r in rows),
                'input_tokens_observed': sum(r['input_tokens'] for r in rows), 'output_tokens_observed': sum(r['output_tokens'] for r in rows),
                'token_measurements_complete': all(r['token_measurements_complete'] for r in rows)}
            actual = report['summary'][split][arm]
            if any(actual[k] != value for k, value in expected.items()) or not math.isclose(actual['elapsed_seconds'], sum(r['elapsed_seconds'] for r in rows), abs_tol=1e-9):
                raise ValueError('Comparison summary differs from per-case outcomes')
    if 'by_repository' in report:
        for repository in ['django/django', 'pytest-dev/pytest']:
            for split in ['development', 'holdout']:
                selected = [c for c in cases if c['qualified'] and c['split'] == split and c['repository'] == repository]
                for arm in ['baseline', 'loop', 'drafts']:
                    actual = report['by_repository'][repository][split][arm]
                    if actual['cases'] != len(selected) or actual['verified'] != sum(c['arms'][arm]['verified'] for c in selected):
                        raise ValueError('Repository repair totals differ from paired cases')
    return True


def verify(root):
    root = Path(root).resolve(strict=True)
    seal = read_json(root / MANIFEST)
    if seal.get('version') != 'measurement014-v1' or seal.get('parent_commit') != PARENT_COMMIT:
        raise ValueError('Unknown measurement ancestry')
    if seal.get('parent_manifest') != fingerprint(root / parent.MANIFEST):
        raise ValueError('Historical evaluation013 manifest changed')
    excluded = {*METADATA, 'evidence/ci009/manifest.json', 'evidence/repair010/manifest.json',
        'evidence/retrieval011/manifest.json', 'evidence/loop012/manifest.json', parent.MANIFEST, MANIFEST}
    actual = {n: row for n, row in inventory(root).items() if n not in excluded}
    verify_delta(actual, inherited(root), seal['files'])
    evaluation = read_json(root / 'evidence/measurement014/training/heldout-evaluation014.json')
    metric_arithmetic(evaluation)
    resume = read_json(root / 'evidence/measurement014/training/selected-resume014.json')
    if resume.get('complete_state_bitwise_equal') is not True or resume.get('passed') is not True:
        raise ValueError('Actual selected-head resume evidence unavailable')
    comparison = read_json(root / 'evidence/measurement014/comparison/report.json')
    if comparison.get('execution_complete') is not True or comparison.get('frozen_candidates') != 24:
        raise ValueError('Fresh comparison is incomplete')
    comparison_arithmetic(comparison)
    cohort = read_json(root / 'evidence/evaluation013/cohort/cohort.json')
    if [(c['instance_id'], c['split']) for c in comparison['cases']] != [(c['instance_id'], c['split']) for c in cohort['candidates']]:
        raise ValueError('Comparison differs from original cohort order/split')
    return {'passed': True, 'phase': 'measurement014', 'files': len(seal['files']),
        'historical_seals_preserved': True, 'training_queries': evaluation['queries'],
        'scope': 'Exact captured bytes and source overlay; measured claims remain limited to recorded protocols'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    a = parser.parse_args()
    try: print(json.dumps(verify(a.root), indent=2))
    except (ValueError, KeyError, OSError, TypeError) as e: parser.exit(1, 'Measurement seal failed: ' + str(e) + '\n')

if __name__ == '__main__': main()
