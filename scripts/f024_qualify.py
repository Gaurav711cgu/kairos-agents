"""Qualify the F024 pilot cases with the reviewed qualify014 machinery; no inference.

Inert without --execute. Execution needs Docker with the pinned local images
(pull never, network none) and, for pinned full source, --allow-source-download.
Receipts are immutable and written outside the repository.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = {'django': 'django/django', 'pytest-dev': 'pytest-dev/pytest'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalize(row):
    """qualify014 reads test-id fields as JSON strings, as in unseen023's normalized rows."""
    return {**row, **{key: json.dumps(list(row[key])) for key in ('FAIL_TO_PASS', 'PASS_TO_PASS') if not isinstance(row[key], str)}}


def main():
    parser = argparse.ArgumentParser()
    for name in ['package', 'parquet', 'output', 'storage-roots']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--allow-source-download', action='store_true')
    parser.add_argument('--capacity-gib', type=int, default=None, help='approved aggregate storage cap for this run; reserve unchanged')
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT))
    import pyarrow.parquet as pq
    import scripts.qualify014 as q
    package = json.loads(args.package.read_text())
    identifiers = sorted({job['instance_id'] for job in package['jobs']})
    rows = {r['instance_id']: normalize(r) for r in pq.read_table(args.parquet).to_pylist() if r['instance_id'] in identifiers}
    from scripts.localization_dev024 import PREFIXES, targets
    entries = [{'instance_id': i, 'repository': REPOSITORY[i.split('__')[0]], 'base_commit': rows[i]['base_commit'], 'split': 'development',
                'status': 'eligible', 'source_scope': {'approved_prefix': PREFIXES[rows[i]['repo']], 'entry_files': targets(rows[i]['patch'], PREFIXES[rows[i]['repo']])},
                'provenance': 'F024 pilot development case. Reference-derived entry files are registry metadata for qualification only and never reach inference.'}
               for i in identifiers]
    if any(rows[e['instance_id']]['repo'] != e['repository'] for e in entries):
        raise ValueError('Package case and dataset repository differ')
    deps = q.dependencies(PROJECT)
    if args.capacity_gib is not None:
        q.CAPACITY = args.capacity_gib * 1024 ** 3
    inputs = {'package': sha(args.package), 'dataset': sha(args.parquet), 'implementation': sha(__file__), 'storage_capacity_bytes': q.CAPACITY,
              'dependencies': {name: sha(PROJECT / name) for name in q.MODULE_FILES}}
    binding = hashlib.sha256(q.encoded(inputs)).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    q.immutable(args.output / 'binding.json', {'binding': binding, 'inputs': inputs, 'cases': identifiers,
                                               'scope': 'Baseline/reference qualification only; no inference'})
    if not args.execute:
        print(json.dumps({'status': 'prepared_not_executed', 'binding': binding, 'cases': identifiers}))
        return
    roots = json.loads(args.storage_roots.read_text())['roots']
    q.storage_guard(roots, 512 * 1024 ** 2)
    q.inspect_images({e['repository'] for e in entries})
    receipts = [q.execute_case(e, rows[e['instance_id']], args.output, roots, binding, args.allow_source_download, deps) for e in entries]
    summary = {'binding': binding, 'model_calls': 0, 'qualified': {r['instance_id']: r['qualified'] for r in receipts},
               'reasons': {r['instance_id']: r.get('reason') for r in receipts}}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=1, sort_keys=True))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
