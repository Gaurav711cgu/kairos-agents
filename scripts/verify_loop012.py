"""Verify the bounded-loop overlay without rewriting earlier release seals."""
from pathlib import Path
import argparse
import json

from scripts.package_release007 import fingerprint, inventory, read_json, validate_entries
from scripts.verify_retrieval011 import (parent_inventory, MANIFEST as PARENT_MANIFEST,
                                         PARENT_MANIFEST as REPAIR_MANIFEST,
                                         PARENT_COMMIT as REPAIR_COMMIT)
from scripts.verify_showcase008 import METADATA

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'evidence/loop012/manifest.json'
PARENT_COMMIT = '78586f0e51ca8a42d632090bfe3c4fa877fa85f1'
ALLOWED = {'README.md', 'BRAIN.md', 'DECISIONS.md', '.github/workflows/regression-gate.yml',
    'scripts/acceptance007.py', 'scripts/study010.py', 'scripts/study012.py',
    'scripts/verify_loop012.py', 'docs/LOOP_012.md',
    'kairos_api/investigations/context_v7.py', 'kairos_api/investigations/contracts.py', 'kairos_api/investigations/model.py',
    'kairos_api/investigations/repository.py', 'kairos_api/investigations/routes.py',
    'kairos_api/investigations/sandbox.py', 'kairos_api/investigations/worker.py',
    'kairos_api/investigations/output_supervisor.py',
    'kairos_api/migrations/0005_configuration_v8_expand.sql',
    'kairos_api/migrations/0006_configuration_v8_validate.sql',
    'scripts/repair010/codex_context010.py', 'scripts/repair010/codex_transport010.py',
    'scripts/repair010/feedback010.py', 'tests/test_codex_transport010.py',
    'tests/test_migrations007.py', 'tests/test_protocol_v8.py', 'tests/test_v8_postgres.py',
    'tests/test_output_supervisor011.py', 'tests/test_retrieval_loop012.py',
    'tests/test_retrieval_admission012.py', 'tests/test_retrieval_integration012.py', 'tests/test_study012.py', 'tests/test_verify_loop012.py'}


def allowed(name):
    return (name in ALLOWED or name.startswith('scripts/repair012/') and name.endswith('.py')
            or name.startswith('evidence/loop012/') and Path(name).suffix in {'.json', '.md'})


def inherited_inventory(root):
    base = parent_inventory(root)
    parent = read_json(root / PARENT_MANIFEST)
    if (parent.get('version') != 'retrieval011-phase1-v1'
            or parent.get('parent_commit') != REPAIR_COMMIT
            or parent.get('parent_manifest') != fingerprint(root / REPAIR_MANIFEST)):
        raise ValueError('Preserved retrieval011 ancestry differs')
    return {**base, **validate_entries(parent['files'])}


def verify_delta(actual, inherited, changes):
    changes = validate_entries(changes)
    if MANIFEST in changes or any(not allowed(name) for name in changes):
        raise ValueError('Undeclared Phase 2 source path')
    if actual != {**inherited, **changes}:
        raise ValueError('Active source differs from the sealed loop phase')


def verify(root):
    root = Path(root).resolve(strict=True)
    value = read_json(root / MANIFEST)
    if value.get('version') != 'loop012-phase2-v1' or value.get('parent_commit') != PARENT_COMMIT:
        raise ValueError('Unknown loop phase identity')
    if value.get('parent_manifest') != fingerprint(root / PARENT_MANIFEST):
        raise ValueError('Preserved retrieval011 manifest differs')
    inherited = inherited_inventory(root)
    excluded = {*METADATA, 'evidence/ci009/manifest.json', REPAIR_MANIFEST, PARENT_MANIFEST, MANIFEST}
    actual = {name: row for name, row in inventory(root).items() if name not in excluded}
    verify_delta(actual, inherited, value['files'])
    return {'passed': True, 'phase': 'loop012-phase2', 'files': len(value['files']),
            'historical_seals_and_archive_verified': True,
            'scope': 'Byte consistency and preserved evidence; fixture tests do not establish model repair effectiveness'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Loop phase verification failed: ' + str(error) + '\n')
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
