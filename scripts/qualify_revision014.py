"""Freeze an explicit image revision and retry only fresh pre-model environments."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

if __package__:
    from . import qualify014 as q
else:
    import qualify014 as q

VERSION = "qualification014-image-revision-v1"
ORIGINAL_IMAGES = copy.deepcopy(q.IMAGES)


def image_policy(path):
    value = q.load(path, 65536)
    repositories = value.get("repositories", {})
    versions = repositories.get("django/django", {})
    if (value.get("version") != "qualification014-image-policy-v1" or value.get("reviewed") is not True
            or set(repositories) != set(ORIGINAL_IMAGES)
            or set(versions) != {"3.1", "3.2", "4.0", "4.1", "4.2", "5.0"}
            or set(repositories.get("pytest-dev/pytest", {})) != {"*"}):
        raise ValueError("Use the explicit reviewed Django version/pytest wildcard image policy")
    for mapping in repositories.values():
        for image in mapping.values():
            if (not isinstance(image.get("tag"), str) or not image["tag"]
                    or not isinstance(image.get("id"), str) or not q.re.fullmatch(r"sha256:[a-f0-9]{64}", image["id"])):
                raise ValueError("Every reviewed image needs its exact local tag and SHA-256 ID")
    pair = lambda image: {key: image[key] for key in ("tag", "id")}
    if (any(pair(versions[v]) != ORIGINAL_IMAGES["django/django"] for v in ("3.1", "3.2"))
            or pair(repositories["pytest-dev/pytest"]["*"]) != ORIGINAL_IMAGES["pytest-dev/pytest"]
            or not all(pair(versions[v]) == pair(versions["4.0"]) for v in ("4.1", "4.2"))
            or versions["4.0"]["id"] == ORIGINAL_IMAGES["django/django"]["id"]
            or versions["5.0"]["id"] in {versions["4.0"]["id"], ORIGINAL_IMAGES["django/django"]["id"]}):
        raise ValueError("Policy must preserve old 3.1/3.2/pytest images and distinguish both reviewed new Django recipes")
    return value


def selected_image(policy, row):
    mapping = policy["repositories"][row["repo"]]
    image = mapping.get(row["version"], mapping.get("*"))
    if image is None:
        raise ValueError("No reviewed image for frozen repository/version: " + row["repo"] + "/" + row["version"])
    return {key: image[key] for key in ("tag", "id")}


def pre_model_gate(path, cohort):
    value = q.load(path, 65536)
    if (value.get("cohort_sha256") != q.COHORT_SHA256
            or value.get("candidate_ids") != [c["instance_id"] for c in cohort["candidates"]]
            or type(value.get("model_calls")) is not int or value["model_calls"] != 0
            or type(value.get("dispatch_intents")) is not int or value["dispatch_intents"] != 0
            or value.get("evaluation_started") is not False):
        raise ValueError("Image revisions require an exact-cohort zero-model/zero-intent pre-evaluation receipt")
    return value


def previous_run(path, cohort):
    binding, plan, report = (q.load(path / name) for name in ("binding.json", "plan.json", "report.json"))
    expected = [(c["instance_id"], c["split"]) for c in cohort["candidates"]]
    if (report.get("binding") != binding["binding"] or plan.get("binding") != binding["binding"]
            or report.get("model_calls") != 0
            or [(c["instance_id"], c["split"]) for c in report["candidates"]] != expected):
        raise ValueError("Previous run must be complete, model-free and bound to all 24 original cases")
    if report.get("execution_complete") is not True:
        interruption = report.get("interruption", {})
        if interruption.get("reason") != "Reviewed dependency revision before model execution" or interruption.get("no_uncaptured_checks") is not True:
            raise ValueError("Incomplete prior execution requires an explicit safe-boundary interruption receipt")
    for intent in path.glob("cases/*/*.started.json"):
        if not intent.with_name(intent.name.replace(".started.json", ".json")).is_file():
            raise ValueError("Prior check has an uncertain dispatch; preserve it without automatic retry")
    receipts = {}
    for entry in report["candidates"]:
        target = path / "cases" / entry["instance_id"] / "receipt.json"
        if target.exists():
            receipt = q.load(target)
            if (receipt.get("binding") != binding["binding"] or receipt.get("instance_id") != entry["instance_id"]
                    or receipt.get("status") != entry["status"] or receipt.get("model_calls") != 0):
                raise ValueError("Previous terminal receipt differs from its bound report")
            receipts[entry["instance_id"]] = (target, receipt)
        elif entry["status"] not in {"scope_excluded", "input_unavailable", "eligible"}:
            raise ValueError("Previous terminal case receipt is unavailable")
    return binding, plan, report, receipts


def reusable(path, receipt, candidate, row, image, qualifier):
    evidence = path.parent
    required = {"baseline.json", "reference.json", "source.json", "case-definition.json", "test-scope.json", "material-manifest.json"}
    hashes = receipt.get("evidence_sha256", {})
    if not required.issubset(hashes) or any(Path(n).name != n or q.sha(evidence / n) != h for n, h in hashes.items()):
        raise ValueError("Prior qualification artifact hashes are incomplete or changed")
    case, source, scope, manifest = (q.load(evidence / n) for n in ("case-definition.json", "source.json", "test-scope.json", "material-manifest.json"))
    if ((case["id"], case["repository"], case["revision"], case["issue"], case["split"], case["image"]) !=
            (candidate["instance_id"], row["repo"], row["base_commit"], row["problem_statement"], candidate["split"], image["id"])):
        return False
    prefix = "registry/cases/" + case["id"] + "/"
    files = manifest["files"]
    original = [(f["path"][len(prefix + "source/"):], f["sha256"]) for f in files if f["path"].startswith(prefix + "source/") and "sha256" in f]
    source_hash = hashlib.sha256(json.dumps(original, separators=(",", ":")).encode()).hexdigest()
    material = {f["path"]: f.get("sha256") for f in files}
    old = qualifier.added_test_selectors
    qualifier.added_test_selectors = lambda *_: scope.get("added_hidden_tests", [])
    try:
        script, regenerated_scope = qualifier.verifier(row, Path("/unavailable-source"))
    finally:
        qualifier.added_test_selectors = old
    if (not original or source_hash != case["source_digest"] or source["source_digest"] != source_hash
            or source["revision"] != row["base_commit"] or source["repository"] != row["repo"]
            or regenerated_scope != scope or case["reference_digest"] != hashlib.sha256(row["patch"].encode()).hexdigest()
            or case["verification_digest"] != hashlib.sha256((row["test_patch"] + script).encode()).hexdigest()
            or material.get(prefix + "reference.patch") != case["reference_digest"]
            or material.get(prefix + "test.patch") != hashlib.sha256(row["test_patch"].encode()).hexdigest()
            or material.get(prefix + "verify.py") != hashlib.sha256(script.encode()).hexdigest()):
        raise ValueError("Prior source/reference/verification digests do not reproduce the same case")
    checks = [q.load(evidence / n) for n in ("baseline.json", "reference.json")]
    if any(c.get("binding") != receipt["binding"] for c in checks) or not q.check_qualified(checks[0]["result"], checks[1]["result"], qualifier)["qualified"]:
        raise ValueError("Prior receipt lacks complete baseline failure and reference pass")
    return True


def copy_receipt(path, destination, binding, roots):
    files = sorted(path.parent.glob("*.json"))
    q.storage_guard(roots, sum(p.stat().st_size for p in files))
    for source in files:
        q.immutable(destination / source.name, q.load(source))
        if q.sha(source) != q.sha(destination / source.name):
            raise ValueError("Prior JSON capture was not preserved byte for byte")
    q.immutable(destination / "reuse-provenance.json", {"revision_binding": binding,
        "original_receipt": str(path), "original_receipt_sha256": q.sha(path), "checks_rerun": 0})


def inspect_policy(policy):
    images = {(i["tag"], i["id"]) for m in policy["repositories"].values() for i in m.values()}
    for tag, expected in sorted(images):
        result = subprocess.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], capture_output=True, text=True, timeout=10)
        if result.returncode or result.stdout.strip() != expected:
            raise ValueError("Reviewed policy image is unavailable or changed: " + tag)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "hidden-records", "hidden-provenance", "previous", "image-policy", "pre-model-receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--budget-root", type=Path, action="append", required=True)
    parser.add_argument("--allow-source-download", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        project, previous, out = (q.no_symlinks(p) for p in (args.project, args.previous, args.output))
        if out.is_relative_to(previous) or previous.is_relative_to(out):
            raise ValueError("Revision output must be a new namespace separate from the previous run")
        roots = q.budget_paths(args.budget_root)
        if not all(q.covered(p, roots) for p in (project / ".runtime/investigations", previous, out, args.hidden_records, args.hidden_provenance, args.image_policy, args.pre_model_receipt)):
            raise ValueError("Count every prior/new source, hidden input, policy and ephemeral output root")
        q.storage_guard(roots)
        cohort = q.frozen_cohort(project, project / "evidence/evaluation013/cohort/cohort.json")
        policy = image_policy(args.image_policy)
        pre_model_gate(args.pre_model_receipt, cohort)
        old_binding, old_plan, old_report, prior = previous_run(previous, cohort)
        deps = q.dependencies(project)
        rows = q.hidden_rows(args.hidden_records, args.hidden_provenance, project, cohort)
        frozen = q.plan_for(cohort, rows, deps[0])
        if frozen["candidates"] != old_plan["candidates"] or any(old_binding[k] != q.sha(p) for k, p in (("hidden_records_sha256", args.hidden_records), ("hidden_provenance_sha256", args.hidden_provenance))):
            raise ValueError("Image revision cannot change hidden rows or frozen source eligibility")
        inputs = {"version": VERSION, "cohort_sha256": q.COHORT_SHA256, "image_policy_sha256": q.sha(args.image_policy),
            "pre_model_receipt_sha256": q.sha(args.pre_model_receipt), "previous_report_sha256": q.sha(previous / "report.json"),
            "prior_receipts_sha256": {i: q.sha(p) for i, (p, _) in prior.items()}, "implementation_sha256": q.sha(Path(__file__)),
            "helper_sha256": q.sha(Path(q.__file__)), "dependency_sha256": {n: q.sha(project / n) for n in q.MODULE_FILES},
            "hidden_records_sha256": q.sha(args.hidden_records), "hidden_provenance_sha256": q.sha(args.hidden_provenance),
            "budget_roots": [str(p) for p in roots], "allow_source_download": args.allow_source_download}
        binding = q.digest(inputs)
        if out.exists() and not (out / "binding.json").exists():
            raise ValueError("Revision output must be fresh or resumable under its identical binding")
        q.immutable(out / "binding.json", {"binding": binding, **inputs})
        decisions = []
        old_entries = {e["instance_id"]: e for e in old_report["candidates"]}
        for candidate in frozen["candidates"]:
            identifier = candidate["instance_id"]
            image, prior_entry = selected_image(policy, rows[identifier]), old_entries[identifier]
            action = "retry_environment" if prior_entry["status"] == "environment_failure" else "retain_prior"
            if prior_entry["status"] == "eligible":
                action = "execute_unattempted"
            if prior_entry["status"] == "qualified":
                action = "reuse_qualified" if reusable(*prior[identifier], candidate, rows[identifier], image, deps[0]) else "image_mismatch_no_retry"
            decisions.append({"instance_id": identifier, "split": candidate["split"], "action": action, "image": image, "prior_status": prior_entry["status"]})
        q.immutable(out / "plan.json", {"binding": binding, **frozen, "revision_decisions": decisions, "policy": policy})
        results = {}
        if args.execute:
            inspect_policy(policy)
            for entry, decision in zip(frozen["candidates"], decisions):
                identifier, action = entry["instance_id"], decision["action"]
                if q.sha(args.pre_model_receipt) != inputs["pre_model_receipt_sha256"]:
                    raise ValueError("Pre-model gate changed during qualification; no further retry")
                if action in {"retry_environment", "execute_unattempted"}:
                    original_images = q.IMAGES
                    q.IMAGES = {**ORIGINAL_IMAGES, entry["repository"]: decision["image"]}
                    try:
                        results[identifier] = q.execute_case(entry, rows[identifier], out, roots, binding, args.allow_source_download, deps)
                    finally:
                        q.IMAGES = original_images
                elif action == "image_mismatch_no_retry":
                    results[identifier] = {**entry, "status": "input_unavailable", "qualified": False, "reason": "Prior qualified image differs; completed passing checks are never rerun"}
                    q.immutable(out / "cases" / identifier / "receipt.json", {"binding": binding, **results[identifier]})
                else:
                    results[identifier] = old_entries[identifier]
                    if identifier in prior:
                        copy_receipt(prior[identifier][0], out / "cases" / identifier, binding, roots)
                print(json.dumps({"phase": "qualification_revision", "instance_id": identifier, "action": action, "status": results[identifier]["status"]}), flush=True)
        result = {"binding": binding, **q.report(frozen, results, args.execute), "revision_decisions": decisions}
        q.immutable(out / ("report.json" if args.execute else "plan-report.json"), result)
        print(json.dumps({"binding": binding, "executed": args.execute, "counts": result["counts"], "model_calls": 0}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("Qualification image revision refused: " + str(error), file=q.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
