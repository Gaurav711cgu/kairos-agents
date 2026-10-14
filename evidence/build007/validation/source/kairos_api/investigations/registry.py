"""Server-owned case registry with frozen provenance and source fingerprints."""
import hashlib
import json
import os
import shutil
from pathlib import Path
from fastapi import HTTPException
from kairos_api.model_runtime import digest

ROOT = Path(__file__).resolve().parents[2]


def tree_hash(root):
    items = [(str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest())
             for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()]
    return hashlib.sha256(json.dumps(items, separators=(',', ':')).encode()).hexdigest()


class CaseRegistry:
    def __init__(self, manifest=None, runtime=None):
        self.path = Path(manifest or ROOT/'cases/investigations.json')
        self.runtime = Path(runtime or os.environ.get('KAIROS_INVESTIGATION_ROOT', ROOT/'.runtime/investigations')).resolve()

    def manifest(self):
        if not self.path.exists():
            return {'version': 'repository-cases-v1', 'cases': [], 'selection': {}}
        return json.loads(self.path.read_text())

    def cases(self):
        return self.manifest()['cases']

    def get(self, identifier):
        case = next((c for c in self.cases() if c['id'] == identifier), None)
        if not case:
            raise HTTPException(404, 'Registered case not found')
        if not case.get('qualified'):
            raise HTTPException(409, 'Case has not passed independent preflight')
        return case

    def directory(self, case):
        identifier = case['id']
        if not identifier or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in identifier):
            raise ValueError('Invalid registry identifier')
        return self.runtime/'cases'/identifier

    def fingerprint(self, case):
        return digest({'case': case, 'registry_version': self.manifest()['version']})

    def verify(self, case):
        directory = self.directory(case)
        if shutil.disk_usage(self.runtime).free<4*1024**3:
            raise ValueError('Storage reserve below 4GiB; investigation refused')
        size=sum(p.stat().st_size for p in self.runtime.rglob('*') if p.is_file() and not p.is_symlink())
        if size>6*1024**3: raise ValueError('Investigation runtime exceeds 6GiB storage budget')
        if tree_hash(directory/'source') != case['source_digest']:
            raise ValueError('Source snapshot mismatch')
        reference = hashlib.sha256((directory/'reference.patch').read_bytes()).hexdigest()
        verification = (directory/'test.patch').read_text()
        if (directory/'verify.py').exists():
            verification += (directory/'verify.py').read_text()
        if reference != case['reference_digest'] or hashlib.sha256(verification.encode()).hexdigest() != case['verification_digest']:
            raise ValueError('Verification material mismatch')
