"""Software-only fixtures; these tests make no model repair-quality claim."""
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import scripts.repair010.unresolved_registry010 as module
from scripts.repair010.unresolved_registry010 import (
    REGISTRY_VERSION, TASK_KIND, VERIFIER_COMMAND, UnresolvedCaseRegistry010,
    verify_reviewed_case, validate_reviewed_case,
)
from kairos_api.investigations.registry import tree_hash
from kairos_api.investigations.sandbox import Workspace


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def registered(tmp_path, monkeypatch):
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3))
    runtime = tmp_path / "registered runtime"
    directory = runtime / "cases" / "unresolved-example"
    source = directory / "source" / "package"
    source.mkdir(parents=True)
    (source / "logic.py").write_text("def value(x):\n    return x + 1\n")
    (directory / "test.patch").write_text("")
    (directory / "verify.py").write_text("# Reviewed verifier fixture; not executed in software tests.\n")
    (directory / "baseline").mkdir()
    verification = hashlib.sha256(
        ((directory / "test.patch").read_text() + (directory / "verify.py").read_text()).encode()
    ).hexdigest()
    task = {
        "task_kind": TASK_KIND,
        "id": "unresolved-example",
        "title": "An independently reported Python defect",
        "issue": "The value function returns an unexpected value for an input.",
        "repository": "example/package",
        "revision": "a" * 40,
        "approved_prefix": "package/",
        "entry_files": ["package/logic.py"],
        "entry_lines": {"package/logic.py": 1},
        "localization": "reviewer-provided-source-entry-files",
        "provenance": "Software fixture only. Entry source was provided by the reviewer; no solution reference is used.",
        "split": "unresolved",
        "image": "sha256:" + "b" * 64,
        "command": list(VERIFIER_COMMAND),
        "source_digest": tree_hash(directory / "source"),
        "verification_digest": verification,
        "environment_digest": "c" * 64,
        "verification_files": {"test_patch": sha(directory / "test.patch"), "verify_py": sha(directory / "verify.py")},
        "baseline_receipts": {},
        "qualified": True,
    }
    for suite in ("regression", "existing"):
        failed = suite == "regression"
        receipt = {
            "version": "independent-unresolved-baseline-v1", "captured_by": "trusted-qualifier",
            "run_id": "independent_run_001", "task_id": task["id"], "suite": suite,
            **{field: copy.deepcopy(task[field]) for field in (
                "revision", "source_digest", "verification_digest", "image", "environment_digest", "command")},
            "completed": True, "passed": not failed, "returncode": 1 if failed else 0,
            "tests_run": 2, "failures": 1 if failed else 0, "environment_error": False,
            "timed_out": False, "output_limit_exceeded": False, "output_complete": True,
            "stdout": "FAILED assertion" if failed else "2 passed", "stderr": "",
        }
        path = directory / "baseline" / (suite + ".json")
        path.write_text(json.dumps(receipt))
        task["baseline_receipts"][suite] = sha(path)
    manifest = tmp_path / "tasks.json"

    def save():
        manifest.write_text(json.dumps({"version": REGISTRY_VERSION, "cases": [task]}))

    def change_receipt(suite, field, value, rebind=True):
        path = directory / "baseline" / (suite + ".json")
        receipt = json.loads(path.read_text())
        receipt[field] = value
        path.write_text(json.dumps(receipt))
        if rebind:
            task["baseline_receipts"][suite] = sha(path)
        save()

    save()
    registry = UnresolvedCaseRegistry010(manifest, runtime)
    return SimpleNamespace(task=task, directory=directory, manifest=manifest,
                           registry=registry, save=save, change_receipt=change_receipt)


