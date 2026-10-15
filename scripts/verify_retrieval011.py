"""Verify the additive retrieval phase and every preserved release binding."""
from pathlib import Path
import argparse
import json

from scripts.package_release007 import fingerprint, inventory, read_json, validate_entries
from scripts.verify_repair010 import (verify_parent, MANIFEST as PARENT_MANIFEST,
                                      PRESERVED as PARENT_PRESERVED)
from scripts.verify_showcase008 import METADATA

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'evidence/retrieval011/manifest.json'
PARENT_COMMIT = '69432bd468e2d8ccefcf522d89365cbe32970d31'
ALLOWED = {'README.md', 'BRAIN.md', 'DECISIONS.md', '.github/workflows/regression-gate.yml',
    'scripts/acceptance007.py', 'scripts/retrieval_study011.py', 'scripts/prepare_retrieval011.py',
    'scripts/verify_retrieval011.py', 'tests/test_retrieval011.py', 'tests/test_retrieval_study011.py',
    'tests/test_encoder011.py', 'tests/test_verify_retrieval011.py', 'tests/test_faiss_worker011.py', 'tests/test_retrieval_cli011.py',
    'requirements-retrieval011.lock', 'profiles/coderank011.json', 'profiles/coderank011-header.json',
    'docs/AI_ADVANCEMENT_PLAN_011.md', 'docs/RETRIEVAL_011.md'}


def allowed(name):
    return (name in ALLOWED or name.startswith('scripts/retrieval011/') and name.endswith('.py')
            or name.startswith('evidence/retrieval011/') and Path(name).suffix in {'.json', '.md'})


def parent_inventory(root):
    base = verify_parent(root)
    parent = read_json(root / PARENT_MANIFEST)
    if (parent.get('version') != 'repair-workflow010-v1'
            or parent.get('preserved_parent') != {name: fingerprint(root / name) for name in PARENT_PRESERVED}):
        raise ValueError('Preserved repair010 ancestry differs')
    return {**base, **validate_entries(parent['files'])}


def verify_delta(actual, inherited, changes):
    changes = validate_entries(changes)
    if MANIFEST in changes or any(not allowed(name) for name in changes):
        raise ValueError('Undeclared Phase 1 source path')
    if actual != {**inherited, **changes}:
        raise ValueError('Active source differs from the sealed retrieval phase')


def verify(root):
    root = Path(root).resolve(strict=True)
    value = read_json(root / MANIFEST)
    if value.get('version') != 'retrieval011-phase1-v1' or value.get('parent_commit') != PARENT_COMMIT:
        raise ValueError('Unknown retrieval phase identity')
    if value.get('parent_manifest') != fingerprint(root / PARENT_MANIFEST):
        raise ValueError('Preserved repair010 manifest differs')
    inherited = parent_inventory(root)
    excluded = {*METADATA, 'evidence/ci009/manifest.json', PARENT_MANIFEST, MANIFEST}
    actual = {name: row for name, row in inventory(root).items() if name not in excluded}
    verify_delta(actual, inherited, value['files'])
    return {'passed': True, 'phase': 'retrieval011-phase1', 'files': len(value['files']),
            'historical_seals_and_archive_verified': True,
            'scope': 'Byte consistency and preserved evidence; retrieval measurements and repair outcomes have separate receipts'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Retrieval phase verification failed: ' + str(error) + '\n')
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
