"""Freeze and execute the qualified three-arm cohort without uncertain redispatch."""
from pathlib import Path
from types import SimpleNamespace
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile

from scripts import comparison014 as c, qualify014 as q
from scripts.study010 import _source_identity, cli_identity010, report010
from scripts.study012 import policy012, VERSION as VERSION012

ROOT = Path(__file__).resolve().parents[1]

def load(p):
    return json.loads(p.read_bytes())

def freeze(qualification, output, roots):
    report = load(qualification / 'report.json')
    cohort = load(ROOT / 'evidence/evaluation013/cohort/cohort.json')
    if report.get('execution_complete') is not True or report.get('model_calls') != 0:
        raise ValueError('Qualification must finish before model-study freeze')
    cases = []
    for row in cohort['candidates']:
        p = qualification / 'cases' / row['instance_id'] / 'receipt.json'
        receipt = load(p)
        if receipt['instance_id'] != row['instance_id'] or receipt['split'] != row['split']:
            raise ValueError('Terminal qualification order/split differs')
        cases.append({'instance_id': row['instance_id'], 'split': row['split'], 'qualification_receipt_sha256': c.sha(p)})
    qualified = [row for row in cases if load(qualification / 'cases' / row['instance_id'] / 'receipt.json').get('qualified') is True]
    if not qualified:
        raise ValueError('No independently qualified cases')
    _, provider = cli_identity010()
    policy = policy012(SimpleNamespace(configuration='baseline-v8', retrieval_mode='ast', budget_root=roots), None, {'revision': 'freeze-only'})
    source_files = (*policy.source_files, 'scripts/comparison014.py', 'scripts/repair014/independent_drafts014.py')
    identity = {**_source_identity(ROOT), **{name: c.sha(ROOT / name) for name in source_files}}
    value = {'version': c.VERSION, 'cohort_sha256': c.COHORT_SHA, 'arms': list(c.ARMS),
        'strategy_profiles_sha256': c.digest(c.strategy_profiles014()), 'profiles': c.strategy_profiles014(), 'cases': cases,
        'source_sha256': identity, 'provider': provider, 'orchestrator_sha256': c.sha(Path(__file__)),
        'qualification_report_sha256': c.sha(qualification / 'report.json'),
        'execution_order': 'Original frozen case order; baseline, loop, drafts per qualified case',
        'selection': 'No repair development tuning in this study; original cohort split retained',
        'scope': 'Curated independently qualified subset of Lite; source-only registered checks, not official full SWE-bench score'}
    q.immutable(output, value)
    return value