def test_unresolved_qualifies_without_reference_or_credentials(registered, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not (registered.directory / "reference.patch").exists()
    before = registered.manifest.read_bytes()
    case = registered.registry.get("unresolved-example")
    assert case["task_kind"] == TASK_KIND
    assert case["qualified"] is True
    assert registered.manifest.read_bytes() == before
    assert len(registered.registry.fingerprint(case)) == 64


def test_existing_workspace_reads_source_without_reference(registered):
    case = registered.registry.get("unresolved-example")
    workspace = Workspace(registered.registry, case)
    try:
        result = workspace.read_original("package/logic.py", 1, 2)
        assert "return x + 1" in result["text"]
        assert workspace.root != registered.directory / "source"
        workspace.root.joinpath("package/logic.py").write_text("changed candidate\n")
        assert "return x + 1" in registered.directory.joinpath("source/package/logic.py").read_text()
    finally:
        workspace.close()


def test_helper_integrates_with_plain_existing_registry(registered):
    base = module.CaseRegistry(registered.manifest, registered.registry.runtime)
    assert validate_reviewed_case(registered.task) == registered.task
    assert verify_reviewed_case(base, registered.task) is None


def test_reference_material_is_never_read(registered, monkeypatch):
    reference = registered.directory / "reference.patch"
    reference.write_text("This sibling is not used by unresolved task registration.")
    original = Path.read_bytes

    def guarded(path):
        assert path.name != "reference.patch", "Reference repair must not be read"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    assert registered.registry.get("unresolved-example")["qualified"]


@pytest.mark.parametrize("field,value", [
    ("source_url", "https://example.invalid/source"),
    ("reference_digest", "d" * 64),
    ("host_path", "/private/secret"),
    ("credentials", "never accepted"),
])
def test_unknown_task_fields_rejected(registered, field, value):
    registered.task[field] = value
    registered.save()
    with pytest.raises(ValidationError):
        registered.registry.manifest()


@pytest.mark.parametrize("field,value", [
    ("id", "../outside"), ("id", "/tmp/outside"), ("id", "bad\\path"),
    ("approved_prefix", "../"), ("approved_prefix", "/package/"),
    ("approved_prefix", "package"), ("approved_prefix", "package//"),
    ("entry_files", ["package/../secret.py"]),
    ("entry_files", ["/tmp/secret.py"]),
    ("entry_files", ["package/tests/test_case.py"]),
    ("entry_files", ["package/.private.py"]),
    ("entry_files", ["package/logic.py", "package/logic.py"]),
    ("entry_lines", {}), ("entry_lines", {"package/logic.py": 0}),
    ("command", ["sh", "-c", "arbitrary command"]),
    ("image", "python:latest"), ("qualified", "true"),
    ("task_kind", "unreviewed-arbitrary-v1"),
])
def test_strict_paths_and_metadata(registered, field, value):
    registered.task[field] = value
    registered.save()
    with pytest.raises((ValueError, ValidationError)):
        registered.registry.manifest()


@pytest.mark.parametrize("where", ["case", "source", "source_file", "verifier", "baseline"])
def test_symlinks_rejected(registered, tmp_path, where):
    directory = registered.directory
    target = {
        "case": directory,
        "source": directory / "source",
        "source_file": directory / "source/package/logic.py",
        "verifier": directory / "verify.py",
        "baseline": directory / "baseline",
    }[where]
    outside = tmp_path / ("outside-" + where)
    target.rename(outside)
    target.symlink_to(outside, target_is_directory=outside.is_dir())
    with pytest.raises(ValueError, match="links|symlink"):
        registered.registry.get("unresolved-example")


def test_unrelated_source_symlink_rejected_even_when_tree_hash_omits_it(registered, tmp_path):
    outside = tmp_path / "secret.py"
    outside.write_text("secret = 1\n")
    (registered.directory / "source/package/alias.py").symlink_to(outside)
    with pytest.raises(ValueError, match="links"):
        registered.registry.get("unresolved-example")


def test_hard_link_source_rejected(registered, tmp_path):
    os.link(registered.directory / "source/package/logic.py", tmp_path / "external-alias.py")
    with pytest.raises(ValueError, match="links"):
        registered.registry.get("unresolved-example")


@pytest.mark.parametrize("where", ["source/package/logic.py", "test.patch", "verify.py", "baseline/regression.json"])
def test_modified_inputs_refuse_qualification(registered, where):
    path = registered.directory / where
    path.write_text(path.read_text() + "\nchanged after capture\n")
    with pytest.raises(ValueError, match="mismatch"):
        registered.registry.get("unresolved-example")


@pytest.mark.parametrize("suite,field,value", [
    ("regression", "passed", True), ("regression", "returncode", 0),
    ("regression", "returncode", 124), ("regression", "returncode", 125),
    ("regression", "returncode", -9), ("regression", "failures", 0),
    ("existing", "passed", False), ("existing", "returncode", 1),
    ("existing", "failures", 1), ("existing", "tests_run", 0),
    ("regression", "tests_run", 0), ("regression", "failures", 3),
    ("regression", "completed", False), ("existing", "completed", False),
    ("regression", "environment_error", True), ("regression", "timed_out", True),
    ("regression", "output_limit_exceeded", True), ("existing", "output_complete", False),
    ("existing", "source_digest", "d" * 64),
    ("existing", "verification_digest", "d" * 64),
    ("existing", "environment_digest", "d" * 64),
    ("existing", "image", "sha256:" + "d" * 64),
    ("existing", "revision", "d" * 40),
    ("existing", "suite", "regression"), ("existing", "task_id", "another-task"),
    ("existing", "run_id", "another_run_001"),
    ("existing", "command", ["python", "arbitrary.py"]),
    ("existing", "captured_by", "model"), ("existing", "tests_run", True),
])
def test_false_or_unbound_baselines_rejected_even_after_manifest_rehash(registered, suite, field, value):
    registered.change_receipt(suite, field, value)
    with pytest.raises((ValueError, ValidationError)):
        registered.registry.get("unresolved-example")


def test_unknown_baseline_fields_rejected(registered):
    registered.change_receipt("regression", "unreviewed", True)
    with pytest.raises(ValidationError):
        registered.registry.get("unresolved-example")


def test_qualified_false_stays_unavailable(registered):
    registered.task["qualified"] = False
    registered.save()
    with pytest.raises(HTTPException) as error:
        registered.registry.get("unresolved-example")
    assert error.value.status_code == 409


def test_missing_baseline_refuses_qualified_flag(registered):
    (registered.directory / "baseline/existing.json").unlink()
    with pytest.raises(FileNotFoundError):
        registered.registry.get("unresolved-example")


def test_missing_identifier_does_not_resolve_browser_path(registered):
    with pytest.raises(HTTPException) as error:
        registered.registry.get("../../private")
    assert error.value.status_code == 404


def test_entry_line_must_exist(registered):
    registered.task["entry_lines"]["package/logic.py"] = 300
    registered.save()
    with pytest.raises(ValueError, match="exceeds"):
        registered.registry.get("unresolved-example")


def test_strict_manifest_and_duplicate_fields(registered):
    value = json.loads(registered.manifest.read_text())
    value["host_path"] = "/secret"
    registered.manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Unknown"):
        registered.registry.manifest()
    registered.manifest.write_text('{"version":"reviewed-task-registry-v1","version":"other","cases":[]}')
    with pytest.raises(ValueError, match="Duplicate"):
        registered.registry.manifest()


def test_duplicate_task_identifiers_rejected(registered):
    registered.manifest.write_text(json.dumps({"version": REGISTRY_VERSION,
                                               "cases": [registered.task, registered.task]}))
    with pytest.raises(ValueError, match="unique"):
        registered.registry.manifest()


def test_historical_behavior_delegates_unchanged(registered, monkeypatch):
    historical = {"id": "old-case", "qualified": True, "some_historical_field": "retained"}
    registered.manifest.write_text(json.dumps({"version": "repository-cases-v1", "cases": [historical], "selection": {}}))
    before = registered.manifest.read_bytes()
    called = []
    monkeypatch.setattr(module.CaseRegistry, "verify", lambda self, case: called.append(case))
    assert registered.registry.get("old-case") == historical
    registered.registry.verify(historical)
    assert called == [historical]
    assert registered.registry.directory(historical) == registered.registry.runtime / "cases/old-case"
    assert registered.manifest.read_bytes() == before
