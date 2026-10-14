"""Actual process-death recovery using explicitly isolated provider fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.sandbox import Workspace
from kairos_api.investigations.worker import InvestigationWorker

ROOT = Path(__file__).resolve().parents[1]


def child(state_path, phase, identifier):
    state = json.loads(state_path.read_text())
    registry = CaseRegistry(Path(state['registry']), Path(state['runtime']))
    repository = InvestigationRepository(state['database'], Path(state['blobs']), registry)
    job = repository.claim('crash-fixture-' + phase)
    if not job or str(job['id']) != identifier:
        raise RuntimeError('Unexpected isolated crash queue')
    workspace = Workspace(registry, registry.get('fixture'))
    source = workspace.read_original('source/value.py')
    sequence = repository.begin(job, 'tool', 'initial_source', {'fixture_only': True})
    repository.capture(job, sequence, source)
    sequence = repository.begin(job, 'context', 'selection', {'fixture_only': True})
    repository.capture(job, sequence, {'allowed_actions': ['final_result'], 'source_catalog': [source],
                                     'selection': {'observations': []}})
    sequence = repository.begin(job, 'model', 'dispatch', {'fixture_only': True})
    if phase == 'captured':
        repository.capture(job, sequence, {'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'action': 'final_result', 'summary': 'Isolated captured-response fixture.'})}}]})
    marker = state_path.parent / (phase + '.ready.json')
    marker.write_text(json.dumps({'workspace': workspace.temporary.name}))
    os.kill(os.getpid(), signal.SIGSTOP)
    raise RuntimeError('Crash child unexpectedly resumed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path)
    parser.add_argument('--phase', choices=['intent', 'captured'])
    parser.add_argument('--identifier')
    args = parser.parse_args()
    if args.child:
        child(args.child, args.phase, args.identifier)
        return
    database = os.environ['TEST_DATABASE_URL']
    schema = 'crash006_' + uuid4().hex
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    receipts = []
    try:
        with tempfile.TemporaryDirectory(prefix='kairos-crash006-', dir=ROOT / '.runtime') as temporary:
            directory = Path(temporary)
            directory.chmod(0o700)
            case_directory = directory / 'cases/fixture'
            (case_directory / 'source/source').mkdir(parents=True)
            (case_directory / 'source/source/value.py').write_text('value = 1\n')
            for name in ('reference.patch', 'test.patch'):
                (case_directory / name).write_text('')
            empty = hashlib.sha256(b'').hexdigest()
            case = {'id': 'fixture', 'qualified': True, 'title': 'Explicit crash fixture', 'issue': 'No repair requested.',
                    'repository': 'fixture', 'revision': 'fixture-v1', 'entry_files': ['source/value.py'],
                    'approved_prefix': 'source/', 'split': 'development',
                    'source_digest': tree_hash(case_directory / 'source'),
                    'reference_digest': empty, 'verification_digest': empty}
            registry_path = directory / 'cases.json'
            registry_path.write_text(json.dumps({'version': 'repository-cases-v1', 'cases': [case]}))
            state = {'database': make_conninfo(database, options='-c search_path=' + schema),
                     'registry': str(registry_path), 'runtime': str(directory), 'blobs': str(directory / 'blobs')}
            state_path = directory / 'state.json'
            descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as output:
                json.dump(state, output)
            registry = CaseRegistry(registry_path, directory)
            repository = InvestigationRepository(state['database'], directory / 'blobs', registry)
            repository.initialize()
            try:
                for phase in ('intent', 'captured'):
                    record = repository.enqueue('crash-fixture', phase, 'fixture', 'baseline-v5')
                    marker = directory / (phase + '.ready.json')
                    process = subprocess.Popen([sys.executable, '-m', 'scripts.verify_recovery006', '--child', str(state_path),
                                                '--phase', phase, '--identifier', record['id']],
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
                    try:
                        deadline = time.monotonic() + 20
                        while not marker.exists():
                            if process.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError('Crash fixture did not reach its durable boundary')
                            time.sleep(0.05)
                        os.kill(process.pid, signal.SIGKILL)
                        process.wait(timeout=10)
                        with repository.connect() as connection:
                            connection.execute("UPDATE kairos_investigations SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s", (record['id'],))
                        class NoDispatch:
                            def prepare(self, *args):
                                raise AssertionError('Recovery must consume the captured result')
                            def __call__(self, *args):
                                raise AssertionError('Recovery must not dispatch inference')
                        InvestigationWorker(repository, NoDispatch()).run_once()
                        result = repository.read(record['id'], 'crash-fixture')
                        expected = 'unknown_dispatch' if phase == 'intent' else 'no_patch'
                        assert result['outcome'] == expected and result['model_calls'] == 1
                        assert result['integrity']['verified']
                        receipts.append({'phase': phase, 'signal': 'SIGKILL', 'exit_code': process.returncode,
                                         'outcome': result['outcome'], 'dispatch_receipts': 1,
                                         'actual_model_calls': 0, 'additional_dispatches': 0, 'integrity_verified': True})
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait(timeout=10)
                        if marker.exists():
                            workspace = Path(json.loads(marker.read_text())['workspace'])
                            if workspace.parent == Path(tempfile.gettempdir()) and workspace.name.startswith('kairos-investigation-'):
                                shutil.rmtree(workspace, ignore_errors=True)
            finally:
                repository.close()
    finally:
        with psycopg.connect(database, autocommit=True) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    receipt = {'passed': True, 'drills': receipts,
               'scope': 'Real SIGKILL and PostgreSQL recovery with isolated provider fixtures; not a new real-model experiment.'}
    (ROOT / 'evidence/build006/crash-recovery.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
