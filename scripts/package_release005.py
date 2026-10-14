"""Package genuine public captures and lossless historical raw measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/build005'


def fingerprint(path):
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'sha256': sha, 'bytes': path.stat().st_size}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def published_captures():
    destination = ROOT / 'dashboard/evidence'
    (destination / 'records').mkdir(parents=True, exist_ok=True)
    (destination / 'blobs').mkdir(exist_ok=True)
    cohorts = [json.loads((ROOT / 'dashboard/lib' / name).read_text()) for name in ('investigation-cohort.json', 'study004-cohort.json')]
    identifiers = [identifier for cohort in cohorts for identifier in cohort['ids']]
    assert len(identifiers) == len(set(identifiers)) == 48
    originals = {}
    for version in ('003', '004'):
        for path in (ROOT / ('evidence/build' + version)).rglob('*.json'):
            try:
                record = json.loads(path.read_text())
            except ValueError:
                continue
            if isinstance(record, dict) and record.get('id') in identifiers and 'steps' in record:
                originals.setdefault(record['id'], path)
    assert set(originals) == set(identifiers), 'Missing genuine cohort records'
    manifest = {'version': 'published-evidence-v1', 'records': {}, 'blobs': {}}

    def blob(key, data):
        assert len(key) == 64 and all(char in '0123456789abcdef' for char in key)
        assert hashlib.sha256(data).hexdigest() == key, 'Captured-byte mismatch: ' + key
        path = destination / 'blobs' / key
        if path.exists():
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
        manifest['blobs'][key] = {'path': 'blobs/' + key, **fingerprint(path)}

    for identifier in identifiers:
        source = originals[identifier]
        record = json.loads(source.read_bytes())
        assert record['published'] and record['integrity']['verified']
        assert record['status'] not in ('queued', 'running')
        assert not {'tenant_id', 'command_key', 'command_digest', 'lease_owner', 'lease_token'} & record.keys()
        references = set()
        for expected, step in enumerate(record['steps'], 1):
            assert step['seq'] == expected
            for kind in ('request', 'result'):
                capture = step[kind]
                if capture is None:
                    continue
                key = capture['sha256']
                data = (ROOT / '.runtime/blobs' / key).read_bytes()
                assert json.loads(data) == capture['body']
                blob(key, data)
                references.add(key)
        for artifact in record['artifacts']:
            key = artifact['sha256']
            data = (ROOT / '.runtime/blobs' / key).read_bytes()
            assert len(data) == artifact['bytes']
            blob(key, data)
            references.add(key)
        registry_version = record.get('registry_version', 'repository-cases-v1')
        blob(record['task_digest'], canonical({'case': record['task_snapshot'], 'registry_version': registry_version}))
        blob(record['config_digest'], canonical(record['config_snapshot']))
        target = destination / 'records' / (identifier + '.json')
        target.write_bytes(source.read_bytes())
        manifest['records'][identifier] = {
            'path': 'records/' + identifier + '.json', **fingerprint(target),
            'task_snapshot_blob': record['task_digest'], 'config_snapshot_blob': record['config_digest'],
            'registry_version': registry_version,
        }
    path = destination / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    receipt = {'passed': True, 'records': len(manifest['records']), 'blobs': len(manifest['blobs']),
               'manifest': fingerprint(path), 'recorded_ids': identifiers,
               'scope': 'Published captured records and exact artifact bytes. No fixture inference, model execution, invented authentication or immutable-history claim.'}
    (OUT / 'published-package.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'published_records': receipt['records'], 'exact_blobs': receipt['blobs']}))


def raw_measurements():
    old = ROOT / 'evidence/build004'
    names = sorted(path for path in old.rglob('*') if path.is_file() and
                   (path.suffix == '.jsonl' or path.name in {'capacity-pooled-run.txt', 'capacity-run.txt'}))
    archive = OUT / 'historical-raw.tar.gz'
    members = {str(path.relative_to(ROOT)): fingerprint(path) for path in names}
    with tarfile.open(archive, 'w:gz', compresslevel=6) as package:
        for path in names:
            package.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    with tarfile.open(archive, 'r:gz') as package:
        seen = set()
        for member in package:
            assert member.isfile() and member.name in members and member.name not in seen
            with package.extractfile(member) as stream:
                sha = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert sha == members[member.name]['sha256'] and member.size == members[member.name]['bytes']
            seen.add(member.name)
        assert seen == set(members)
    receipt = {'passed': True, 'archive': fingerprint(archive), 'members': members,
               'original_bytes': sum(value['bytes'] for value in members.values()),
               'scope': 'Lossless compressed publication copy. Original files and frozen manifests remain unchanged locally.'}
    (OUT / 'historical-raw-index.json').write_text(json.dumps(receipt, indent=2) + '\n')
    ignore = ROOT / '.gitignore'
    marker = '# Build005: raw measurements are distributed losslessly in historical-raw.tar.gz.'
    current = ignore.read_text()
    if marker not in current:
        ignore.write_text(current + '\n' + marker + '\n' + ''.join('/' + name + '\n' for name in members))
    print(json.dumps({'raw_files': len(members), 'original_bytes': receipt['original_bytes'], 'archive_bytes': receipt['archive']['bytes']}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['captures', 'raw', 'all'], default='all', nargs='?')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.mode in ('captures', 'all'):
        published_captures()
    if args.mode in ('raw', 'all'):
        raw_measurements()


if __name__ == '__main__':
    main()
