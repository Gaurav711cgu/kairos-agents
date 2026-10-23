"""Independently score F025 repair-loop chains; never invokes a model.

Each chain record is hash-checked, then its final reply is re-parsed and re-applied to the
pinned qualified source within the recorded regions; the recorded patch is never trusted.
An accepted re-derivation runs in the pinned local image and is judged against the qualified
baseline exactly as f024_score does. Synthetic chains are reported, not scored. Inert without --execute.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def load_chains(roots, package):
    """Verified dev chains by chain_id, plus the synthetic chain ids that are skipped.

    A record hash alone can be recomputed by whoever edits the record, so binding and regions are
    also checked against the package that was shipped to Colab.
    """
    from scripts.f024_colab import digest
    binding = digest(package)
    shipped = {c['chain_id']: [{k: r[k] for k in ['path', 'start_line', 'end_line']} for r in c['regions']] for c in package['chains']}
    chains, synthetic = {}, []
    for root in roots:
        for path in sorted((root / 'chains').rglob('*.json')):
            record = json.loads(path.read_text())
            chain_id = record['chain_id']
            if path != root / 'chains' / (chain_id + '.json'):
                raise ValueError(f'{path}: chain_id does not match its file')
            if digest({k: v for k, v in record.items() if k != 'record_sha256'}) != record['record_sha256']:
                raise ValueError(f'{chain_id}: record_sha256 mismatch')
            receipts = root / 'receipts' / (chain_id + '.jsonl')
            if not receipts.exists() or hashlib.sha256(receipts.read_bytes()).hexdigest() != record['receipts_sha256']:
                raise ValueError(f'{chain_id}: receipts_sha256 mismatch')
            if record.get('binding') != binding or record.get('regions') != shipped.get(chain_id):
                raise ValueError(f'{chain_id}: binding or regions differ from the shipped package')
            parts = chain_id.split('/')
            if parts[0] == 'synthetic':
                synthetic.append(chain_id)
            elif parts[0] == 'dev' and len(parts) == 3:
                if chain_id in chains:
                    raise ValueError(f'{chain_id}: duplicate chain')
                entries = [json.loads(line) for line in receipts.read_text().splitlines() if line.strip()]
                runs = [r for r in entries if r.get('kind') == 'run']
                exit_code = re.match(r'RUN exit (-?\d+)', runs[-1]['feedback'] or '') if runs else None
                # None only when no repro ran; a timed-out or refused-after-run repro is 'no_exit', never a pass
                last = None if not runs else int(exit_code[1]) if exit_code else 'no_exit'
                chains[chain_id] = {**record, 'last_run_exit': last, 'final_reply': patch_reply(root, chain_id, entries, record)}
            else:
                raise ValueError(f'{chain_id}: unknown chain kind')
    # a dev chain that halted without a record still counts in the denominator
    missing = sorted(c['chain_id'] for c in package['chains'] if c['chain_id'].startswith('dev/') and c['chain_id'] not in chains)
    chains.update({chain_id: {'chain_id': chain_id, 'status': 'not_run'} for chain_id in missing})
    return chains, sorted(synthetic)


def patch_reply(root, chain_id, entries, record):
    """The reply whose blocks made the accepted patch: after a self_test review it precedes the last reply (F025 run 6).

    Found by the accepted receipt's reply hash, so the hash-chained receipts still vouch for the text.
    """
    want = next((e.get('reply_sha256') for e in entries if e.get('kind') == 'accepted'), None)
    for capture in sorted((root / 'captures' / chain_id).glob('c*.json')):
        text = json.loads(capture.read_text()).get('result', {}).get('text')
        if want and isinstance(text, str) and hashlib.sha256(text.encode()).hexdigest() == want:
            return text
    return record['final_reply']


def summarize(results, chains):
    """Best-of-n views. ``fair_pick`` uses only evidence visible during the run (accepted, and the model's own
    last repro script exited 0 if it ran one); ``pass_at_2`` needs the hidden results and is labelled as such."""
    verified = {r['chain_id']: r['verified_repair'] for r in results}
    cases = {}
    for chain_id in sorted(chains, key=lambda c: (c.split('/')[1], int((re.search(r'-s(\d+)$', c) or [0, 0])[1]))):
        cases.setdefault(chain_id.split('/')[1], []).append(chain_id)
    fair = {}
    for case, ids in cases.items():
        pick = next((c for c in ids if chains[c].get('status') == 'accepted' and chains[c].get('last_run_exit') in (None, 0)), None)
        fair[case] = {'sample': None if pick is None else int((re.search(r'-s(\d+)$', pick) or [0, 0])[1]),
                      'verified': bool(pick and verified.get(pick))}
    return {'pass_at_2': sum(any(verified.get(c) for c in ids) for ids in cases.values()), 'pass_at_2_label': 'oracle_selection',
            'fair_pick': fair, 'fair_pick_verified': sum(v['verified'] for v in fair.values())}


def main():  # pragma: no cover - Docker execution is approval-gated
    parser = argparse.ArgumentParser()
    for name in ['results', 'package', 'qualification', 'parquet', 'storage-roots', 'output', 'admission-module']:
        parser.add_argument('--' + name, type=Path, required=True, action='append' if name == 'results' else None)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--work-root', type=Path, default=None, help='disposable work trees; keep outside Finder-visible folders')
    parser.add_argument('--capacity-gib', type=int, default=None, help='approved aggregate storage cap for this run; reserve unchanged')
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT))
    chains, synthetic = load_chains(args.results, json.loads(args.package.read_text()))
    if not args.execute:
        print(json.dumps({'status': 'prepared_not_executed', 'chains': {k: v['status'] for k, v in sorted(chains.items())},
                          'skipped_synthetic': synthetic}, indent=1))
        return
    import pyarrow.parquet as pq
    import scripts.qualify014 as q
    if args.capacity_gib is not None:
        q.CAPACITY = args.capacity_gib * 1024 ** 3
    from scripts.search_replace025 import apply_blocks, parse_blocks
    from kairos_api.investigations.sandbox import Workspace
    from scripts.localization_dev024 import load_module
    admit = load_module('frozen_comparison023', args.admission_module).admit_receipt
    qualifier, Registry, tree_hash, _ = q.dependencies(PROJECT)
    from scripts.f024_qualify import normalize
    identifiers = {chain_id.split('/')[1] for chain_id in chains}
    rows = {r['instance_id']: normalize(r) for r in pq.read_table(args.parquet).to_pylist() if r['instance_id'] in identifiers}
    roots = json.loads(args.storage_roots.read_text())['roots']
    q.inspect_images({rows[i]['repo'] for i in rows})
    binding = json.loads((args.qualification / 'binding.json').read_text())['binding']
    results = []
    for identifier in sorted(identifiers):
        attempts = {k: v for k, v in chains.items() if k.split('/')[1] == identifier}
        try:
            case = admit(args.qualification, identifier, binding, qualifier)['case']  # rechecks every artifact hash
        except ValueError as error:
            results += [{'chain_id': k, 'model_calls': 0, 'verified_repair': False, 'outcome': 'case_not_qualified', 'reason': str(error)} for k in attempts]
            continue
        work = (args.work_root or args.output / 'work') / identifier  # one pinned download per case, shared by its chains
        work.mkdir(parents=True)
        row = rows[identifier]
        source, _ = q.pinned_source(row, work, roots, True, tree_hash)
        if tree_hash(source) != case['source_digest']:
            raise ValueError('Scoring source differs from the qualified snapshot')
        with q.counted_temporary(work / 'temporary'):
            script, _ = qualifier.verifier(row, source)
        if hashlib.sha256((row['test_patch'] + script).encode()).hexdigest() != case['verification_digest']:
            raise ValueError('Verification material differs from qualification')
        directory = work / 'registry/cases' / identifier
        directory.mkdir(parents=True)
        source.rename(directory / 'source')
        for name, text in [('reference.patch', row['patch']), ('test.patch', row['test_patch']), ('verify.py', script)]:
            (directory / name).write_text(text)
        q.immutable(work / 'registry.json', {'version': 'repository-cases-v1', 'cases': [case]})
        baseline = q.load(args.qualification / 'cases' / identifier / 'baseline.json')['result']
        for chain_id, record in sorted(attempts.items()):
            result = {'chain_id': chain_id, 'model_calls': 0, 'verified_repair': False}
            if record['status'] != 'accepted':
                results.append({**result, 'outcome': 'loop_' + record['status']})
                continue
            workspace = Workspace(Registry(work / 'registry.json', work / 'registry'), case)
            try:
                verdict = apply_blocks(workspace, parse_blocks(record['final_reply']), record['regions'] + record.get('read_regions', []))
                if not verdict['accepted']:
                    results.append({**result, 'outcome': 'revalidation_rejected', 'reason': verdict['reason']})
                    continue
                if verdict['patch'] != record['patch']:
                    results.append({**result, 'outcome': 'patch_mismatch'})
                    continue
                check = q.captured_check(args.output / 'checks' / (chain_id.replace('/', '__') + '.json'), 'candidate',
                                         lambda: workspace.checks(timeout=120), binding, roots, q.tree_bytes(workspace.root))
                judged = q.check_qualified(baseline, check, qualifier)
                outcome = 'verified_repair' if judged['qualified'] else judged['status']
                extra = {}
                # Same rule as f024_score: the sandbox ran but executed no tests, so the candidate broke import.
                if outcome == 'environment_failure' and check.get('environment_error') is False:
                    outcome, extra = 'candidate_execution_failure', {'candidate_stderr_tail': str(check.get('stderr', ''))[-800:]}
                results.append({**result, 'outcome': outcome, 'verified_repair': judged['qualified'], 'checks': judged, **extra})
            finally:
                workspace.close()
        if tree_hash(directory / 'source') != case['source_digest']:
            raise ValueError('Original source changed during scoring')
    q.immutable(args.output / 'scores.json', {'results': results, 'model_calls': 0, 'verified_repairs': sum(r['verified_repair'] for r in results),
                                              'attempts': len(results), 'skipped_synthetic': synthetic, **summarize(results, chains)})
    print(json.dumps({r['chain_id']: r['outcome'] for r in results}, indent=1))


if __name__ == '__main__':
    main()
