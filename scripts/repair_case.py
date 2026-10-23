"""Repair one real SWE-bench bug end to end: qualify it, repair it with a hosted model, score it independently.

    python -m scripts.repair_case django__django-13516
    python -m scripts.repair_case django__django-13516 --model nvidia/nemotron-3-ultra-550b-a55b --samples 2

Needs Docker (pinned image kairos-investigation-django:build003) and a free provider key in
~/.kairos-provider.env (see scripts/hosted_repair.py). Everything is written under ~/.kairos/repair/<case>/.
Qualification proves the hidden tests fail before the reference fix and pass after it; the model is called
only for a qualified case, and its patch counts only if those hidden tests pass in Docker.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from scripts import hosted_repair
from scripts.f025_colab import build_package, dev_chains_from_cases, validate_package
from scripts.localization_dev024 import bucket

ROOT = Path(__file__).resolve().parent.parent
# Outside any git work tree: inside one, `git apply` rewrites patch paths relative to that repository.
RUNTIME = Path.home() / '.kairos/repair'
DATASET_REVISION = 'c6fe717fd7a4c3ac1daa4055a4fd082c6a1d28a2'
DATASET_URL = f'https://huggingface.co/datasets/SWE-bench/SWE-bench/resolve/{DATASET_REVISION}/data/test-00000-of-00001.parquet'
DATASET_SHA256 = 'd4f5a245c75319fa8240c540674958c4d491e82edf274b144d43836bdcbc4567'
SUPPORTED = {('django/django', v) for v in ('3.0', '3.1', '3.2')}  # what the pinned Python 3.8 image runs
DEFAULT_MODEL = 'nvidia/nemotron-3-ultra-550b-a55b'
CAPACITY_GIB = '8'


def ensure_dataset(path, opener=urllib.request.urlopen):
    import hashlib
    path = Path(path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with opener(DATASET_URL, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != DATASET_SHA256:
        raise ValueError('SWE-bench dataset hash differs from the pinned revision; refusing to use it')
    partial = path.with_suffix('.partial')
    partial.write_bytes(data)
    partial.rename(path)
    return path


def pick(rows, case):
    row = next((r for r in rows if r['instance_id'] == case), None)
    if row is None:
        raise SystemExit(f'{case} is not in SWE-bench (test split)')
    if bucket(case) != 'development':
        raise SystemExit(f'{case} belongs to the protected {bucket(case)} set; only development cases can be run here')
    if (row['repo'], row['version']) not in SUPPORTED:
        raise SystemExit(f"{case} is {row['repo']} {row['version']}; the pinned image runs Django 3.0-3.2 only")
    return row


def _python(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True)


def qualify(case, row, work):
    (work / 'qualify-input.json').write_text(json.dumps({'jobs': [{'instance_id': case}]}))
    _python('scripts/f024_qualify.py', '--package', work / 'qualify-input.json', '--parquet', work.parent / 'swe-bench-test.parquet',
            '--output', work / 'qualification', '--storage-roots', work / 'storage-roots.json', '--capacity-gib', CAPACITY_GIB,
            '--execute', '--allow-source-download')
    return json.loads((work / 'qualification/summary.json').read_text())['qualified'].get(case) is True


def repair(row, work, model, samples):
    chains = dev_chains_from_cases([row], work / 'chain-build')
    if not chains:
        raise SystemExit('The fix spans more code regions than the harness gives the model; case skipped')
    package = build_package([], chains, samples=samples)
    package['label'] = f"repair_case: {row['instance_id']} with {model}"
    validate_package(package, call_cap=len(package['chains']) * hosted_repair.MAX_CALLS_PER_CHAIN)
    (work / 'package.json').write_text(json.dumps(package, sort_keys=True, indent=1))
    hosted_repair.load_env()
    provider = 'openrouter' if model.endswith(':free') else 'nvidia'  # OpenRouter's free models carry the :free suffix
    generate = hosted_repair.client(provider, model, hosted_repair.api_key(provider))
    hosted_repair.run(package, work / 'results', generate)


def score(work):
    _python('scripts/f025_score.py', '--results', work / 'results', '--package', work / 'package.json',
            '--qualification', work / 'qualification', '--parquet', work.parent / 'swe-bench-test.parquet',
            '--storage-roots', work / 'storage-roots.json', '--admission-module', ROOT / 'scripts/admission023.py',
            '--output', work / 'scoring', '--work-root', work / 'score-work', '--capacity-gib', CAPACITY_GIB, '--execute')
    return json.loads((work / 'scoring/scores.json').read_text())


def run_case(row, work, model, samples):
    work.mkdir(parents=True, exist_ok=True)
    (work / 'storage-roots.json').write_text(json.dumps({'roots': [str(work)]}))
    if not qualify(row['instance_id'], row, work):
        raise SystemExit(f"{row['instance_id']} did not qualify: its hidden tests do not fail before and pass after the "
                         'reference fix in the pinned image, so a repair could not be judged')
    repair(row, work, model, samples)
    return score(work)


def main():  # pragma: no cover - network, Docker and a hosted model
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('case')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--samples', type=int, default=1, choices=[1, 2])
    args = parser.parse_args()
    import pyarrow.parquet as pq
    rows = pq.read_table(ensure_dataset(RUNTIME / 'swe-bench-test.parquet')).to_pylist()
    row = pick(rows, args.case)
    work = RUNTIME / args.case
    if work.exists():
        raise SystemExit(f'{work} already exists; move it away to run this case again')
    scores = run_case(row, work, args.model, args.samples)
    for result in scores['results']:
        print(f"{result['chain_id']}: {result['outcome']}")
    verified = scores['fair_pick_verified'] == 1
    print(('REPAIRED: hidden tests pass. ' if verified else 'NOT REPAIRED. ') + f'Evidence: {work}')
    record = work / 'results/chains' / (scores['results'][0]['chain_id'] + '.json')
    if verified and record.exists():
        print(json.loads(record.read_text())['patch'])


if __name__ == '__main__':
    main()
