"""Recorded repair follow-up; frozen historical outcomes are never overwritten."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT
OUT = ROOT / 'evidence/build006'
STATE = ROOT / '.runtime/study006'
PROFILES = {name: ORIGINAL / f'evidence/build004/inference-{name}-mac.json' for name in ('coder', 'qwen3')}
PROFILES['thinking'] = OUT / 'inference-qwen3-thinking.json'
PILOT_IDS = ['django__django-11066', 'pytest-dev__pytest-6197', 'psf__requests-2931']
SOURCE_FILES = ['contracts.py', 'model.py', 'worker.py', 'sandbox.py', 'context_v5.py', 'repository.py', 'routes.py', 'schema.sql']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.pending')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def plan(profile, registry):
    from kairos_api.investigations.contracts import CONFIGURATIONS, generation_for
    return {'version': 'repair-follow-up-v1', 'profile': json.loads(profile.read_text()),
            'registry': json.loads(registry.read_text()),
            'source_hashes': {name: hashlib.sha256((ROOT / 'kairos_api/investigations' / name).read_bytes()).hexdigest()
                              for name in SOURCE_FILES},
            'configurations': {name: {'budgets': CONFIGURATIONS[name], 'generation': generation_for(name)}
                               for name in ('baseline-v5', 'loop-v5', 'baseline-v6', 'loop-v6')},
            'limits': ['Development uses three previously designated development cases.',
                       'New validation cases are qualified and locked before their model execution.',
                       'Historical validation failures informed general harness diagnosis; historical evaluation is never rerun as fresh validation.',
                       'Public historical cases may be contaminated. No leaderboard or statistical superiority claim.']}


def start_model(name):
    profile = json.loads(PROFILES[name].read_text())
    runtime = ORIGINAL / '.runtime/investigations'
    with httpx.Client(timeout=1, trust_env=False) as client:
        try: client.get('http://127.0.0.1:8130/health')
        except httpx.HTTPError: pass
        else: raise RuntimeError('An existing model server occupies port 8130; it was preserved')
    for item in profile['files']:
        path = runtime / item['path']
        with path.open('rb') as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != item['sha256'] or path.stat().st_size != item['bytes']:
            raise ValueError('Pinned runtime file mismatch: ' + item['path'])
    import tarfile
    with tarfile.open(runtime / 'runtime/llama.tar.gz') as archive:
        for member in archive.getmembers():
            if not member.isfile(): continue
            with (runtime / 'runtime' / member.name).open('rb') as actual, archive.extractfile(member) as expected:
                if hashlib.file_digest(actual, 'sha256').hexdigest() != hashlib.file_digest(expected, 'sha256').hexdigest():
                    raise ValueError('Extracted runtime differs: ' + member.name)
    model = next(item['path'] for item in profile['files'] if item['path'].endswith('.gguf'))
    args = [str(runtime / 'runtime/llama-b11552/llama-server'), '--model', str(runtime / model),
            '--host', '127.0.0.1', '--port', '8130', '--ctx-size', str(profile['settings']['context']), '--parallel', '1',
            '--threads', '4', '--n-predict', str(profile['settings']['max_output_tokens']), '--jinja', '--no-webui']
    log = (STATE / ('model-' + name + '.log')).open('a')
    process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            for _ in range(60):
                if process.poll() is not None: raise RuntimeError('Pinned inference exited; private runtime log retained')
                try:
                    if client.get('http://127.0.0.1:8130/health').status_code == 200: return process, log
                except httpx.HTTPError: pass
                time.sleep(1)
        raise TimeoutError('Local model startup exceeded sixty seconds')
    except BaseException:
        process.terminate(); process.wait(timeout=15); log.close(); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['pilot', 'freeze', 'evaluate'])
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--revision', type=int, choices=[1, 2], default=1)
    parser.add_argument('--strategy', choices=['baseline-v5', 'loop-v5', 'baseline-v6', 'loop-v6'], default='baseline-v5')
    args = parser.parse_args()
    os.environ.update(json.loads((STATE / 'environment.json').read_text()))
    profile = PROFILES[args.profile]
    os.environ['KAIROS_INVESTIGATION_MODEL_MANIFEST'] = str(profile)
    registry_path = ROOT / ('cases/study004.json' if args.phase == 'pilot' else 'cases/study006-toml-reuse.json')
    if args.phase != 'pilot':
        os.environ['KAIROS_INVESTIGATION_ROOT'] = str(ORIGINAL / '.runtime/investigations/study006')
    from kairos_api.investigations.registry import CaseRegistry
    from kairos_api.investigations.repository import InvestigationRepository
    from kairos_api.investigations.worker import InvestigationWorker
    frozen = plan(profile, registry_path)
    lock = OUT / 'validation-lock.json'
    if args.phase == 'freeze':
        qualification = json.loads((OUT / 'qualification-toml-reuse/qualification.json').read_text())
        if qualification['model_calls'] or len(frozen['registry']['cases']) != qualification['qualified'] or qualification['qualified'] < 4:
            raise RuntimeError('Qualification receipts do not support a bounded fresh cohort')
        frozen['qualification'] = qualification
        # An exhausted repository pool remains an explicit shortfall. All qualified
        # cases are locked and attempted; none are replaced by model performance.
        frozen['qualification_target_met'] = qualification['complete']
        frozen['validation_cohort_size'] = qualification['qualified']
        if lock.exists() and json.loads(lock.read_text()) != frozen: raise RuntimeError('Existing validation lock differs')
        write(lock, frozen); print('Fresh validation configuration locked; no inference.', flush=True); return
    if args.phase == 'evaluate':
        qualification = json.loads((OUT / 'qualification-toml-reuse/qualification.json').read_text())
        frozen.update(qualification=qualification, qualification_target_met=qualification['complete'], validation_cohort_size=qualification['qualified'])
        if not lock.exists() or json.loads(lock.read_text()) != frozen:
            raise RuntimeError('Validation source, profile or case lock differs')
    label = 'pilot-' + args.profile + '-r' + str(args.revision) if args.phase == 'pilot' else 'validation'
    directory = OUT / label
    manifest = directory / 'configuration.json'
    if manifest.exists() and json.loads(manifest.read_text()) != frozen:
        raise RuntimeError('Recorded revision changed; preserve it and use the next development revision')
    write(manifest, frozen)
    for name in SOURCE_FILES:
        target = directory / 'source' / name; target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / 'kairos_api/investigations' / name).read_bytes()
        if target.exists() and target.read_bytes() != raw: raise RuntimeError('Captured source changed')
        target.write_bytes(raw)
    registry = CaseRegistry(registry_path)
    cases = [registry.get(identifier) for identifier in PILOT_IDS] if args.phase == 'pilot' else registry.cases()
    strategies = [args.strategy] if args.phase == 'pilot' else ['baseline-v5', 'loop-v5']
    repo = InvestigationRepository(registry=registry); repo.initialize()
    process = log = None
    try:
        process, log = start_model(args.profile)
        worker = InvestigationWorker(repo)
        for case in cases:
            for strategy in strategies:
                key = 'repair006:' + label + ':' + case['id'] + ':' + strategy
                record = repo.enqueue('repair006', key, case['id'], strategy)
                # The command receipt is retained before execution. Unknown dispatches are never replaced.
                write(directory / (case['id'] + '-' + strategy + '.json'), record)
                if record['status'] == 'queued':
                    expected_id = record['id']
                    record = worker.run_once()
                    if not record or record['id'] != expected_id:
                        raise RuntimeError('Unexpected study queue state')
                if record['status'] in {'queued', 'running'}: raise RuntimeError('Attempt remains active; do not retry dispatch')
                record = repo.publish(record['id'], 'repair006')
                write(directory / (case['id'] + '-' + strategy + '.json'), record)
                print(json.dumps({'task': case['id'], 'strategy': strategy, 'outcome': record['outcome'],
                                  'calls': record['model_calls'], 'patches': record['patch_count'], 'checks': record['check_count']}), flush=True)
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        if log is not None: log.close()
        repo.close()
    records = []
    for path in sorted(directory.glob('*.json')):
        value = json.loads(path.read_text())
        if isinstance(value, dict) and 'steps' in value: records.append(value)
    write(directory / 'summary.json', {'attempts': len(records), 'verified': sum(r['outcome'] == 'verified_repair' for r in records),
          'records': [{'id': r['id'], 'task_id': r['task_id'], 'configuration': r['configuration'], 'outcome': r['outcome'],
                       'calls': r['model_calls'], 'patches': r['patch_count'], 'checks': r['check_count']} for r in records],
          'updated_at': datetime.now(timezone.utc).isoformat(), 'api_spend_usd': 0})


if __name__ == '__main__': main()