def rehydrate(identifier, qualification, hidden, work, roots):
    receipt_path = qualification / 'cases' / identifier / 'receipt.json'
    case = {**load(receipt_path.parent / 'case-definition.json'), 'qualified': True}
    row = next(r for r in hidden if r['instance_id'] == identifier) if isinstance(hidden, list) else hidden[identifier]
    if work.exists():
        expected = {'case': identifier, 'qualification_sha256': c.sha(receipt_path), 'ephemeral': True}
        if work.is_symlink() or load(work / 'owner.json') != expected or not (work / 'registry.json').is_file():
            raise ValueError('Incomplete or unrelated preparation is preserved without overwrite')
        from kairos_api.investigations.registry import CaseRegistry
        registry = CaseRegistry(work / 'registry.json', work / 'registry')
        registered = registry.get(identifier)
        if registered != case: raise ValueError('Prepared case differs from independent qualification')
        registry.verify(registered)
        c.validate_qualification014(receipt_path, c.sha(receipt_path), registered)
        return work / 'registry.json'
    work.mkdir(parents=True, mode=0o700)
    q.immutable(work / 'owner.json', {'case': identifier, 'qualification_sha256': c.sha(receipt_path), 'ephemeral': True})
    qualifier, registry_class, tree_hash, _ = q.dependencies(ROOT)
    source, _ = q.pinned_source(row, work, roots, True, tree_hash)
    if tree_hash(source) != case['source_digest']:
        raise ValueError('Rehydrated source digest differs from independent qualification')
    scope = load(receipt_path.parent / 'test-scope.json')
    old = qualifier.added_test_selectors
    qualifier.added_test_selectors = lambda *_: scope['added_hidden_tests']
    try:
        if scope.get('protocol') == 'structured-unittest014-v1':
            from scripts.verifier_unittest014 import verifier
            script, regenerated = verifier(row, source)
        else:
            script, regenerated = qualifier.verifier(row, source)
    finally:
        qualifier.added_test_selectors = old
    if regenerated != scope:
        raise ValueError('Rehydrated verifier scope differs')
    directory = work / 'registry/cases' / identifier
    directory.mkdir(parents=True)
    source.rename(directory / 'source')
    for name, text in [('reference.patch', row['patch']), ('test.patch', row['test_patch']), ('verify.py', script)]:
        (directory / name).write_text(text)
    manifest = work / 'registry.json'
    q.immutable(manifest, {'version': 'repository-cases-v1', 'cases': [case]})
    registry = registry_class(manifest, work / 'registry')
    registry.verify(case)
    for license_name in ['LICENSE', 'LICENSE.rst', 'LICENSE.txt']:
        license_path = directory / 'source' / license_name
        if license_path.is_file() and not license_path.is_symlink():
            attribution = work.parent.parent / 'attribution' / identifier / 'LICENSE.txt'
            attribution.parent.mkdir(parents=True, exist_ok=True)
            attribution.write_bytes(license_path.read_bytes())
            break
    c.validate_qualification014(receipt_path, c.sha(receipt_path), case)
    return manifest

def compact_database(runtime):
    """Preserve every new stopped database byte before reclaiming its working copy."""
    source = runtime / 'postgres-data'
    if not source.is_dir():
        return
    if (source / 'postmaster.pid').exists():
        raise ValueError('Database still active; no compaction')
    metadata = []
    for p in sorted(source.rglob('*')):
        if p.is_symlink():
            raise ValueError('Unexpected database symlink')
        if p.is_file():
            metadata.append({'path': p.relative_to(source).as_posix(), 'sha256': c.sha(p), 'bytes': p.stat().st_size, 'mode': p.stat().st_mode & 0o777})
    archive = runtime / 'postgres-data.tar.gz'
    with tarfile.open(archive, 'x:gz') as stream:
        stream.add(source, arcname='postgres-data', recursive=True)
    with tarfile.open(archive) as stream:
        for item in metadata:
            member = stream.getmember('postgres-data/' + item['path'])
            raw = stream.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Database archive round trip differs')
            if len(raw) != item['bytes'] or member.mode & 0o777 != item['mode']:
                raise ValueError('Database archive metadata differs')
    q.immutable(runtime / 'database-preservation.json', {'archive_sha256': c.sha(archive), 'files': metadata, 'scope': 'Lossless archive of this newly created, stopped study database'})
    shutil.rmtree(source)


def checked_result(args, runtime, identifier, arm, study):
    report010(runtime, expected_version=VERSION012)
    result = load(runtime / 'result.json')
    experiment = load(runtime / 'experiment.json')
    authority = experiment.get('policy', {}).get('comparison014', {})
    if (result.get('task_id') != identifier or experiment.get('task_id') != identifier
            or authority.get('study_sha256') != args.study_sha256 or authority.get('arm') != arm
            or experiment.get('provider') != study['provider'] or experiment.get('source') != study['source_sha256']):
        raise ValueError('Captured result differs from frozen case, arm, provider or source authority')
    return result


