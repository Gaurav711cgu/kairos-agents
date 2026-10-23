"""Independently check imported, frozen model edits without model execution.

Uses Kairos's original-source validator and reviewed, network-isolated verifier.
Each case runs sequentially in a new owned directory. Unknown checks are never
redispatched. References remain outside the model runtime and candidate source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def materials(case, scope, row, qualifier):
    if (row.get('instance_id'), row.get('repo'), row.get('base_commit')) != (
            case['id'], case['repository'], case['revision']):
        raise ValueError('External dataset row differs from qualified case')
    # Historical publication removed an entire issue containing a private path.
    # Keep the frozen prompt unchanged and disclose this limitation. The full
    # private row is independently bound to the pinned dataset before this call.
    redacted = '[Private machine location omitted; original bytes are retained locally.]'
    if case['issue'] != row.get('problem_statement') and case['issue'] != redacted:
        raise ValueError('External issue differs from the frozen public case')
    original = qualifier.added_test_selectors
    qualifier.added_test_selectors = lambda *_: scope['added_hidden_tests']
    try:
        if scope.get('protocol') == 'structured-unittest014-v1':
            from scripts.verifier_unittest014 import verifier
            script, regenerated = verifier(row, Path('/unavailable-source'))
        else:
            script, regenerated = qualifier.verifier(row, Path('/unavailable-source'))
    finally:
        qualifier.added_test_selectors = original
    if regenerated != scope:
        raise ValueError('Regenerated verification scope differs')
    reference = row['patch'].encode()
    if (hashlib.sha256(reference).hexdigest() != case['reference_digest']
            or hashlib.sha256((row['test_patch'] + script).encode()).hexdigest() != case['verification_digest']):
        raise ValueError('Private verification material differs from qualified hashes')
    return {'reference.patch': reference, 'test.patch': row['test_patch'].encode(), 'verify.py': script.encode()}


def execute(args):
    sys.path.insert(0, str(args.project))
    from scripts import coding_eval020 as protocol, qualify014 as q, qualify006
    from scripts.comparison014 import raw_complete014
    from kairos_api.investigations.registry import CaseRegistry, tree_hash
    from kairos_api.investigations.sandbox import Workspace
    roots = q.budget_paths(args.budget_root)
    if not q.covered(args.output, roots):
        raise ValueError('Output must be inside a declared storage root')
    imported, package, bindings = map(q.load, [args.imported, args.prompts, args.bindings])
    if (imported['version'] != 'inference-import020-v1'
            or imported['binding']['prompts_sha256'] != q.sha(args.prompts)
            or bindings['prompts_sha256'] != q.sha(args.prompts)):
        raise ValueError('Imported generations and private bindings must match frozen prompts')
    expected = [case['instance_id'] for case in package['cases']]
    if len(expected) != 12 or len(set(expected)) != 12:
        raise ValueError('Frozen case membership differs')
    private = {case['instance_id']: case for case in bindings['bindings']}
    public = {case['instance_id']: case for case in package['cases']}
    indexed = {}
    for record in imported['records']:
        key = record['instance_id'], record['arm']
        if key in indexed or key[0] not in expected or key[1] not in ['base', 'adapter']:
            raise ValueError('Unexpected or duplicate imported attempt')
        unsigned = {name: value for name, value in record.items() if name != 'capture_sha256'}
        if (record.get('capture_sha256') != protocol.digest(unsigned)
                or record.get('binding_sha256') != protocol.digest(imported['binding'])
                or record.get('verified_repair') is not None or record.get('verification_complete') is not False):
            raise ValueError('Imported capture changed after verification')
        indexed[key] = record
    if len(indexed) != 24:
        raise ValueError('Missing imported attempts')
    # Revalidate the external dataset against its original pinned split receipt.
    cohort = q.frozen_cohort(args.project, args.project / 'evidence/evaluation013/cohort/cohort.json')
    rows = q.hidden_rows(args.hidden_records, args.hidden_provenance, args.project, cohort)
    if isinstance(rows, list):
        rows = {row['instance_id']: row for row in rows}
    q.storage_guard(roots)
    args.output.mkdir(parents=True, exist_ok=True)
    binding = {'version': 'independent-repair-verification020-v1', 'import_sha256': q.sha(args.imported),
               'prompts_sha256': q.sha(args.prompts), 'private_bindings_sha256': q.sha(args.bindings),
               'validator_sha256': q.sha(args.project / 'kairos_api/investigations/sandbox.py'),
               'verifier_sha256': q.sha(args.project / 'scripts/qualify006.py'),
               'runner_sha256': q.sha(__file__), 'model_dispatches': 0}
    q.immutable(args.output / 'binding.json', binding)
    results = []
    for identifier in expected:
        output = args.output / identifier
        output.mkdir(exist_ok=True)
        completed = output / 'assessment.json'
        if completed.exists():
            previous = q.load(completed)
            if previous['binding'] != binding:
                raise ValueError('Prior assessment binding differs')
            results.extend(previous['records'])
            continue
        context = public[identifier]
        candidate_actions, assessed = {}, {}
        for arm in ['base', 'adapter']:
            record = indexed[identifier, arm]
            result = {'instance_id': identifier, 'arm': arm, 'model_calls': record['model_calls'],
                      'capture_sha256': record['capture_sha256'], 'verified_repair': False,
                      'verification_complete': False, 'checks': {}, 'status': record['status']}
            if record['status'] == 'captured':
                try:
                    action, normalized = protocol.parse_action(record['text'], context['source_handles'])
                    candidate_actions[arm] = action
                    result.update(status='awaiting_independent_checks', syntactic_normalization=normalized)
                except (ValueError, KeyError, TypeError) as error:
                    result.update(status='invalid_action', reason=str(error), verification_complete=True)
            else:
                result['reason'] = record.get('reason', 'No complete captured generation')
            assessed[arm] = result
        if candidate_actions:
            folder = args.project / 'evidence/measurement014/qualification' / identifier
            case = {**q.load(folder / 'case-definition.json'), 'qualified': True}
            original_qualification = q.load(folder / 'receipt.json')
            if (original_qualification.get('qualified') is not True
                    or q.sha(folder / 'receipt.json') != private[identifier]['qualification_sha256']
                    or (case['repository'], case['revision'], case['source_digest']) != (
                        context['repository'], context['revision'], context['source_digest'])):
                raise ValueError('Qualified case identity changed')
            record_path = args.project / 'evidence/measurement014/comparison/records' / identifier / 'baseline/bundle.json'
            if q.sha(record_path) != private[identifier]['record_sha256']:
                raise ValueError('Historical original-source authority changed')
            hidden = materials(case, q.load(folder / 'test-scope.json'), rows[identifier], qualify006)
            # Do not start Docker or pull an image automatically.
            actual_image = subprocess.run(['docker', 'image', 'inspect', case['image'], '--format', '{{.Id}}'],
                                          capture_output=True, text=True, timeout=10, check=True).stdout.strip()
            if actual_image != case['image']:
                raise ValueError('Reviewed verifier image changed')
            source, source_receipt = q.pinned_source({'instance_id': identifier, 'repo': case['repository'],
                'base_commit': case['revision']}, output, roots, args.allow_source_download, tree_hash)
            if source_receipt['source_digest'] != case['source_digest']:
                raise ValueError('Reconstructed source differs from original qualification')
            original_source = q.load(folder / 'source.json')
            if source_receipt['archive_sha256'] != original_source['archive_sha256']:
                raise ValueError('Pinned source archive differs from qualification')
            downloaded_archive = output / 'source.tar.gz'
            if downloaded_archive.exists():
                if q.sha(downloaded_archive) != source_receipt['archive_sha256']:
                    raise ValueError('Temporary download changed; preserve it for inspection')
                # The verified expanded source and pinned receipt suffice here;
                # release this newly downloaded duplicate before workspace copies.
                downloaded_archive.unlink()
            directory = output / 'registry/cases' / identifier
            directory.mkdir(parents=True, exist_ok=True)
            if source != directory / 'source':
                source.rename(directory / 'source')
            for name, raw in hidden.items():
                path = directory / name
                if path.exists() and path.read_bytes() != raw:
                    raise ValueError('Prior private material changed')
                path.write_bytes(raw)
            q.immutable(output / 'registry.json', {'version': 'repository-cases-v1', 'cases': [case]})
            registry = CaseRegistry(output / 'registry.json', output / 'registry')
            size = q.tree_bytes(directory / 'source')
            q.storage_guard(roots, size * 2 + q.CHECK_RESERVATION)
            work = None
            with q.counted_temporary(output / 'temporary'):
                try:
                    work = Workspace(registry, case)
                    baseline = q.captured_check(output / 'baseline.json', 'baseline',
                        lambda: work.checks(timeout=120), q.digest(binding), roots, size)
                    work.propose(hidden['reference.patch'].decode())
                    reference = q.captured_check(output / 'reference.json', 'reference',
                        lambda: work.checks(timeout=120), q.digest(binding), roots, size)
                    qualification = q.check_qualified(baseline, reference, qualify006)
                    q.immutable(output / 'qualification.json', qualification)
                    sources = {'S' + region['reference']['excerpt_id'][:12]: region['reference']
                               for region in private[identifier]['original_regions']}
                    for arm, action in candidate_actions.items():
                        result = assessed[arm]
                        if not qualification['qualified']:
                            result.update(status='environment_or_qualification_failure')
                            continue
                        try:
                            patch = work.propose_line_edits(action['edits'], sources)
                        except ValueError as error:
                            result.update(status='invalid_patch', reason=str(error), verification_complete=True)
                            continue
                        q.immutable(output / (arm + '.patch.json'), patch)
                        capture = q.captured_check(output / (arm + '.check.json'), arm,
                            lambda: work.checks(timeout=120), q.digest(binding), roots, size)
                        summary = qualify006.summary(capture)
                        complete = bool(raw_complete014(capture) and summary.get('execution_complete') is True
                                        and summary.get('tests_run', 0) > 0)
                        passed = bool(complete and capture.get('passed') is True and summary.get('complete') is True)
                        result.update(status='verified_repair' if passed else 'checks_failed' if complete else 'verification_incomplete',
                            verified_repair=passed, verification_complete=complete,
                            checks={'baseline_failed': True, 'regression_passed': passed, 'existing_passed': passed,
                                    'execution_complete': complete, 'independent': True}, summary=summary,
                            check_capture_sha256=q.sha(output / (arm + '.check.json')),
                            patch_capture_sha256=q.sha(output / (arm + '.patch.json')))
                finally:
                    if work is not None:
                        work.close()
            registry.verify(case)
            q.immutable(output / 'source-preservation.json', {'source': source_receipt,
                'verified_tree_digest': case['source_digest'], 'original_source_unchanged': True,
                'scope': 'Registry verification recomputed the full path/content tree digest before cleanup; pinned archive and source identities are retained.'})
            # Only this regenerated source is removed after manifest sealing.
            shutil.rmtree(directory / 'source')
        value = {'binding': binding, 'records': list(assessed.values())}
        q.immutable(completed, value)
        results.extend(value['records'])
        print(json.dumps({'case': identifier, 'outcomes': {arm: r['status'] for arm, r in assessed.items()}}), flush=True)
    report = protocol.summarize(results, expected)
    q.immutable(args.output / 'report.json', {**report, 'binding': binding, 'records': results})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['project', 'imported', 'prompts', 'bindings', 'hidden-records', 'hidden-provenance', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--budget-root', type=Path, action='append', required=True)
    parser.add_argument('--allow-source-download', action='store_true')
    print(json.dumps(execute(parser.parse_args()), indent=2))
