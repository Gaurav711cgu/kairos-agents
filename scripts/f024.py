"""F024 offline harness: memory preflight, outcome classes and turn-two planning.

No model call happens here. Turn-one prompts come from the frozen 021 pack; captures
come back from an approved Colab run and are validated locally by ``validate021``.
"""
import hashlib
import json

from scripts.feedback_turn021 import next_turn021, validate021
from scripts.repair010.feedback010 import FeedbackContextOverflow010

from scripts.f024_colab import ENVELOPE_TOKENS  # single source: the hash-bound runner
TURN1_MAX_NEW = 1024
TURN2_MAX_NEW = 512
TURN1_MAX_NEW_PILOT = 512  # policy P2: keeps 28/30 issue-only prompts inside the envelope


def make_job(instance_id, context, arm, turn, messages, tokenizer, max_new_tokens=TURN1_MAX_NEW_PILOT):
    """One job; the token-id digest is re-checked against the real tokenizer on Colab before dispatch."""
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    return {'job_id': f'{instance_id}/{context}/{arm}/t{turn}', 'instance_id': instance_id, 'context': context, 'arm': arm,
            'turn': turn, 'messages': messages, 'prompt_tokens': len(ids), 'max_new_tokens': max_new_tokens,
            'prompt_token_ids_sha256': hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()}


def preflight(prompt_tokens, max_new_tokens):
    return prompt_tokens + max_new_tokens <= ENVELOPE_TOKENS


def classify(verdict):
    if verdict['accepted']:
        return 'accepted'
    if verdict['stage'] == 'parse':
        return 'parse'
    reason = verdict['reason']
    if 'syntax rejected' in reason:
        return 'syntax_indentation' if 'indent' in reason else 'syntax_other'
    if 'escapes captured excerpt' in reason or 'bounds' in reason:
        return 'range'
    if 'makes no change' in reason:
        return 'no_change'
    return 'validator_other'


def turn2(jobs, captures, context_for, tokenizer):
    """Plan turn two for rejected turn-one captures that fit the envelope; record every outcome."""
    planned, ledger = [], {}
    for job in jobs:
        capture = captures.get(job['job_id'])
        if capture is None or capture['status'] != 'captured':  # never redispatched
            ledger[job['job_id']] = 'not_captured' if capture is None else capture['status']
            continue
        workspace, regions = context_for(job)
        verdict = validate021(workspace, capture['result']['text'], regions)
        ledger[job['job_id']] = classify(verdict)
        try:
            # The memory envelope (tokens) is the binding gate; the byte budget stays at the module default.
            second = next_turn021(job['messages'], regions, verdict, tokenizer=tokenizer,
                                  maximum_prompt_tokens=ENVELOPE_TOKENS - TURN2_MAX_NEW)
        except FeedbackContextOverflow010 as error:
            ledger[job['job_id']] += '+turn2_over_token_envelope' if 'token cap' in str(error) else '+turn2_over_feedback_bytes'
            continue
        if second is not None:
            planned.append({**make_job(job['instance_id'], job['context'], job['arm'], 2, second, tokenizer, TURN2_MAX_NEW),
                            'parent_job_id': job['job_id'], 'parent_capture_sha256': capture['capture_sha256']})
    return planned, ledger


