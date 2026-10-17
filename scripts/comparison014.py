"""Run one frozen fresh comparison arm through the existing durable CLI runner.

Install this file and independent_drafts014.py inside the reviewed execution
checkout before running. Staging can be imported for fixture tests only.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from kairos_api.investigations.registry import CaseRegistry
from scripts.qualify006 import summary
from scripts.retrieval011.__main__ import storage_guard
from scripts.study010 import (_run_new010, _source_identity, checked_runtime010,
    cli_identity010, runner_lock010)
from scripts.study012 import policy012

try:
    from scripts.repair014 import independent_drafts014 as drafts_module
except ModuleNotFoundError as error:
    if error.name not in {"scripts.repair014", "scripts.repair014.independent_drafts014"}:
        raise
    import independent_drafts014 as drafts_module

VERSION = "comparison014-study-v1"
COHORT_SHA = "97f681a503ca3e1f63314c5c22c82e6e12be0f7891b2a80b6c16e74042f4fd1f"
ARMS = ("baseline", "loop", "drafts")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > 32 * 1024**2:
        raise ValueError("Comparison inputs must be bounded ordinary files without symlink ancestors")
    return json.loads(path.read_bytes())


def strategy_profiles014():
    return {
        "baseline": {"configuration": "baseline-v8", "max_calls": 1, "max_patches": 1, "max_checks": 1, "seconds": 600, "retrieval": "original AST", "strategy": "single call"},
        "loop": {"configuration": "loop-v8", "max_calls": 10, "max_patches": 4, "max_checks": 4, "seconds": 900, "retrieval": "original AST then bounded original search/read", "strategy": "adaptive existing v8"},
        "drafts": {"configuration": "loop-v8", "max_calls": 10, "max_patches": 4, "max_checks": 4, "seconds": 900, "retrieval": "fresh original AST only", "strategy": drafts_module.VERSION, "selection": drafts_module.POLICY},
    }


def validate_study014(path, expected_sha, cohort):
    study = load(path)
    if sha(path) != expected_sha:
        raise ValueError("Frozen comparison study bytes changed")
    if (study.get("version") != VERSION or study.get("cohort_sha256") != COHORT_SHA
            or study.get("arms") != list(ARMS)
            or study.get("strategy_profiles_sha256") != digest(strategy_profiles014())):
        raise ValueError("Study does not bind the reviewed three-arm strategy profiles")
    cases = study.get("cases", [])
    expected = [(c["instance_id"], c["split"]) for c in cohort["candidates"]]
    if [(c.get("instance_id"), c.get("split")) for c in cases] != expected:
        raise ValueError("Study must preserve all 24 frozen candidate IDs, order and splits")
    if any(not isinstance(c.get("qualification_receipt_sha256"), str) or len(c["qualification_receipt_sha256"]) != 64 for c in cases):
        raise ValueError("Every frozen study case must bind its terminal qualification receipt")
    return study


def raw_complete014(result):
    raw = result.get("raw_output", {})
    if (raw.get("encoding") != "base64" or raw.get("complete") is not True
            or result.get("output_limit_exceeded") or result.get("environment_error")):
        return False
    try:
        for name in ("stdout", "stderr"):
            stream = raw[name]
            data = base64.b64decode(stream["data"], validate=True)
            if (stream.get("truncated") or len(data) != stream["bytes"] or len(data) != stream["observed_bytes"]
                    or hashlib.sha256(data).hexdigest() != stream["sha256"]):
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def validate_qualification014(path, expected_sha, case):
    receipt = load(path)
    if (sha(path) != expected_sha or receipt.get("instance_id") != case["id"]
            or receipt.get("split") != case["split"] or receipt.get("status") != "qualified"
            or receipt.get("qualified") is not True):
        raise ValueError("This arm requires the same independently qualified frozen case")
    evidence = Path(path).parent
    for name, expected in receipt.get("evidence_sha256", {}).items():
        relative = Path(name)
        if relative.name != name or sha(evidence / name) != expected:
            raise ValueError("Qualification artifact hash changed")
    required = {"baseline.json", "reference.json", "case-definition.json", "source.json", "material-manifest.json", "test-scope.json"}
    if not required.issubset(receipt.get("evidence_sha256", {})):
        raise ValueError("Qualification receipt lacks complete source and check evidence")
    original = load(evidence / "case-definition.json")
    if {**original, "qualified": True} != case:
        raise ValueError("Rehydrated registered case differs from qualified source or hidden verifier")
    baseline = load(evidence / "baseline.json")["result"]
    reference = load(evidence / "reference.json")["result"]
    before, after = summary(baseline), summary(reference)
    if (not raw_complete014(baseline) or not raw_complete014(reference)
            or baseline.get("passed") is not False or baseline.get("returncode") in (None, 0, 124, 125, 126, 127)
            or before.get("execution_complete") is not True or not before.get("regression_failed") or before.get("tests_run", 0) <= 0
            or reference.get("passed") is not True or reference.get("returncode") != 0
            or after.get("execution_complete") is not True or after.get("complete") is not True or after.get("tests_run", 0) <= 0):
        raise ValueError("Captured complete baseline regression failure and reference pass are required")
    return receipt


def make_policy014(args, registry, case, study, study_sha):
    args.configuration = "baseline-v8" if args.arm == "baseline" else "loop-v8"
    args.retrieval_mode = "ast"
    policy = policy012(args, registry, case)
    checkout = Path(args.checkout).resolve(strict=True)
    additions = []
    for path in (Path(__file__).resolve(), Path(drafts_module.__file__).resolve()):
        if not path.is_relative_to(checkout):
            raise ValueError("Install reviewed comparison source inside the execution checkout before running")
        additions.append(path.relative_to(checkout).as_posix())
    files = tuple(dict.fromkeys((*policy.source_files, *additions)))
    identity = {**_source_identity(checkout), **{name: sha(checkout / name) for name in files}}
    if study.get("source_sha256") != identity:
        raise ValueError("Frozen comparison source identity changed or is incomplete")
    metadata = {**policy.metadata, "comparison014": {"study_sha256": study_sha, "arm": args.arm,
        "strategy_profiles_sha256": digest(strategy_profiles014()), "source_sha256": identity},
        "scope": "Frozen fresh-case comparison arm; outcome applies only to this candidate and declared resources; public pretraining exposure unknown"}
    original_factory = policy.provider_factory
    def frozen_provider(runtime, executable, expected_version, expected_sha256, model_id=None):
        expected = study["provider"]
        if (expected_version != expected["cli_version"] or expected_sha256 != expected["cli_sha256"]
                or model_id != expected["requested_model"]
                or {**_source_identity(checkout), **{name: sha(checkout / name) for name in files}} != identity):
            raise ValueError("Frozen provider/source identity changed before dispatch setup")
        return original_factory(runtime, executable, expected_version, expected_sha256, model_id=model_id)
    return replace(policy, metadata=metadata, source_files=files, provider_factory=frozen_provider,
        worker_factory=drafts_module.IndependentDraftWorker014 if args.arm == "drafts" else policy.worker_factory)


def run014(args):
    checkout = Path(args.checkout).resolve(strict=True)
    cohort_path = checkout / "evidence/evaluation013/cohort/cohort.json"
    if sha(cohort_path) != COHORT_SHA:
        raise ValueError("Execution checkout does not contain the exact frozen cohort")
    study = validate_study014(args.study, args.study_sha256, load(cohort_path))
    registry = CaseRegistry(args.manifest, args.case_root)
    case = registry.get(args.task_id)
    selected = next((c for c in study["cases"] if c["instance_id"] == case["id"]), None)
    if selected is None:
        raise ValueError("Task is absent from the frozen study")
    validate_qualification014(args.qualification_receipt, selected["qualification_receipt_sha256"], case)
    registry.verify(case)
    runtime = checked_runtime010(args.runtime, registry, case)
    if runtime.exists():
        raise ValueError("Comparison runtime is occupied; inspect its captured result without redispatch")
    roots = [Path(p).absolute() for p in args.budget_root]
    if not all(any(path.absolute().is_relative_to(p) for p in roots) for path in (runtime, registry.runtime, Path(args.study).parent, Path(args.qualification_receipt).parent)):
        raise ValueError("All study, qualification, source and runtime storage must be counted")
    storage_guard(roots, projected=96 * 1024**2)
    policy = make_policy014(args, registry, case, study, args.study_sha256)
    _, observed = cli_identity010(args.codex)
    if study.get("provider") != observed:
        raise ValueError("Frozen CLI/provider identity changed; no model was dispatched")
    with runner_lock010(checkout):
        if runtime.exists():
            raise ValueError("Comparison runtime became occupied; no model was dispatched")
        return _run_new010(args, checkout, registry, case, runtime, policy=policy)


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    for name in ("checkout", "manifest", "case-root", "runtime", "study", "qualification-receipt"):
        value.add_argument("--" + name, type=Path, required=True)
    value.add_argument("--task-id", required=True)
    value.add_argument("--study-sha256", required=True)
    value.add_argument("--arm", choices=ARMS, required=True)
    value.add_argument("--codex", type=Path)
    value.add_argument("--budget-root", type=Path, action="append", required=True)
    return value


def main(argv=None):
    try:
        result = run014(parser().parse_args(argv))
        print(json.dumps(result, sort_keys=True))
        return 1 if result.get("status") in {"failed", "incomplete", "unknown"} else 0
    except Exception as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__, "detail": str(error)[:500]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
