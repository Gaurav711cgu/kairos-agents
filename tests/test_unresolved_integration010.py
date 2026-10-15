"""Real PostgreSQL/Docker acceptance for a reference-free software fixture.

These tests execute a fixture-authored patch, not model inference. They establish
registration, isolation, durable capture, independent checks and replay behavior;
they provide no evidence about model repair effectiveness. The caller must start
its own PostgreSQL and Docker beforehand. No service or image is downloaded.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from scripts.repair010.feedback010 import FeedbackWorker010
from scripts.repair010.unresolved_registry010 import (
    REGISTRY_VERSION, TASK_KIND, VERIFIER_COMMAND, BaselineReceipt,
    UnresolvedCaseRegistry010,
)
from kairos_api.investigations.context_v5 import source_handle
from kairos_api.investigations.registry import tree_hash
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.routes import create_investigation_router
from kairos_api.investigations.sandbox import Workspace
from kairos_api.migrations import apply
from kairos_api.model_runtime import digest


PINNED_IMAGE = "sha256:df8f0ef9be4fb1f710c20ba9738a4ec6fa68d2a1d6422fce277cbfc4b69ed73e"
FIXTURE_SOURCE = "def add(a, b):\n    return a - b\n"
VERIFIER = '''"""Reviewed integration fixture verifier, separate from candidate source."""
import json
import os
import sys
import unittest
from package.logic import add

class Regression(unittest.TestCase):
    def test_positive_addition(self):
        self.assertEqual(add(2, 3), 5)

class Existing(unittest.TestCase):
    def test_additive_identity_at_zero(self):
        self.assertEqual(add(0, 0), 0)

selection = os.environ.get("KAIROS_SUITE", "combined")
classes = {"regression": [Regression], "existing": [Existing],
           "combined": [Regression, Existing]}[selection]
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in classes)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("KAIROS_VERIFIER_RESULT " + json.dumps({"complete": True,
      "tests_run": result.testsRun, "failures": len(result.failures) + len(result.errors)}), flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
'''


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qualify_suite(directory, task, suite):
    """Trusted fixture qualification with a fixed command and bounded container."""
    name = "kairos010-qualify-" + uuid4().hex
    command = [
        "docker", "run", "--pull=never", "--rm", "--name", name,
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--user=10001:10001",
        "--cpus=2", "--memory=1g", "--pids-limit=128",
        "--tmpfs=/tmp:rw,nosuid,size=128m",
        "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/workspace",
        "-e", "KAIROS_SUITE=" + suite,
        "-v", str(directory / "source") + ":/workspace:ro",
        "-v", str(directory / "verify.py") + ":/verification/verify.py:ro",
        "-w", "/workspace", task["image"], *VERIFIER_COMMAND,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
    markers = [line.removeprefix("KAIROS_VERIFIER_RESULT ")
               for line in result.stdout.splitlines() if line.startswith("KAIROS_VERIFIER_RESULT ")]
    assert len(markers) == 1, (result.returncode, result.stdout, result.stderr)
    completion = json.loads(markers[0])
    assert len(result.stdout.encode()) + len(result.stderr.encode()) < 16_000
    return {
        "version": "independent-unresolved-baseline-v1", "captured_by": "trusted-qualifier",
        "run_id": "fixture_qualification_001", "task_id": task["id"], "suite": suite,
        **{field: task[field] for field in (
            "revision", "source_digest", "verification_digest", "image", "environment_digest", "command")},
        "completed": completion["complete"], "passed": result.returncode == 0,
        "returncode": result.returncode, "tests_run": completion["tests_run"],
        "failures": completion["failures"], "environment_error": False, "timed_out": False,
        "output_limit_exceeded": False, "output_complete": True,
        "stdout": result.stdout, "stderr": result.stderr,
    }


@pytest.fixture
def integration(tmp_path, monkeypatch):
    url = os.environ.get("KAIROS_REPAIR010_DATABASE_URL")
    if not url:
        pytest.skip("KAIROS_REPAIR010_DATABASE_URL required; caller owns PostgreSQL/Docker startup")
    settings = conninfo_to_dict(url)
    if settings.get("host") not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Integration acceptance requires an explicitly supplied loopback PostgreSQL instance")
    image = os.environ.get("KAIROS_REPAIR010_IMAGE", PINNED_IMAGE)
    assert image.startswith("sha256:") and len(image) == 71
    subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                   check=True, capture_output=True, timeout=10)
    subprocess.run(["docker", "image", "inspect", image], check=True, capture_output=True, timeout=10)
    root = tmp_path / "registered runtime"
    directory = root / "cases" / "unresolved-fixture"
    package = directory / "source/package"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "logic.py").write_text(FIXTURE_SOURCE)
    (directory / "test.patch").write_text("")
    (directory / "verify.py").write_text(VERIFIER)
    task = {
        "task_kind": TASK_KIND, "id": "unresolved-fixture",
        "title": "Reference-free integration fixture",
        "issue": "add(2, 3) should return 5, but returns -1. Preserve existing addition behavior.",
        "repository": "software-fixture/package", "revision": "a" * 40,
        "approved_prefix": "package/", "entry_files": ["package/logic.py"],
        "entry_lines": {"package/logic.py": 1},
        "localization": "reviewer-provided-source-entry-files",
        "provenance": "Software acceptance fixture; reviewer supplied entry file; no reference repair exists or is used.",
        "split": "unresolved", "image": image, "command": list(VERIFIER_COMMAND),
        "source_digest": tree_hash(directory / "source"),
        "verification_digest": hashlib.sha256(VERIFIER.encode()).hexdigest(),
        "environment_digest": digest({
            "image": image, "command": VERIFIER_COMMAND, "network": "none", "user": "10001:10001",
            "cpus": 2, "memory": "1g", "qualification_suite": "Trusted KAIROS_SUITE selector; combined for candidate checks",
        }),
        "verification_files": {"test_patch": file_sha(directory / "test.patch"), "verify_py": file_sha(directory / "verify.py")},
        "baseline_receipts": {}, "qualified": True,
    }
    (directory / "baseline").mkdir()
    for suite in ("regression", "existing"):
        receipt = _qualify_suite(directory, task, suite)
        BaselineReceipt.model_validate(receipt)
        path = directory / "baseline" / (suite + ".json")
        path.write_text(json.dumps(receipt, indent=2))
        task["baseline_receipts"][suite] = file_sha(path)
    manifest = tmp_path / "reviewed-tasks.json"
    manifest.write_text(json.dumps({"version": REGISTRY_VERSION, "cases": [task]}, indent=2))
    registry = UnresolvedCaseRegistry010(manifest, root)
    assert registry.get(task["id"]) == task
    model_manifest = tmp_path / "fixture-profile.json"
    model_manifest.write_text(json.dumps({"provider": "mechanical-software-fixture", "model_inference": False}))
    monkeypatch.setenv("KAIROS_INVESTIGATION_MODEL_MANIFEST", str(model_manifest))
    database = "kairos010_integration_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    repository = None
    try:
        isolated_url = make_conninfo(url, dbname=database)
        apply(isolated_url)
        repository = InvestigationRepository(isolated_url, tmp_path / "blobs", registry)
        repository.initialize()
        yield {"repository": repository, "registry": registry, "task": task,
               "directory": directory, "manifest": manifest}
    finally:
        if repository:
            repository.close()
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


class MechanicalFixtureProvider:
    """Prewritten software-test action; never label its result a model repair."""
    def __init__(self):
        self.calls = 0

    def verify_profile(self):
        return {"provider": "mechanical-software-fixture", "model_inference": False}

    def prepare(self, case, configuration, observations, budgets):
        sources = [item["result"] for item in observations if item["result"].get("reference")]
        assert sources
        reference = sources[0]["reference"]
        handle = source_handle(reference)
        action = {"action": "propose_patch", "edits": [{
            "source_id": handle, "start_line": 2, "end_line": 2, "new": "    return a + b\n",
        }]}
        return {"software_fixture_action": action}, {
            "version": "mechanical-software-fixture-v1", "allowed_actions": ["propose_patch", "final_result"],
            "reference_bindings": {handle: reference}, "source_catalog": sources,
            "selection": {"provenance": "Prewritten fixture action; not model inference", "budgets": budgets},
        }

    def __call__(self, request, remaining):
        self.calls += 1
        return {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(request["software_fixture_action"]),
        }}], "provider": "mechanical-software-fixture", "model_inference": False}


def test_reference_free_task_completes_durable_sandbox_journey_and_read_only_replay(integration):
    repository = integration["repository"]
    app = FastAPI()
    app.include_router(create_investigation_router(
        lambda: "fixture-tenant", lambda: "fixture-command", lambda: "fixture-tenant", lambda: repository))
    client = TestClient(app)
    command = {"task_id": integration["task"]["id"], "configuration": "loop-v7"}
    initial = client.post("/api/investigations", json=command)
    assert initial.status_code == 202
    identifier = initial.json()["id"]
    assert client.post("/api/investigations", json=command).json()["id"] == identifier
    provider = MechanicalFixtureProvider()
    final = FeedbackWorker010(repository, provider, Workspace).run_once()
    assert final["id"] == identifier
    assert final["outcome"] == "verified_repair"
    assert (final["model_calls"], final["patch_count"], final["check_count"]) == (1, 1, 1)
    assert final["integrity"]["verified"] is True
    check = next(step["result"]["body"] for step in final["steps"] if step["name"] == "run_checks")
    assert check["passed"] is True and check["verification_complete"] is True
    assert check["tests_run"] == 2 and check["returncode"] == 0
    assert check["raw_output"]["complete"] is True
    assert provider.calls == 1
    assert integration["directory"].joinpath("source/package/logic.py").read_text() == FIXTURE_SOURCE
    assert not integration["directory"].joinpath("reference.patch").exists()
    replay = client.get("/api/investigations/" + identifier + "/replay")
    assert replay.status_code == 200
    assert replay.json()["network_calls"] == replay.json()["tool_executions"] == 0
    assert replay.json()["investigation"] == repository.read(identifier, "fixture-tenant")
    assert provider.calls == 1
    patch = client.get("/api/investigations/" + identifier + "/patch")
    assert patch.status_code == 200 and "+    return a + b" in patch.text
    bundle = client.get("/api/investigations/" + identifier + "/bundle")
    assert bundle.status_code == 200 and bundle.json()["integrity"]["verified"] is True
    assert client.post("/api/investigations", json={**command, "url": "https://invalid.example/source"}).status_code == 422


def test_changed_registered_source_after_enqueue_refuses_dispatch(integration):
    repository = integration["repository"]
    record = repository.enqueue("fixture-tenant", "changed-source", integration["task"]["id"], "loop-v7")
    integration["directory"].joinpath("source/package/logic.py").write_text("changed after durable enqueue\n")
    provider = MechanicalFixtureProvider()
    final = FeedbackWorker010(repository, provider, Workspace).run_once()
    assert final["id"] == record["id"]
    assert final["outcome"] == "environment_failure"
    assert "Pinned source snapshot mismatch" in final["summary"]
    assert final["model_calls"] == final["patch_count"] == final["check_count"] == provider.calls == 0
    assert final["integrity"]["verified"] is True


def test_optional_cli_runner_owns_database_checks_and_saved_report_without_inference(integration, monkeypatch):
    """Exercise the real CLI orchestration with a plainly prewritten fixture action.

    Only account preflight and the provider are replaced. Schema migration,
    source fingerprinting, the private PostgreSQL process, worker, Docker checks,
    result receipts and scoped shutdown use the actual implementation.
    """
    import argparse
    import shutil
    import sys

    import kairos_api
    import scripts.study010 as study010

    pg_ctl = shutil.which("pg_ctl")
    if not shutil.which("initdb") or not pg_ctl:
        pytest.skip("Existing native PostgreSQL tools required for the optional runner acceptance")
    checkout = Path(kairos_api.__file__).resolve().parents[1]
    runtime = integration["manifest"].parent / "cli execution"
    providers = []
    original_helpers = study010._helpers()

    class RunnerFixtureProvider(MechanicalFixtureProvider):
        def __init__(self, *values, **settings):
            super().__init__()
            assert settings == {"model_id": study010.REQUESTED_MODEL}
            providers.append(self)

    def fixture_identity(_):
        return Path(sys.executable), {
            "cli_version": "mechanical-software-fixture-no-model", "cli_sha256": file_sha(Path(sys.executable)),
            "requested_model": study010.REQUESTED_MODEL, "resolved_model": None,
            "scope": "Software acceptance fixture; no account preflight or model inference occurred",
        }

    monkeypatch.setattr(study010, "_helpers", lambda: (RunnerFixtureProvider, *original_helpers[1:]))
    monkeypatch.setattr(study010, "cli_identity010", fixture_identity)
    arguments = argparse.Namespace(checkout=checkout, manifest=integration["manifest"],
        case_root=integration["registry"].runtime, task_id=integration["task"]["id"],
        runtime=runtime, codex=None)
    original_manifest = os.environ.get("KAIROS_INVESTIGATION_MODEL_MANIFEST")
    result = study010.run010(arguments)
    assert result["verified"] is True and result["outcome"] == "verified_repair"
    assert result["source_unchanged"] is True and result["evidence_verified"] is True
    assert result["failure"] is None and result["cleanup_errors"] == []
    assert (result["cli_dispatches"], result["patches"], result["checks"]) == (1, 1, 1)
    assert len(providers) == 1 and providers[0].calls == 1
    record = json.loads((runtime / "record.json").read_text())
    check = next(step["result"]["body"] for step in record["steps"] if step["name"] == "run_checks")
    assert check["tests_run"] == 2 and check["verification_complete"] and check["passed"]
    assert check["raw_output"]["complete"] is True
    assert os.environ.get("KAIROS_INVESTIGATION_MODEL_MANIFEST") == original_manifest
    frozen = json.loads((runtime / "experiment.json").read_text())
    assert frozen["source"] == study010._source_identity(checkout)
    assert "scripts/study010.py" in frozen["source"]
    assert all("scripts/repair010/" + filename in frozen["source"] for filename in (
        "feedback010.py", "codex_context010.py", "codex_transport010.py", "unresolved_registry010.py"))
    stopped = subprocess.run([pg_ctl, "-D", str(runtime / "postgres-data"), "status"],
                             capture_output=True, timeout=10)
    assert stopped.returncode != 0
    assert study010.report010(runtime) == result
    assert study010.run010(arguments) == result
    assert len(providers) == 1 and providers[0].calls == 1
    assert integration["directory"].joinpath("source/package/logic.py").read_text() == FIXTURE_SOURCE