def build_pilot(receipt, rows, cache, pack, tokenizer, per_repository=1):
    """Turn-one pilot jobs: first in-scope cases per repository whose two contexts both fit.

    Selection bias, stated: in-scope (edit-protocol limits) and short enough for the envelope,
    in salted split order. A pipeline check, not a representative sample. The issue arm never
    sees the gold patch; only the separately packed oracle arm does.
    """
    import types
    from kairos_api.investigations.sandbox import Workspace
    from scripts.coding_context_v3_014 import select as frozen023
    from scripts.localization_dev024 import PREFIXES
    from scripts.oracle_context024 import oracle_regions
    jobs, chosen = [], {}
    for case in receipt['cases']:
        repository, identifier = case['repository'], case['instance_id']
        if chosen.get(repository, 0) >= per_repository or case['arms']['frozen023']['containment'] == 'scope_limit':
            continue
        row, directory = rows[identifier], cache / identifier
        source = json.loads((directory / 'source.json').read_text())
        if (source['revision'], source['archive_sha256']) != (case['revision'], case['archive_sha256']):
            raise ValueError('Cached source differs from the localization receipt: ' + identifier)
        workspace = Workspace(types.SimpleNamespace(verify=lambda _: None, directory=lambda _: directory),
                              {'id': identifier, 'issue': row['problem_statement'], 'approved_prefix': PREFIXES[repository], 'entry_files': [], 'entry_lines': {}})
        try:
            issue = frozen023(workspace)
            try:
                oracle = oracle_regions(workspace, row['patch'], PREFIXES[repository])
            except ValueError:
                continue
            packed = {'issue': pack(row['problem_statement'], issue, tokenizer), 'oracle': pack(row['problem_statement'], oracle, tokenizer)}
        finally:
            workspace.close()
        if len(packed['oracle']['regions']) != len(oracle) or not all(preflight(p['prompt_tokens'], TURN1_MAX_NEW_PILOT) for p in packed.values()):
            continue
        chosen[repository] = chosen.get(repository, 0) + 1
        for context, p in packed.items():
            jobs += [make_job(identifier, context, arm, 1, p['messages'], tokenizer) for arm in ('base', 'adapter')]
    return jobs


def main():  # pragma: no cover - thin CLI over turn2; exercised by the mock dry run
    """Build the turn-two package from downloaded turn-one captures (local; no model)."""
    import argparse
    import types
    from pathlib import Path
    from kairos_api.investigations.sandbox import Workspace
    from kairos_api.investigations.context_v7 import source_block
    from scripts.f024_colab import validate_package
    from scripts.localization_dev024 import PREFIXES, ChatTokenizer
    parser = argparse.ArgumentParser()
    for name in ['package', 'results', 'cache', 'tokenizer', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Turn-two package is immutable; choose a new output path')
    package = json.loads(args.package.read_text())
    validate_package(package)
    captures = {}
    for path in (args.results / 'captures').rglob('*.json'):
        record = json.loads(path.read_text())
        captures[record['job_id']] = record
    workspaces = []

    def context_for(job):
        repository = 'django/django' if job['instance_id'].startswith('django') else 'pytest-dev/pytest'
        directory = args.cache / job['instance_id']
        workspace = Workspace(types.SimpleNamespace(verify=lambda _: None, directory=lambda _: directory),
                              {'id': job['instance_id'], 'issue': '', 'approved_prefix': PREFIXES[repository], 'entry_files': [], 'entry_lines': {}})
        workspaces.append(workspace)
        blocks = json.loads(job['messages'][1]['content'])['original_source']
        regions = [workspace.read_original(b['path'], b['start_line'], b['end_line']) for b in blocks]
        if [source_block(r)['source_id'] for r in regions] != [b['source_id'] for b in blocks]:
            raise ValueError('Captured source handles differ from the cached source: ' + job['job_id'])
        return workspace, regions

    try:
        planned, ledger = turn2([j for j in package['jobs'] if j['turn'] == 1], captures, context_for, ChatTokenizer(args.tokenizer / 'tokenizer.json'))
    finally:
        for workspace in workspaces:
            workspace.close()
    second = {**package, 'jobs': planned, 'scope': package.get('scope', '') + '; turn two after local validation'}
    if planned:
        validate_package(second)
    args.output.mkdir(parents=True)
    (args.output / 'turn2-package.json').write_text(json.dumps(second, sort_keys=True, indent=1))
    (args.output / 'turn1-ledger.json').write_text(json.dumps(ledger, sort_keys=True, indent=1))
    print(json.dumps({'turn2_jobs': len(planned), 'ledger': ledger}, indent=1))


if __name__ == '__main__':
    main()