def bounded_process(argv, log):
    process = subprocess.Popen(argv, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        return process.wait(timeout=1200)
    except BaseException:
        # Allow runner finally blocks to stop owned PostgreSQL before a forced kill.
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        raise


def run(args):
    if c.sha(args.study) != args.study_sha256:
        raise ValueError('Study manifest changed')
    study = load(args.study)
    if study['orchestrator_sha256'] != c.sha(Path(__file__)):
        raise ValueError('Frozen orchestrator changed')
    hidden = load(args.hidden_records)
    binding = load(args.qualification / 'binding.json')
    if c.sha(args.hidden_records) != binding['hidden_records_sha256']:
        raise ValueError('Hidden inputs differ')
    ledger = []
    for item in study['cases']:
        identifier = item['instance_id']
        receipt = args.qualification / 'cases' / identifier / 'receipt.json'
        qualification = load(receipt)
        if c.sha(receipt) != item['qualification_receipt_sha256']:
            raise ValueError('Frozen qualification receipt changed')
        if not qualification.get('qualified'):
            ledger.append({**item, 'qualification': qualification['status'], 'arms': []})
            continue
        work = args.output / 'prepared' / identifier
        arms = []
        manifest = None
        for arm in c.ARMS:
            runtime = args.output / 'attempts' / identifier / arm
            intent = runtime.parent / (arm + '.intent.json')
            if (runtime / 'result.json').exists():
                result = checked_result(args, runtime, identifier, arm, study)
                arms.append({'arm': arm, 'result_sha256': c.sha(runtime / 'result.json'), 'result': result})
                if (runtime / 'postgres-data').exists(): compact_database(runtime)
                continue
            if intent.exists() or runtime.exists():
                raise ValueError('Uncertain/interrupted arm preserved without redispatch: ' + identifier + '/' + arm)
            if manifest is None:
                manifest = rehydrate(identifier, args.qualification, hidden, work, args.budget_root)
            argv = [sys.executable, '-m', 'scripts.comparison014', '--checkout', str(ROOT), '--manifest', str(manifest),
                '--case-root', str(work / 'registry'), '--runtime', str(runtime), '--study', str(args.study),
                '--study-sha256', args.study_sha256, '--qualification-receipt', str(receipt), '--task-id', identifier, '--arm', arm]
            for root in args.budget_root: argv += ['--budget-root', str(root)]
            q.immutable(intent, {'study_sha256': args.study_sha256, 'case': identifier, 'arm': arm, 'automatic_redispatch': False})
            with intent.with_suffix('.log').open('xb') as log:
                exit_code = bounded_process(argv, log)
            if not (runtime / 'result.json').exists():
                raise ValueError('Arm ended without captured terminal result; inspect intent/log: ' + str(intent))
            result = checked_result(args, runtime, identifier, arm, study)
            arms.append({'arm': arm, 'result_sha256': c.sha(runtime / 'result.json'), 'result': result, 'exit_code': exit_code})
            compact_database(runtime)
            print(json.dumps({'case': identifier, 'split': item['split'], 'arm': arm, 'outcome': result.get('outcome'), 'status': result.get('status')}), flush=True)
        ledger.append({**item, 'qualification': qualification['status'], 'arms': arms})
        q.immutable(args.output / 'completed' / (identifier + '.json'), ledger[-1])
        if work.exists():
            q.immutable(args.output / 'source-preservation' / (identifier + '.json'), {'files': q.material_manifest(work), 'source_receipt_sha256': qualification['evidence_sha256']['source.json'], 'ephemeral_reconstruction': True})
            shutil.rmtree(work)
    q.immutable(args.output / 'ledger.json', {'study_sha256': args.study_sha256, 'cases': ledger})
    return {'cases': len(ledger), 'attempts': sum(len(c['arms']) for c in ledger), 'complete': True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'run'])
    for name in ['qualification', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--budget-root', type=Path, action='append', required=True)
    parser.add_argument('--study', type=Path)
    parser.add_argument('--study-sha256')
    parser.add_argument('--hidden-records', type=Path)
    a = parser.parse_args()
    for path in [a.output, a.qualification]:
        if not any(path.absolute().is_relative_to(p.absolute()) for p in a.budget_root):
            parser.error('Output and qualification must belong to counted roots')
    if a.action == 'freeze':
        freeze(a.qualification, a.output, a.budget_root)
        print(json.dumps({'frozen_sha256': c.sha(a.output)}))
    else:
        if not all([a.study, a.study_sha256, a.hidden_records]): parser.error('run needs study, trusted hash and private hidden records')
        print(json.dumps(run(a)))

if __name__ == '__main__':
    main()
