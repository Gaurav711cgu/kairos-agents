"""Run one exposed development diagnostic without changing locked studies."""
from dataclasses import replace
from pathlib import Path
import argparse
import json

from kairos_api.investigations.registry import CaseRegistry
from scripts import study010, study012
from scripts.repair012.retrieval_loop012 import VERSION

PILOT_VERSION = 'development-retrieval013-v1'
SCOPE = ('Previously exposed development case with public issue hints; '
         'not fresh validation, a full SWE-bench result, or loop-superiority evidence')


def prepare(args):
    """Validate identity and freeze policy without starting services or generation."""
    registry = CaseRegistry(args.manifest, args.case_root)
    case = registry.get(args.task_id)
    if case.get('split') != 'development':
        raise ValueError('This pilot accepts exposed development cases only; locked evaluation is refused')
    registry.verify(case)
    runtime = study010.checked_runtime010(args.runtime, registry, case)
    # Metadata paths are explicit operator inputs. Source/verification access stays
    # within the existing registry; no reference content enters retrieval context.
    policy = study012.policy012(args, registry, case)
    policy = replace(policy, metadata={**policy.metadata, 'scope': SCOPE,
                     'pilot_version': PILOT_VERSION, 'exposed_development': True},
                     source_files=(*policy.source_files, 'scripts/pilot013.py'))
    return registry, case, runtime, policy


def run(args):
    registry, case, runtime, policy = prepare(args)
    if runtime.exists():
        return study010.existing_runtime010(runtime, case['id'], expected_version=VERSION)
    # This lock is shared with all optional CLI investigations. Existing runtimes
    # are never redispatched, including uncertain ones.
    with study010.runner_lock010(args.checkout):
        if runtime.exists():
            return study010.existing_runtime010(runtime, case['id'], expected_version=VERSION)
        result = study010._run_new010(args, args.checkout, registry, case, runtime, policy=policy)
    return {**result, 'pilot_scope': SCOPE}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('operation', choices=('validate', 'run', 'report'))
    for name in ('manifest', 'case-root', 'runtime', 'index-root', 'encoder-dir', 'encoder-profile', 'codex'):
        result.add_argument('--' + name, type=Path)
    result.add_argument('--checkout', type=Path, default=study010.ROOT)
    result.add_argument('--task-id')
    result.add_argument('--index-id')
    result.add_argument('--configuration', choices=('baseline-v8', 'loop-v8'), default='loop-v8')
    result.add_argument('--retrieval-mode', choices=('ast', 'lexical', 'dense', 'hybrid'), default='dense')
    result.add_argument('--budget-root', action='append', type=Path, default=[])
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.runtime is None:
            raise ValueError('An explicit private runtime is required')
        if args.operation == 'report':
            result = study010.report010(args.runtime, expected_version=VERSION)
        else:
            if not all((args.manifest, args.case_root, args.task_id)):
                raise ValueError('Provide the registered manifest, case root and development task ID')
            args.checkout = args.checkout.resolve(strict=True)
            if args.checkout != study010.ROOT.resolve():
                raise ValueError('Run this module from the installed checkout being fingerprinted')
            args.encoder_profile = args.encoder_profile or args.checkout / 'profiles/coderank011.json'
            if args.operation == 'validate':
                registry, case, _, policy = prepare(args)
                result = {'passed': True, 'pilot_version': PILOT_VERSION, 'task_id': case['id'],
                          'task_digest': registry.fingerprint(case), 'policy': policy.metadata,
                          'scope': SCOPE, 'services_started': False, 'model_dispatched': False}
            else:
                result = run(args)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        parser().exit(1, 'Development pilot refused: ' + str(error) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return int(result.get('status') in {'unknown', 'failed', 'incomplete'}
               or result.get('outcome') in {'unknown_dispatch', 'environment_failure'})


if __name__ == '__main__':
    raise SystemExit(main())
