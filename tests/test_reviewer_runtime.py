"""Ownership and bootstrap regressions do not start Docker or network services."""
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest
from scripts import reviewer, reviewer_runtime as runtime


def test_recycled_pid_is_never_signalled(monkeypatch):
    monkeypatch.setattr(runtime, "process_identity", lambda _pid: "new process identity")
    monkeypatch.setattr(os, "kill", lambda *_: pytest.fail("Unrelated process was signalled"))
    assert not runtime.terminate_owned({"pid": 42, "identity": "original process identity"})


def test_conflicting_container_is_never_stopped(tmp_path, monkeypatch):
    state = runtime.ensure_runtime(tmp_path)
    monkeypatch.setattr(runtime, "docker_inspect", lambda *_: {"Config": {"Labels": {runtime.LABEL: "another-owner"}}, "State": {"Running": True}})
    with pytest.raises(RuntimeError, match="another owner"):
        runtime.stop(tmp_path)
    assert json.loads((tmp_path / "owner.json").read_text()) == state


def test_same_runtime_retains_owner_and_resource_names(tmp_path):
    original = runtime.ensure_runtime(tmp_path)
    assert runtime.ensure_runtime(tmp_path) == original
    assert runtime.resource_names(tmp_path) == runtime.resource_names(tmp_path)
    assert runtime.resource_names(tmp_path) != runtime.resource_names(tmp_path / "other")
    assert (tmp_path / "owner.json").stat().st_mode & 0o777 == 0o600


def test_runtime_and_pending_private_file_symlinks_are_rejected(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir(); linked = tmp_path / "linked"; linked.symlink_to(outside)
    with pytest.raises(RuntimeError): runtime.ensure_runtime(linked)
    destination = outside / "state.json"; protected = tmp_path / "protected"; protected.write_text("unchanged")
    (outside / "state.json.pending").symlink_to(protected)
    with pytest.raises(OSError): runtime.private_json(destination, {"changed": True})
    assert protected.read_text() == "unchanged"


def test_existing_port_is_preserved():
    with socket.socket() as owned:
        owned.bind(("127.0.0.1", 0)); owned.listen(); port = owned.getsockname()[1]
        with pytest.raises(RuntimeError, match="existing service"):
            runtime.require_ports([port])
        assert owned.fileno() >= 0


def test_reviewer_environment_discards_existing_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "existing-private-database")
    monkeypatch.setenv("KAIROS_MODEL_ENDPOINT", "https://outside-provider.invalid")
    monkeypatch.setenv("KAIROS_DEV_TOKEN", "private-existing-token")
    value = reviewer.environment(tmp_path)
    assert "DATABASE_URL" not in value
    assert "KAIROS_MODEL_ENDPOINT" not in value
    assert "KAIROS_DEV_TOKEN" not in value
    assert value["KAIROS_EVIDENCE_MODE"] == "recorded"


def test_failed_command_produces_receipt_and_failed_aggregate(tmp_path, monkeypatch):
    runtime.ensure_runtime(tmp_path)
    # Port ownership has its own real-socket test. This unit targets command failure
    # and must also work while a separate reviewer acceptance server is running.
    monkeypatch.setattr(reviewer, "require_ports", lambda _: None)
    def failing_checks(path, fullstack):
        reviewer.command(["false"], path, "intentional-failure")
    monkeypatch.setattr(reviewer, "run_checks", failing_checks)
    with pytest.raises(RuntimeError): reviewer.check(tmp_path, False)
    aggregate = json.loads((tmp_path / "acceptance.json").read_text())
    assert aggregate["passed"] is False
    assert aggregate["checks"][0]["returncode"] != 0
    assert aggregate["inference_calls"] == 0


def test_active_mode_conflict_preserves_owned_services(tmp_path, monkeypatch):
    owner = runtime.ensure_runtime(tmp_path)["owner"]
    runtime.private_json(tmp_path / "state.json", {"owner": owner, "mode": "demo", "supervisor": {"pid": 42, "identity": "known"}, "processes": []})
    monkeypatch.setattr(reviewer, "is_owned_process", lambda _: True)
    with pytest.raises(RuntimeError, match="Another reviewer mode"):
        reviewer.active_state(tmp_path, "fullstack")
    assert json.loads((tmp_path / "state.json").read_text())["supervisor"]["pid"] == 42
