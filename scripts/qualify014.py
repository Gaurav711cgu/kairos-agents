"""Qualify the exact frozen013 cohort without inference or historical writes.

This additive runner deliberately uses the reviewed qualify006 verifier and
CaseRegistry/Workspace. Plan creation is inert. Execution requires a separate
--execute flag, and fetching pinned source requires --allow-source-download.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from uuid import uuid4

sys.dont_write_bytecode = True

DATASET = "princeton-nlp/SWE-bench_Lite"
REVISION = "6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2"
COHORT_SHA256 = "97f681a503ca3e1f63314c5c22c82e6e12be0f7891b2a80b6c16e74042f4fd1f"
CAPACITY, RESERVE = 6 * 1024**3, 4 * 1024**3
MAX_ARCHIVE, MAX_EXPANDED = 80 * 1024**2, 240 * 1024**2
CHECK_RESERVATION = 16 * 1024**2
METADATA_FIELDS = {"instance_id", "repo", "base_commit", "problem_statement", "version", "created_at", "environment_setup_commit"}
IMAGES = {
    "django/django": {"tag": "kairos-investigation-django:build003", "id": "sha256:df8f0ef9be4fb1f710c20ba9738a4ec6fa68d2a1d6422fce277cbfc4b69ed73e"},
    "pytest-dev/pytest": {"tag": "kairos-investigation-pytest:build006", "id": "sha256:3407ec26f4cb3a0a626c5c8412b9e644e319b935a7a5f42ecfc867a9c18192f2"},
}
PREFIXES = {"django/django": "django/", "pytest-dev/pytest": "src/_pytest/"}
MODULE_FILES = ("scripts/qualify006.py", "kairos_api/investigations/registry.py",
    "kairos_api/investigations/sandbox.py", "kairos_api/investigations/patches.py",
    "kairos_api/investigations/output_supervisor.py", "kairos_api/model_runtime.py")
FINAL_STATUSES = {"qualified", "behavioral_mismatch", "environment_failure", "input_unavailable", "scope_excluded"}


class InputUnavailable(ValueError):
    """Required source data is missing, inconsistent or unbound."""


class StorageFailure(ValueError):
    """The aggregate resource gate cannot admit this operation."""


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def no_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Paths must not traverse symlinks")
    return path


def load(path, limit=32 * 1024**2):
    path = no_symlinks(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise InputUnavailable("Required bounded ordinary JSON file is unavailable: " + str(path))
    try:
        return json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as error:
        raise InputUnavailable("Invalid JSON: " + path.name) from error


def immutable(path, value):
    """Never replace evidence; reuse only byte-identical completed captures."""
    path = no_symlinks(path)
    data = encoded(value)
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError("Frozen receipt differs: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # A link publishes an fsynced complete file atomically without replacing a
    # concurrently-created receipt. Orphan .pending files are never receipts.
    temporary = path.parent / ("." + path.name + "." + uuid4().hex + ".pending")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def budget_paths(roots):
    if not roots:
        raise StorageFailure("Declare every owned experiment root with --budget-root")
    paths = sorted({no_symlinks(p) for p in roots}, key=lambda p: (len(p.parts), str(p)))
    unique = [p for i, p in enumerate(paths) if not any(p.is_relative_to(old) for old in paths[:i])]
    if any(not p.is_dir() for p in unique):
        raise StorageFailure("Declared budget roots must already exist")
    return unique


def tree_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file() and not p.is_symlink())


def storage_guard(roots, projected=0):
    """Count all supplied roots once, including source, archives and temp copies."""
    if not isinstance(projected, int) or projected < 0:
        raise ValueError("Projected storage must be a nonnegative byte count")
    roots = budget_paths(roots)
    owned = sum(tree_bytes(p) for p in roots)
    free = min(shutil.disk_usage(p).free for p in roots)
    if owned + projected > CAPACITY or free - projected < RESERVE:
        raise StorageFailure(f"Aggregate storage gate: {owned}+{projected}>{CAPACITY} or {free}-{projected}<{RESERVE}")
    return {"owned_bytes": owned, "projected_bytes": projected, "free_bytes": free,
        "budget_bytes": CAPACITY, "reserve_bytes": RESERVE, "roots": [str(p) for p in roots]}


def covered(path, roots):
    return any(no_symlinks(path).is_relative_to(p) for p in budget_paths(roots))


def dependencies(project):
    project = no_symlinks(project)
    sys.path.insert(0, str(project))
    qualifier = importlib.import_module("scripts.qualify006")
    registry = importlib.import_module("kairos_api.investigations.registry")
    sandbox = importlib.import_module("kairos_api.investigations.sandbox")
    for module, relative in ((qualifier, MODULE_FILES[0]), (registry, MODULE_FILES[1]), (sandbox, MODULE_FILES[2])):
        if Path(module.__file__).resolve() != project / relative:
            raise ValueError("Imported qualification dependency came from a different project")
    return qualifier, registry.CaseRegistry, registry.tree_hash, sandbox.Workspace


def frozen_cohort(project, path):
    cohort = load(path)
    if sha(path) != COHORT_SHA256:
        raise InputUnavailable("Use the exact frozen evidence/evaluation013/cohort/cohort.json bytes")
    for name, key in (("metadata.json", "metadata_sha256"), ("prior-exposures.json", "history_sha256")):
        if sha(project / "evidence/evaluation013/cohort" / name) != cohort[key]:
            raise InputUnavailable("Frozen cohort source identity changed: " + name)
    candidates = cohort["candidates"]
    if (cohort.get("dataset") != DATASET or cohort.get("revision") != REVISION
            or cohort.get("split") != "test" or len(candidates) != 24
            or len({c["instance_id"] for c in candidates}) != 24):
        raise InputUnavailable("Invalid frozen cohort identity")
    return cohort


def hidden_rows(records_path, provenance_path, project, cohort):
    """Validate the pinned full split and exact metadata before inspecting fixes."""
    sidecar = load(provenance_path, 65536)
    actual = sha(records_path)
    if (sidecar.get("dataset") != DATASET or sidecar.get("revision") != REVISION
            or sidecar.get("split") != "test" or sidecar.get("rows") != 300
            or sidecar.get("records_sha256") != actual):
        raise InputUnavailable("Hidden provenance does not bind the pinned full 300-row records JSON")
    rows = load(records_path)
    if not isinstance(rows, list) or len(rows) != 300:
        raise InputUnavailable("Hidden records must contain the complete 300-row Lite test array")
    metadata = load(project / "evidence/evaluation013/cohort/metadata.json")["records"]
    expected = {row["instance_id"]: row for row in metadata}
    index = {}
    for row in rows:
        if not isinstance(row, dict) or not METADATA_FIELDS.issubset(row):
            raise InputUnavailable("Hidden row lacks the seven reviewed metadata fields")
        identifier = row["instance_id"]
        if not isinstance(identifier, str) or identifier in index or identifier not in expected:
            raise InputUnavailable("Hidden split has duplicate, missing or substituted instance IDs")
        if {key: row[key] for key in METADATA_FIELDS} != expected[identifier]:
            raise InputUnavailable("Hidden row metadata differs from the frozen metadata: " + identifier)
        if any(not isinstance(row.get(key), str) for key in ("patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS")):
            raise InputUnavailable("Hidden row lacks required verifier material: " + identifier)
        index[identifier] = row
    if set(index) != set(expected):
        raise InputUnavailable("Hidden split does not match all frozen metadata IDs")
    for candidate in cohort["candidates"]:
        row = index[candidate["instance_id"]]
        if (row["repo"], row["base_commit"], row["problem_statement"]) != (candidate["repository"], candidate["base_commit"], candidate["issue"]):
            raise InputUnavailable("Hidden repository/base/issue does not match the frozen candidate")
    return index


def source_scope(row, qualifier):
    """Apply qualify006 scope, then the stricter frozen014 two-file/40-line gate."""
    _, prefix, _ = qualifier.scope(row)
    patch = row["patch"]
    if len(patch.encode()) > 24000 or "\x00" in patch:
        raise ValueError("Reference patch exceeds the reviewed source patch byte bound")
    if re.search(r"^(?:rename |copy |old mode |new mode |new file mode (?!100644)|deleted file mode|GIT binary|Binary files)", patch, re.M):
        raise ValueError("Only ordinary Python source text changes are in scope")
    headers = re.findall(r"^(?:---|\+\+\+) (.+)$", patch, re.M)
    if not headers or len(headers) % 2:
        raise ValueError("Reference patch lacks paired unified diff headers")
    for raw in headers:
        if raw == "/dev/null":
            continue
        if not re.fullmatch(r"[ab]/[A-Za-z0-9_./-]+", raw):
            raise ValueError("Reference patch has an unsupported path")
        name = raw[2:]
        path = PurePosixPath(name)
        if (not name.startswith(prefix) or path.is_absolute() or ".." in path.parts
                or not name.endswith(".py") or Path(name).name.startswith("test_")
                or any(part.startswith(".") or part in {"tests", "__pycache__", "node_modules"} for part in path.parts)):
            raise ValueError("Reference patch escapes approved Python source files")
    result = subprocess.run(["git", "apply", "--numstat", "-"], input=patch, text=True, capture_output=True, timeout=5)
    rows = [line.split("\t") for line in result.stdout.splitlines()]
    if result.returncode or not rows or any(len(r) != 3 or not r[0].isdigit() or not r[1].isdigit() for r in rows):
        raise ValueError("Reference patch is not an ordinary valid unified text diff")
    names = [r[2] for r in rows]
    changed = sum(int(r[0]) + int(r[1]) for r in rows)
    if len(set(names)) > 2 or not 1 <= changed <= 40:
        raise ValueError("Reference repair exceeds two approved Python source files or 40 changed lines")
    if any(not name.startswith(prefix) or not name.endswith(".py") or name not in [h[2:] for h in headers if h != "/dev/null"] for name in names):
        raise ValueError("Reference numstat paths differ from approved patch headers")
    return {"entry_files": names, "approved_prefix": prefix, "changed_lines": changed,
        "maximum_files": 2, "maximum_changed_lines": 40}


def plan_for(cohort, rows, qualifier, error=None):
    entries = []
    for order, candidate in enumerate(cohort["candidates"]):
        entry = {"order": order, "instance_id": candidate["instance_id"], "repository": candidate["repository"],
            "base_commit": candidate["base_commit"], "split": candidate["split"]}
        if error:
            entry.update(status="input_unavailable", reason=error)
        else:
            row = rows[entry["instance_id"]]
            try:
                scope = source_scope(row, qualifier)
            except (ValueError, KeyError, TypeError, subprocess.SubprocessError) as failure:
                entry.update(status="scope_excluded", reason=str(failure))
            else:
                try:
                    for key in ("FAIL_TO_PASS", "PASS_TO_PASS"):
                        values = json.loads(row[key])
                        if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                            raise ValueError(key + " must be a JSON array of test IDs")
                    if not json.loads(row["FAIL_TO_PASS"]):
                        raise ValueError("No declared behavioral regression")
                    if len(row["test_patch"].encode()) > 1024**2:
                        raise ValueError("Hidden test patch exceeds the bounded 1 MiB verifier material limit")
                    qualifier.test_paths(row)
                except (ValueError, KeyError, TypeError) as failure:
                    entry.update(status="input_unavailable", reason=str(failure), source_scope=scope)
                else:
                    entry.update(status="eligible", reason=None, source_scope=scope)
        entries.append(entry)
    return {"version": "qualification014-plan-v1", "candidates": entries,
        "exclusions": [e for e in entries if e["status"] != "eligible"], "candidate_count": 24,
        "ordering": "Exact frozen013 candidate order and development/holdout assignments; no replacement",
        "scope": "Source eligibility only; no baseline/reference qualification or model execution", "model_calls": 0}


@contextlib.contextmanager
def counted_temporary(root):
    """Route qualify006 localization and both Workspace copies into counted storage."""
    root.mkdir(parents=True, exist_ok=True)
    before = tempfile.tempdir
    tempfile.tempdir = str(root)
    try:
        yield
    finally:
        tempfile.tempdir = before


def pinned_source(row, directory, roots, allow_download, tree_hash):
    source = directory / "source"
    moved_source = directory / "registry" / "cases" / row["instance_id"] / "source"
    if moved_source.is_dir():
        source = moved_source
    receipt_path = directory / "source.json"
    if receipt_path.exists():
        receipt = load(receipt_path)
        if (receipt.get("revision") != row["base_commit"] or receipt.get("repository") != row["repo"]
                or not source.is_dir() or tree_hash(source) != receipt.get("source_digest")):
            raise InputUnavailable("Existing source does not match its immutable pinned receipt")
        return source, receipt
    if source.exists() or (directory / "source.tar.gz").exists():
        raise InputUnavailable("Interrupted unsealed source acquisition requires a new output binding")
    if not allow_download:
        raise InputUnavailable("Pinned source is unavailable; --allow-source-download was not supplied")
    repository, revision = row["repo"], row["base_commit"]
    if repository not in PREFIXES or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise InputUnavailable("Source must use an approved repository and full pinned commit")
    url = "https://codeload.github.com/" + repository + "/tar.gz/" + revision
    archive = directory / "source.tar.gz"
    total = 0
    with urllib.request.urlopen(url, timeout=60) as response, archive.open("xb") as target:
        if response.geturl() != url:
            raise InputUnavailable("Pinned codeload URL unexpectedly redirected")
        while chunk := response.read(1024 * 1024):
            if total + len(chunk) > MAX_ARCHIVE:
                raise InputUnavailable("Source archive exceeds the 80 MiB bounded download")
            storage_guard(roots, len(chunk))
            target.write(chunk)
            target.flush()
            total += len(chunk)
    archive_sha = sha(archive)
    members, expanded, top = [], 0, None
    with tarfile.open(archive) as files:
        for member in files.getmembers():
            parts = member.name.split("/", 1)
            top = top or parts[0]
            if parts[0] != top:
                raise InputUnavailable("Source archive has multiple top-level roots")
            if len(parts) != 2 or not parts[1]:
                continue
            name = parts[1]
            path = PurePosixPath(name)
            if (path.is_absolute() or ".." in path.parts or "\\" in name or member.islnk()
                    or not (member.isfile() or member.isdir() or member.issym())):
                raise InputUnavailable("Source archive contains traversal, hard links or special files")
            if member.issym() and PurePosixPath(member.linkname).is_absolute():
                raise InputUnavailable("Source archive contains an absolute symbolic link")
            member.name = name
            expanded += member.size
            if expanded > MAX_EXPANDED:
                raise InputUnavailable("Expanded source exceeds the 240 MiB safety bound")
            members.append(member)
        if not members:
            raise InputUnavailable("Pinned source archive is empty")
        storage_guard(roots, expanded)
        source.mkdir()
        files.extractall(source, members=members, filter="data")
    receipt = {"repository": repository, "revision": revision, "source_url": url,
        "archive_sha256": archive_sha, "downloaded_bytes": total, "expanded_bytes": expanded,
        "source_digest": tree_hash(source)}
    immutable(receipt_path, receipt)
    archive.unlink()  # Only the newly owned archive; its full hash is now durable.
    return source, receipt


def material_manifest(directory):
    """Retain full file hashes and symlink targets before owned source removal."""
    entries = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            entries.append({"path": path.relative_to(directory).as_posix(), "symlink": os.readlink(path)})
        elif path.is_file():
            entries.append({"path": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    return entries


def check_qualified(baseline, reference, qualifier):
    before, after = qualifier.summary(baseline), qualifier.summary(reference)
    clean_outputs = all(not item.get("output_limit_exceeded") and item.get("raw_output", {}).get("complete") is True for item in (baseline, reference))
    baseline_complete = (baseline.get("passed") is False and not baseline.get("environment_error")
        and baseline.get("returncode") not in (None, 0, 124, 125, 126, 127)
        and before.get("execution_complete") is True and bool(before.get("regression_failed"))
        and isinstance(before.get("tests_run"), int) and before["tests_run"] > 0)
    reference_complete = (reference.get("passed") is True and not reference.get("environment_error")
        and reference.get("returncode") == 0 and after.get("execution_complete") is True
        and after.get("complete") is True and isinstance(after.get("tests_run"), int) and after["tests_run"] > 0)
    qualified = bool(clean_outputs and baseline_complete and reference_complete)
    environment = (not clean_outputs or any(item.get("environment_error") or item.get("returncode") in (None, 124, 125, 126, 127) for item in (baseline, reference))
        or before.get("execution_complete") is not True or after.get("execution_complete") is not True)
    return {"qualified": qualified, "status": "qualified" if qualified else "environment_failure" if environment else "behavioral_mismatch",
        "baseline_summary": before, "reference_summary": after, "baseline_regression_reproduced": bool(baseline_complete),
        "reference_complete_pass": bool(reference_complete), "raw_outputs_complete": clean_outputs}


def captured_check(path, stage, run, binding, roots, source_copy_bytes=0):
    """Never retry a dispatched check whose final result is unavailable."""
    started = path.with_suffix(".started.json")
    if path.exists():
        value = load(path)
        if value.get("binding") != binding or value.get("stage") != stage:
            raise ValueError("Captured check belongs to another binding")
        return value["result"]
    if started.exists():
        raise RuntimeError("A prior " + stage + " check was dispatched without a complete capture; no automatic redispatch")
    storage_guard(roots, CHECK_RESERVATION + source_copy_bytes)
    immutable(started, {"binding": binding, "stage": stage, "dispatch": "May have started; absence of final capture is unknown"})
    result = run()
    immutable(path, {"binding": binding, "stage": stage, "result": result})
    return result


def inspect_images(repositories):
    results = {}
    for repo in sorted(set(repositories)):
        expected = IMAGES[repo]
        actual = subprocess.run(["docker", "image", "inspect", expected["tag"], "--format", "{{.Id}}"], capture_output=True, text=True, timeout=10)
        if actual.returncode or actual.stdout.strip() != expected["id"]:
            raise RuntimeError("Reviewed local image is unavailable or its ID changed: " + expected["tag"])
        results[repo] = expected
    return {"images": results, "runtime_network": "none", "memory": "1g", "cpus": 2, "user": "10001:10001", "timeout_seconds": 120, "pull": "never"}


def cleanup_owned(work, evidence, owner, receipt):
    if work.exists():
        manifest = load(evidence / "material-manifest.json")
        if (not receipt.get("ephemeral_tree", {}).get("cleanup_authorized")
                or load(work / "owner.json") != owner
                or sha(evidence / "material-manifest.json") != receipt["evidence_sha256"]["material-manifest.json"]
                or material_manifest(work) != manifest["files"]):
            raise ValueError("Owned cleanup provenance changed; case tree preserved")
        shutil.rmtree(work)
    immutable(evidence / "cleanup.json", {"binding": owner["binding"], "instance_id": owner["instance_id"],
        "removed_owned_ephemeral_tree": True, "receipt_sha256": sha(evidence / "receipt.json")})


def execute_case(entry, row, out, roots, binding, allow_download, deps):
    qualifier, CaseRegistry, tree_hash, Workspace = deps
    identifier = entry["instance_id"]
    evidence = out / "cases" / identifier
    evidence.mkdir(parents=True, exist_ok=True)
    final_path = evidence / "receipt.json"
    work = out / "work" / identifier
    owner = {"binding": binding, "instance_id": identifier, "purpose": "Owned ephemeral qualification014 source and verification copies"}
    if final_path.exists():
        prior = load(final_path)
        if prior.get("binding") != binding or prior.get("instance_id") != identifier:
            raise ValueError("Completed receipt has a different binding")
        # Check every captured artifact before reusing a terminal result.
        for name, expected in prior.get("evidence_sha256", {}).items():
            if sha(evidence / name) != expected:
                raise ValueError("Captured qualification evidence changed: " + identifier + "/" + name)
        if prior.get("ephemeral_tree"):
            cleanup_owned(work, evidence, owner, prior)
        return prior
    if work.exists():
        if load(work / "owner.json") != owner:
            raise ValueError("Existing case tree is not owned by this binding")
    else:
        work.mkdir(parents=True, exist_ok=False)
        immutable(work / "owner.json", owner)
    receipt = {"version": "qualification014-case-v1", "binding": binding, **entry,
        "qualified": False, "model_calls": 0, "reason": None}
    workspace = None
    try:
        storage_guard(roots)
        source, source_receipt = pinned_source(row, work, roots, allow_download, tree_hash)
        immutable(evidence / "source.json", source_receipt)
        # Workspace owns one original copy and checks owns a second copy.
        # The existing hidden-selector localization owns at most one copy.
        storage_guard(roots, 2 * tree_bytes(source) + CHECK_RESERVATION + 3 * len(row["test_patch"].encode()))
        with counted_temporary(work / "temporary"):
            script, test_scope = qualifier.verifier(row, source)
            immutable(evidence / "test-scope.json", test_scope)
            directory = work / "registry" / "cases" / identifier
            directory.mkdir(parents=True, exist_ok=True)
            # Move the owned tree rather than copying a third persistent tree.
            if not (directory / "source").exists():
                source.rename(directory / "source")
            source = directory / "source"
            for name, text in (("reference.patch", row["patch"]), ("test.patch", row["test_patch"]), ("verify.py", script)):
                path = directory / name
                if path.exists() and path.read_text() != text:
                    raise ValueError("Frozen hidden verification material changed")
                path.write_text(text)
            case = {"id": identifier, "title": row["problem_statement"].splitlines()[0], "issue": row["problem_statement"],
                "repository": row["repo"], "revision": row["base_commit"], "split": entry["split"],
                "source_url": source_receipt["source_url"], "entry_files": entry["source_scope"]["entry_files"],
                "approved_prefix": entry["source_scope"]["approved_prefix"], "image": IMAGES[row["repo"]]["id"],
                "qualified": False, "qualification_registration": "Internal preflight only; final independent receipt controls qualification",
                "command": ["python", "/verification/verify.py"], "source_digest": tree_hash(source),
                "reference_digest": sha(directory / "reference.patch"),
                "verification_digest": hashlib.sha256((row["test_patch"] + script).encode()).hexdigest(),
                "provenance": "Frozen013 fresh metadata candidate. Public pretraining exposure is unknown. Reference-derived entry files must not become inference localization hints."}
            immutable(evidence / "case-definition.json", case)
            registry_path = work / "registry.json"
            immutable(registry_path, {"version": "repository-cases-v1", "cases": [case]})
            workspace = Workspace(CaseRegistry(registry_path, work / "registry"), case)
            baseline = captured_check(evidence / "baseline.json", "baseline", workspace.checks, binding, roots,
                tree_bytes(workspace.root) + len(row["test_patch"].encode()))
            workspace.propose(row["patch"])
            reference = captured_check(evidence / "reference.json", "reference", workspace.checks, binding, roots,
                tree_bytes(workspace.root) + len(row["test_patch"].encode()))
            receipt.update(check_qualified(baseline, reference, qualifier))
            receipt["reason"] = None if receipt["qualified"] else "Complete baseline regression failure and complete reference pass were not both reproduced"
    except Exception as error:
        receipt.update(status="input_unavailable" if isinstance(error, InputUnavailable) else "environment_failure",
            qualified=False, reason=type(error).__name__ + ": " + str(error)[:1000])
    finally:
        if workspace is not None:
            workspace.close()
    # Both checks (when dispatched) retain complete bounded raw bytes and hashes
    # in baseline.json/reference.json. The manifest also hashes every remaining
    # source file before deleting only this binding's newly created case tree.
    immutable(evidence / "material-manifest.json", {"binding": binding, "files": material_manifest(work)})
    receipt["evidence_sha256"] = {p.name: sha(p) for p in sorted(evidence.glob("*.json")) if p != final_path and not p.name.endswith(".started.json")}
    receipt["ephemeral_tree"] = {"path": str(work), "ownership_sha256": sha(work / "owner.json"), "cleanup_authorized": True}
    immutable(final_path, receipt)
    cleanup_owned(work, evidence, owner, receipt)
    return receipt


def report(plan, receipts, execute):
    entries = [{**e, **receipts.get(e["instance_id"], {})} for e in plan["candidates"]]
    counts = {status: sum(e["status"] == status for e in entries) for status in sorted(FINAL_STATUSES | {"eligible"})}
    by_split = {}
    for repository in PREFIXES:
        by_split[repository] = {}
        for split in ("development", "holdout"):
            selected = [e for e in entries if e["repository"] == repository and e["split"] == split]
            by_split[repository][split] = {"frozen": len(selected), "eligible": sum(e.get("source_scope") is not None and e["status"] != "scope_excluded" for e in selected), "qualified": sum(e["status"] == "qualified" for e in selected)}
    return {"version": "qualification014-report-v1", "frozen_candidates": 24, "counts": counts, "by_repository_split": by_split,
        "execution_requested": execute, "performed": any("baseline_summary" in e for e in entries), "all_candidates_accounted": len(entries) == 24,
        "execution_complete": bool(execute and all(e["status"] in FINAL_STATUSES for e in entries)),
        "qualification_complete": bool(execute and counts["eligible"] == 0 and counts["environment_failure"] == 0 and counts["input_unavailable"] == 0),
        "qualified": counts["qualified"], "candidates": entries, "model_calls": 0, "case_substitutions": 0,
        "scope": "Independent fresh-case preflight only; no inference, evaluation score, training or official benchmark result"}


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    value.add_argument("--cohort", type=Path)
    value.add_argument("--hidden-records", type=Path, required=True)
    value.add_argument("--hidden-provenance", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--budget-root", type=Path, action="append", required=True)
    value.add_argument("--execute", action="store_true")
    value.add_argument("--allow-source-download", action="store_true")
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        project, out = no_symlinks(args.project), no_symlinks(args.output)
        cohort_path = args.cohort or project / "evidence/evaluation013/cohort/cohort.json"
        cohort = frozen_cohort(project, cohort_path)
        roots = budget_paths(args.budget_root)
        if not covered(project / ".runtime/investigations", roots):
            raise StorageFailure("Budget roots must include the historical project .runtime/investigations tree and all other owned experiment roots")
        if not covered(out, roots) or not covered(args.hidden_records, roots) or not covered(args.hidden_provenance, roots):
            raise StorageFailure("Output, hidden records and provenance must all belong to counted experiment roots")
        storage = storage_guard(roots)
        deps = dependencies(project)
        error = None
        try:
            index = hidden_rows(args.hidden_records, args.hidden_provenance, project, cohort)
        except (ValueError, OSError, KeyError, TypeError) as failure:
            index, error = {}, type(failure).__name__ + ": " + str(failure)
        binding_inputs = {"version": "qualification014-binding-v1", "cohort_sha256": sha(cohort_path),
            "hidden_records_sha256": sha(args.hidden_records) if args.hidden_records.is_file() else None,
            "hidden_provenance_sha256": sha(args.hidden_provenance) if args.hidden_provenance.is_file() else None,
            "implementation_sha256": sha(Path(__file__)), "dependency_sha256": {name: sha(project / name) for name in MODULE_FILES},
            "images": IMAGES, "allow_source_download": args.allow_source_download,
            "budget_roots": [str(p) for p in roots], "limits": {"files": 2, "changed_lines": 40}}
        binding = digest(binding_inputs)
        if out.exists() and not (out / "binding.json").is_file():
            raise ValueError("Output must be fresh or already owned by this exact binding")
        out.mkdir(parents=True, exist_ok=True)
        immutable(out / "binding.json", {"binding": binding, **binding_inputs})
        frozen = plan_for(cohort, index, deps[0], error)
        immutable(out / "plan.json", {"binding": binding, **frozen})
        receipts = {}
        image_error = None
        if args.execute and any(e["status"] == "eligible" for e in frozen["candidates"]):
            pending = [e for e in frozen["candidates"] if e["status"] == "eligible"
                and not (out / "cases" / e["instance_id"] / "receipt.json").exists()]
            if pending:
                try:
                    images = inspect_images([e["repository"] for e in frozen["candidates"] if e["status"] == "eligible"])
                    immutable(out / "images.json", {"binding": binding, **images})
                except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as failure:
                    image_error = type(failure).__name__ + ": " + str(failure)
            for entry in frozen["candidates"]:
                if entry["status"] != "eligible":
                    continue
                identifier = entry["instance_id"]
                final_path = out / "cases" / identifier / "receipt.json"
                if image_error and not final_path.exists():
                    receipts[identifier] = {"version": "qualification014-case-v1", "binding": binding, **entry,
                        "status": "environment_failure", "qualified": False, "reason": image_error, "model_calls": 0, "evidence_sha256": {}}
                    immutable(final_path, receipts[identifier])
                else:
                    receipts[identifier] = execute_case(entry, index[identifier], out, roots, binding, args.allow_source_download, deps)
                print(json.dumps({"phase": "qualification_case", "instance_id": identifier, "split": entry["split"],
                    "status": receipts[identifier]["status"], "qualified": receipts[identifier]["qualified"]}), flush=True)
        result = {"binding": binding, **report(frozen, receipts, args.execute), "storage_before": storage}
        # Plan and execution use separate terminal reports. Repeating execution
        # reuses completed receipts and creates no second verifier dispatch.
        report_path = out / ("report.json" if args.execute else "plan-report.json")
        if report_path.exists():
            prior = load(report_path)
            # Free space and output-file sizes are operational, not identity.
            result["storage_before"] = prior["storage_before"]
        immutable(report_path, result)
        print(json.dumps({"binding": binding, "output": str(out), "counts": result["counts"], "qualified": result["qualified"],
            "execution_requested": args.execute, "qualification_complete": result["qualification_complete"], "model_calls": 0}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("Qualification refused: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
