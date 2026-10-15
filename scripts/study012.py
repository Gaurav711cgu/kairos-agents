"""Run a reviewed task with versioned retrieval, bounded edits and durable capture."""
from pathlib import Path
import argparse
import copy
import json

from scripts.study010 import (ROOT, GENERATION, REQUESTED_MODEL, doctor010,
    registered_task010, report010, run010)
from scripts.repair012.retrieval_loop012 import (VERSION, RuntimePolicy012, NoSourceEvidence012,
    QueryEncoder012, RetrievalWorker012, UsageAwareWorker012, TokenBoundCLI012, workspace_class012)
from scripts.retrieval011 import load_index
from scripts.retrieval011.core import MAX_QUERY_BYTES, _tokens
from scripts.retrieval011.__main__ import storage_guard
from kairos_api.investigations.sandbox import Workspace


class UnassistedWorkspace012(Workspace):
    def initial_sources012(self):
        from kairos_api.investigations.context_v7 import initial_sources
        sources = initial_sources(self, use_entry_hints=False)
        if not sources:
            raise NoSourceEvidence012('Issue-only AST localization returned no source regions; no entry-file fallback or model dispatch')
        return sources


def policy012(args, registry, case):
    if args.configuration not in {'loop-v8', 'baseline-v8'}:
        raise ValueError('Only the explicitly versioned v8 configurations are accepted')
    if not args.budget_root:
        raise ValueError('Declare all owned experiment roots with --budget-root')
    storage = storage_guard(args.budget_root, 96 * 1024**2)
    retrieval = {'mode': args.retrieval_mode, 'maintainer_entry_hints_used': False,
                 'source_region_limit': 6, 'maximum_retrieval_actions': 6,
                 'source_revision': case['revision']}
    workspace, worker = UnassistedWorkspace012, UsageAwareWorker012
    if args.retrieval_mode != 'ast':
        issue = case['issue']
        if (not issue.strip() or len(issue.encode()) > MAX_QUERY_BYTES or '\x00' in issue
                or not _tokens(issue)):
            raise ValueError('Initial retrieval requires a nonempty source query of at most 4096 UTF-8 bytes')
        if not all((args.index_root, args.index_id, args.encoder_dir, args.encoder_profile)):
            raise ValueError('Semantic retrieval requires a prepared index, encoder and frozen profile')
        for path in (args.encoder_dir, args.index_root):
            if not any(Path(path).resolve().is_relative_to(Path(p).resolve()) for p in args.budget_root):
                raise ValueError('Embedding/index storage must belong to the counted experiment roots')
        encoder = QueryEncoder012(args.encoder_dir, args.encoder_profile)
        index = load_index(args.index_root, args.index_id, registry.directory(case) / 'source',
                           case['approved_prefix'], case['revision'], encoder=encoder)
        retrieval.update(index_id=index.index_id, source_snapshot_digest=index.source_snapshot_digest,
                         encoder_identity=index.encoder_identity, exact_backend=index.exact_backend)
        workspace = workspace_class012(args.index_root, args.index_id, encoder, args.retrieval_mode)
        worker = RetrievalWorker012
    cap = 10 if args.configuration == 'loop-v8' else 1

    def provider_factory(*values, **settings):
        return TokenBoundCLI012(*values, **settings, max_dispatches=cap)

    generation = {**copy.deepcopy(GENERATION), 'max_harness_dispatches': cap,
        'reported_prompt_token_ceiling': TokenBoundCLI012.prompt_ceiling,
        'reported_completion_token_ceiling': TokenBoundCLI012.completion_ceiling,
        'token_ceiling_scope': 'Stops subsequent calls from captured usage; a final call may overshoot and internal CLI retries are opaque'}
    source_files = ('scripts/study012.py', 'scripts/study010.py',
        'scripts/repair012/__init__.py', 'scripts/repair012/retrieval_loop012.py',
        'scripts/repair012/encoder_worker012.py', 'scripts/retrieval011/core.py',
        'scripts/retrieval011/encoder.py', 'scripts/retrieval011/faiss_worker.py',
        'profiles/coderank011.json', 'profiles/coderank011-header.json',
        'kairos_api/investigations/contracts.py', 'kairos_api/investigations/context_v7.py',
        'kairos_api/investigations/context_v5.py',
        'kairos_api/investigations/repository.py', 'kairos_api/investigations/sandbox.py',
        'kairos_api/investigations/output_supervisor.py', 'kairos_api/investigations/registry.py',
        'kairos_api/investigations/patches.py',
        'kairos_api/migrations.py', 'kairos_api/migrations/0005_configuration_v8_expand.sql',
        'kairos_api/migrations/0006_configuration_v8_validate.sql')
    for name in source_files:
        if not (ROOT / name).is_file():
            raise ValueError('Frozen execution source is unavailable: ' + name)
    return RuntimePolicy012(VERSION, args.configuration, generation,
        {'retrieval': retrieval, 'storage_before': storage, 'new_api_billing': False,
         'semantic_model_lifetime': 'One query child process; exits before model generation or Docker checks'},
        source_files, provider_factory, worker, workspace)


def parser012():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    for action in ('doctor', 'validate-task', 'run', 'report'):
        command = commands.add_parser(action)
        for name in ('manifest', 'case-root', 'runtime', 'codex', 'checkout',
                     'index-root', 'encoder-dir', 'encoder-profile'):
            command.add_argument('--' + name, type=Path)
        command.add_argument('--task-id')
        command.add_argument('--index-id')
        command.add_argument('--configuration', choices=('loop-v8', 'baseline-v8'), default='loop-v8')
        command.add_argument('--retrieval-mode', choices=('ast', 'lexical', 'dense', 'hybrid'), default='hybrid')
        command.add_argument('--budget-root', type=Path, action='append', default=[])
    return parser


def main(argv=None):
    args = parser012().parse_args(argv)
    args.checkout = args.checkout or ROOT
    args.encoder_profile = args.encoder_profile or ROOT / 'profiles/coderank011.json'
    try:
        if args.operation == 'report':
            if args.runtime is None:
                raise ValueError('Report requires an explicit owned runtime')
            result = report010(args.runtime, expected_version=VERSION)
        elif args.operation == 'doctor':
            result = {**doctor010(args), 'version': VERSION,
                      'configuration': args.configuration, 'retrieval_mode': args.retrieval_mode}
        else:
            registry, case = registered_task010(args.manifest, args.case_root, args.task_id)
            if case is None:
                raise ValueError('A registered reviewed task is required')
            policy = policy012(args, registry, case)
            if args.operation == 'validate-task':
                result = {'passed': True, 'version': VERSION, 'task_id': case['id'],
                          'task_digest': registry.fingerprint(case), 'policy': policy.metadata,
                          'model_dispatched': False, 'services_started': False}
            else:
                args.runtime = args.runtime or args.checkout / '.runtime/study012' / case['id']
                result = run010(args, policy=policy)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        parser012().exit(1, 'Retrieval investigation refused: ' + str(error) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 1 if (result.get('status') in {'failed', 'incomplete', 'unknown'}
                 or result.get('outcome') in {'unknown_dispatch', 'environment_failure'}) else 0


if __name__ == '__main__':
    raise SystemExit(main())
