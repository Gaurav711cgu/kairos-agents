"""Deterministic edit-pipeline check on development cases; no model involved.

For each case of an existing localization receipt: (1) the gold patch, limited
to approved-prefix Python files, must apply cleanly to the pinned source; (2)
after an arm selects regions from the issue alone, the gold edit is rendered in
the source-handle protocol and replayed through the production validator. A
rejection other than "outside selected context" is a pipeline fault, because
the edit is known correct. Gold material is read only after selection.
"""
import argparse
import json
import re
import sys
import types
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.localization_dev024 import PREFIXES, arms, sha, targets  # noqa: E402

VERSION = 'patch-roundtrip024-v1'
OUTSIDE = 'outside issue-only selected context'
# Declared protocol bounds (coding_data014.patch_scope, patches.apply_patch), not defects.
SCOPE_LIMITS = ('Outside two-file/', 'Unsupported source operation', 'Creation/deletion', 'Patch must change one to three text files', 'changed lines')


def prefix_patch(patch, prefix):
    """Keep only diff sections for approved-prefix Python files."""
    sections = re.split(r'(?m)^(?=diff --git )', patch)
    return ''.join(s for s in sections if s.startswith('diff --git a/') and s.split()[2][2:] in targets(s, prefix))


def classify(error):
    text = str(error)
    if OUTSIDE in text:
        return 'outside_selected_context'
    if any(limit in text for limit in SCOPE_LIMITS):
        return 'scope_limit'
    return 'pipeline_fault: ' + re.sub(r'\d+', 'N', type(error).__name__ + ': ' + text)[:160]


def main():
    from kairos_api.investigations.sandbox import Workspace
    from scripts.coding_actions014 import convert_action
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True, help='localization_dev024 receipt naming the cases')
    parser.add_argument('--parquet', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Result receipts are immutable; choose a new output path')
    import pyarrow.parquet as pq
    receipt = json.loads(args.receipt.read_text())
    wanted = {c['instance_id']: c for c in receipt['cases']}
    rows = {r['instance_id']: r for r in pq.read_table(args.parquet, columns=['instance_id', 'repo', 'problem_statement', 'patch']).to_pylist() if r['instance_id'] in wanted}
    selectors = arms()
    results = []
    for identifier, case in wanted.items():
        row, prefix = rows[identifier], PREFIXES[case['repository']]
        source = json.loads((args.cache / identifier / 'source.json').read_text())
        if source['archive_sha256'] != case['archive_sha256'] or source['revision'] != case['revision']:
            raise ValueError('Cached source differs from the localization receipt')
        directory = args.cache / identifier
        registry = types.SimpleNamespace(verify=lambda _: None, directory=lambda _: directory)
        record = {'instance_id': identifier, 'arms': {}}
        workspace = Workspace(registry, {'id': identifier, 'issue': row['problem_statement'], 'approved_prefix': prefix, 'entry_files': [], 'entry_lines': {}})
        try:
            selected = {arm: select(workspace) for arm, select in selectors.items()}
            # Gold material enters only after every arm has selected.
            gold = prefix_patch(row['patch'], prefix)
            try:
                workspace.propose(gold)
                record['gold_apply'] = 'clean'
            except Exception as error:  # any rejection of a known patch is recorded, never hidden
                record['gold_apply'] = classify(error)
            for arm, regions in selected.items():
                try:
                    action, _ = convert_action(workspace, gold, regions, anchor_policy='captured-neighbor-coalesced-v3')
                    record['arms'][arm] = {'outcome': 'roundtrip_ok', 'edits': len(action['edits'])}
                except Exception as error:
                    record['arms'][arm] = {'outcome': classify(error)}
        finally:
            workspace.close()
        results.append(record)
        print(json.dumps({'case': identifier, 'gold': record['gold_apply'], **{a: v['outcome'][:40] for a, v in record['arms'].items()}}), flush=True)
    summary = {'gold_clean_apply': {'k': sum(r['gold_apply'] == 'clean' for r in results), 'n': len(results)}}
    for arm in selectors:
        outcomes = {}
        for r in results:
            outcomes[r['arms'][arm]['outcome']] = outcomes.get(r['arms'][arm]['outcome'], 0) + 1
        summary[arm] = outcomes
    report = {'version': VERSION, 'scope': 'Edit-pipeline correctness on known-correct development edits; not model output, not repair',
              'localization_receipt_sha256': sha(args.receipt), 'implementation_sha256': sha(__file__),
              'anchor_policy': 'captured-neighbor-coalesced-v3', 'model_calls': 0, 'docker_runs': 0,
              'summary': summary, 'cases': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
