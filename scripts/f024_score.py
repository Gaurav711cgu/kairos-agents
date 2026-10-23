"""Independently score F024 captures; never invokes a model.

Per (case, context, arm) only the last captured turn is scored. Each edit is parsed
and rendered by ``validate021`` against the captured regions, then an accepted patch
runs in the pinned local image (pull never, network none) and is judged against the
qualified baseline exactly as unseen023 scoring did. Inert without --execute.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def final_attempts(jobs, captures):
    """Map (case, context, arm) to the last job of that chain and its capture status."""
    plan = {}
    for job in sorted(jobs, key=lambda j: j['turn']):
        capture = captures.get(job['job_id'])
        plan[(job['instance_id'], job['context'], job['arm'])] = (job['job_id'], 'not_captured' if capture is None else capture['status'])
    return plan


def main():  # pragma: no cover - Docker execution is approval-gated
    parser = argparse.ArgumentParser()
    for name in ['package', 'results', 'qualification', 'parquet', 'storage-roots', 'output', 'admission-module']:
        parser.add_argument('--' + name, type=Path, required=True, action='append' if name in {'package', 'results'} else None)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--work-root', type=Path, default=None, help='disposable work trees; keep outside Finder-visible folders')
    parser.add_argument('--capacity-gib', type=int, default=None, help='approved aggregate storage cap for this run; reserve unchanged')
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT))
    import pyarrow.parquet as pq
    import scripts.qualify014 as q
    if args.capacity_gib is not None:
        q.CAPACITY = args.capacity_gib * 1024 ** 3
    from scripts.f024 import classify
    from scripts.feedback_turn021 import validate021
    from kairos_api.investigations.sandbox import Workspace
    jobs = [j for p in args.package for j in json.loads(p.read_text())['jobs']]
    captures = {}
    for root in args.results:
        for path in (root / 'captures').rglob('*.json'):
            record = json.loads(path.read_text())
            captures[record['job_id']] = record
    plan = final_attempts(jobs, captures)
    if not args.execute:
        print(json.dumps({'status': 'prepared_not_executed', 'attempts': {'/'.join(k): v for k, v in plan.items()}}, indent=1))
        return
    from scripts.localization_dev024 import load_module
    admit = load_module('frozen_comparison023', args.admission_module).admit_receipt
    qualifier, Registry, tree_hash, _ = q.dependencies(PROJECT)
    from scripts.f024_qualify import normalize
    rows = {r['instance_id']: normalize(r) for r in pq.read_table(args.parquet).to_pylist() if r['instance_id'] in {k[0] for k in plan}}
    roots = json.loads(args.storage_roots.read_text())['roots']
    q.inspect_images({rows[i]['repo'] for i in rows})
    binding = json.loads((args.qualification / 'binding.json').read_text())['binding']
    by_id, results = {j['job_id']: j for j in jobs}, []
    for identifier in sorted({k[0] for k in plan}):
        attempts = {key: value for key, value in plan.items() if key[0] == identifier}
        try:
            case = admit(args.qualification, identifier, binding, qualifier)['case']  # rechecks every artifact hash
        except ValueError as error:
            results += [{'job_id': job_id, 'model_calls': 0, 'verified_repair': False, 'outcome': 'case_not_qualified', 'reason': str(error)} for job_id, _ in attempts.values()]
            continue
        work = (args.work_root or args.output / 'work') / identifier  # one pinned download per case, shared by its attempts
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
        for (_, context, arm), (job_id, status) in sorted(attempts.items()):
            result = {'job_id': job_id, 'model_calls': 0, 'verified_repair': False}
            if status != 'captured':
                results.append({**result, 'outcome': status})
                continue
            workspace = Workspace(Registry(work / 'registry.json', work / 'registry'), case)
            try:
                payload = json.loads(by_id[job_id]['messages'][1]['content'])
                regions = [workspace.read_original(b['path'], b['start_line'], b['end_line']) for b in payload['original_source']]
                verdict = validate021(workspace, captures[job_id]['result']['text'], regions)
                if not verdict['accepted']:
                    results.append({**result, 'outcome': classify(verdict), 'reason': verdict['reason']})
                    continue
                check = q.captured_check(args.output / 'checks' / (job_id.replace('/', '__') + '.json'), 'candidate',
                                         lambda: workspace.checks(timeout=120), binding, roots, q.tree_bytes(workspace.root))
                judged = q.check_qualified(baseline, check, qualifier)
                outcome = 'verified_repair' if judged['qualified'] else judged['status']
                extra = {}
                # Baseline and reference already ran in this image; a sandbox that ran but executed no
                # tests means the candidate itself broke import or collection, not the environment.
                if outcome == 'environment_failure' and check.get('environment_error') is False:
                    outcome, extra = 'candidate_execution_failure', {'candidate_stderr_tail': str(check.get('stderr', ''))[-800:]}
                results.append({**result, 'outcome': outcome, 'verified_repair': judged['qualified'], 'checks': judged, **extra})
            finally:
                workspace.close()
        if tree_hash(directory / 'source') != case['source_digest']:
            raise ValueError('Original source changed during scoring')
    q.immutable(args.output / 'scores.json', {'results': results, 'model_calls': 0,
                                              'verified_repairs': sum(r['verified_repair'] for r in results), 'attempts': len(results)})
    print(json.dumps({r['job_id']: r['outcome'] for r in results}, indent=1))


if __name__ == '__main__':
    main()
