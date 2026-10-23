"""Positive control (infrastructure only): are the F024 pilot gold hunks expressible as SEARCH/REPLACE
against the region text the oracle prompts showed? Gold is read here, never model-visible.

Usage: python -m scripts.search_replace_control025 PACKAGE_JSON TEST_PARQUET
"""
import json
import re
import sys


def parse_hunks(patch):
    """(path, old_text, new_text) per hunk, where old = context + removed lines."""
    out, path = [], None
    for line in patch.splitlines(True):
        if line.startswith('+++ b/'):
            path = line[6:].strip()
        elif line.startswith('@@'):
            out.append([path, [], []])
        elif out and line[:1] in ' -+' and not line.startswith('--- '):
            if line[0] in ' -':
                out[-1][1].append(line[1:])
            if line[0] in ' +':
                out[-1][2].append(line[1:])
    return [(p, ''.join(o), ''.join(n)) for p, o, n in out]


def region_text(job, path):
    """Join the numbered regions of one file; a gap in line numbers breaks contiguity."""
    out, previous = [], None
    for region in json.loads(job['messages'][1]['content'])['original_source']:
        if region['path'] != path:
            continue
        if previous is not None and region['start_line'] != previous + 1:
            out.append('\x00')  # unseen lines between regions
        out.extend(re.sub(r'^\d+: ?', '', l, count=1) for l in region['numbered_original_source'].splitlines(True))
        previous = region['end_line']
    return ''.join(out)


def expressible(job, path, old):
    text = region_text(job, path)
    return text.count(old) == 1 if old.strip() else False


def main(package, parquet):
    import pyarrow.parquet as pq
    jobs = {j['job_id']: j for j in json.load(open(package))['jobs']}
    gold = {r['instance_id']: r['patch'] for r in pq.read_table(parquet).to_pylist()}
    report = []
    for instance in ('django__django-11772', 'pytest-dev__pytest-8124'):
        job = jobs[instance + '/oracle/base/t1']
        for path, old, new in parse_hunks(gold[instance]):
            report.append({'instance': instance, 'path': path, 'old_lines': old.count('\n'),
                           'expressible': expressible(job, path, old)})
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:3])
