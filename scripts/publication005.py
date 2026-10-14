"""Prepare a clean, byte-indexed source snapshot without private runtime or publication."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/build005'
PRIVATE_PREFIXES = ('.git/', '.runtime/', '.venv/', 'node_modules/', 'dashboard/node_modules/',
    'dashboard/.next', 'dashboard/.playwright', 'dashboard/playwright/.auth/', 'dashboard/test-results/',
    'dashboard/playwright-report/', '__pycache__/')


def fingerprint(path):
    with path.open('rb') as stream:
        value = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'sha256': value, 'bytes': path.stat().st_size}


def source_names():
    result = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    names = sorted(set(result.decode().split('\0')) - {''})
    for name in names:
        path = ROOT / name
        if not path.is_file() or path.is_symlink() or name.startswith(PRIVATE_PREFIXES):
            continue
        if any(part in {'__pycache__', '.pytest_cache', '.DS_Store'} for part in path.parts):
            continue
        if path.name.startswith('.env') and path.name != '.env.example':
            continue
        if name.startswith('evidence/build005/') and path.name in {'publication.tar.gz', 'publication-index.json', 'publication-receipt.json'}:
            continue
        if path.suffix in {'.pyc', '.pem', '.db', '.sqlite', '.gguf'}:
            continue
        if path.stat().st_size >= 100 * 1024**2:
            raise ValueError('Oversized source member; use lossless evidence archive: ' + name)
        yield name


def private_values(extra_runtime=None):
    values = set()
    for name in ('.env.kairos.local', '.runtime/identity.env'):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if '=' not in line or line.startswith('#'):
                continue
            key, value = line.split('=', 1)
            if any(part in key for part in ('TOKEN', 'SECRET', 'PASSWORD', 'DATABASE_URL')) and len(value) >= 20:
                values.add(value.encode())
    path = ROOT / '.runtime/identity.local.json'
    if path.exists():
        data = json.loads(path.read_text())
        for key in ('admin_password', 'client_secret'):
            if len(data.get(key, '')) >= 20:
                values.add(data[key].encode())
        for account in data.get('accounts', []):
            if len(account.get('password', '')) >= 20:
                values.add(account['password'].encode())
    if extra_runtime:
        runtime = Path(extra_runtime).resolve()
        for name in ('application.env', 'postgres.env', 'keycloak.env'):
            path = runtime / name
            if path.exists():
                for line in path.read_text().splitlines():
                    if '=' not in line or line.startswith('#'):
                        continue
                    key, value = line.split('=', 1)
                    if any(part in key for part in ('TOKEN', 'SECRET', 'PASSWORD', 'DATABASE_URL')) and len(value) >= 20:
                        values.add(value.encode())
        path = runtime / 'identity.local.json'
        if path.exists():
            data = json.loads(path.read_text())
            for key in ('admin_password', 'client_secret'):
                if len(data.get(key, '')) >= 20:
                    values.add(data[key].encode())
            for account in data.get('accounts', []):
                if len(account.get('password', '')) >= 20:
                    values.add(account['password'].encode())
    return values


def prepare(destination, extra_runtime=None):
    destination = destination.absolute()
    if destination.exists():
        raise ValueError('Snapshot destination already exists; preserve it and choose a new directory')
    if not destination.parent.exists():
        destination.parent.mkdir(parents=True)
    names = list(source_names())
    sensitive = private_values(extra_runtime)
    destination.mkdir()
    entries = {}
    for name in names:
        source, target = ROOT / name, destination / name
        if source.stat().st_size <= 32 * 1024**2 and source.suffix not in {'.png', '.jpg', '.gz', '.zip', '.pdf'}:
            raw = source.read_bytes()
            if any(secret in raw for secret in sensitive):
                raise ValueError('Private value detected in publication member: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        entries[name] = fingerprint(target)
    assert not (destination / '.runtime').exists() and not (destination / '.venv').exists()
    assert not (destination / 'dashboard/node_modules').exists()
    receipt = {'version': 'publication-snapshot-v1', 'files': entries, 'total_bytes': sum(item['bytes'] for item in entries.values()),
        'private_runtime_present': False, 'dependencies_present': False, 'known_private_values_found': False,
        'scope': 'Clean uncommitted source snapshot and public evidence. No GitHub push, hosting or immutable-provenance claim.'}
    OUT.mkdir(exist_ok=True)
    (OUT / 'publication-index.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'files': len(entries), 'bytes': receipt['total_bytes'], 'destination': str(destination)}))


def bundle(destination):
    destination = destination.resolve()
    receipt = json.loads((OUT / 'publication-index.json').read_text())
    for name, expected in receipt['files'].items():
        if fingerprint(destination / name) != expected:
            raise ValueError('Acceptance snapshot source changed: ' + name)
    archive = OUT / 'publication.tar.gz'
    with tarfile.open(archive, 'w:gz') as package:
        for name in receipt['files']:
            package.add(destination / name, arcname='kairos/' + name, recursive=False)
    print(json.dumps({'archive': str(archive), **fingerprint(archive)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'bundle'])
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--private-runtime', type=Path, help='Also scan known generated reviewer credentials; values are never printed')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.destination, args.private_runtime)
    else:
        bundle(args.destination)


if __name__ == '__main__':
    main()
