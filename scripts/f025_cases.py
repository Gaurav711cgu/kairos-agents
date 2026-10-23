"""F025 run-3 case selection: SWE-bench Verified, development bucket, unexposed, pinned-image version.

Verified excludes tasks annotators judged underspecified; the F024/F025 dev cases were not in it.
"""
import argparse
import json
from pathlib import Path

from scripts.localization_dev024 import bucket


def select_cases(rows, verified, exposed, repo='django/django', version='3.1'):
    return sorted(r['instance_id'] for r in rows
                  if r['repo'] == repo and r['version'] == version and r['instance_id'] in verified
                  and bucket(r['instance_id']) == 'development' and r['instance_id'] not in exposed)


def qualify_input(ids):
    """The only shape scripts/f024_qualify.py reads from its --package."""
    return {'jobs': [{'instance_id': i} for i in ids]}


def main():  # pragma: no cover
    import pyarrow.parquet as pq
    parser = argparse.ArgumentParser()
    for name in ['parquet', 'verified', 'exposed', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    rows = pq.read_table(args.parquet, columns=['instance_id', 'repo', 'version']).to_pylist()
    ids = select_cases(rows, set(json.loads(args.verified.read_text())), set(args.exposed.read_text().split()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(qualify_input(ids), indent=1))
    print(json.dumps(ids))


if __name__ == '__main__':
    main()
