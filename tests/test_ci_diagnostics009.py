"""Hosted diagnostics must reveal failures without exporting generated credentials."""
import json

import pytest

from scripts.ci_diagnostics009 import redact, summarize


def test_failure_tail_redacts_runtime_credentials_and_tokens(tmp_path):
    runtime = tmp_path / ".runtime/ci"
    checks = runtime / "checks"
    checks.mkdir(parents=True)
    secret = "isolated-fixture-client-secret-009"
    (runtime / "application.env").write_text("KAIROS_OIDC_CLIENT_SECRET=" + secret + "\n")
    (checks / "backend.receipt.json").write_text(json.dumps({"name": "backend", "returncode": 1}))
    (checks / "backend.log").write_text("\n".join(["old output"] * 150) + "\nAssertionError: " + secret + "\n")
    result = summarize(runtime, tmp_path)
    assert result["failed_checks"][0]["name"] == "backend"
    assert "AssertionError: [redacted]" in result["logs"][0]["tail"]
    assert len(result["logs"][0]["tail"].splitlines()) == 120
    assert secret not in json.dumps(result)
    token = "eyJhbGciOiJIUzI1NiJ9.payload.signature"
    text = redact("postgresql://user:pass@host/db " + token + " ?code=private-code&state=x Authorization: Bearer private-token", set())
    for value in ("user:pass", token, "private-code", "private-token"):
        assert value not in text


def test_diagnostics_reject_external_runtime_and_ignore_log_symlinks(tmp_path):
    runtime = tmp_path / ".runtime/ci"
    runtime.mkdir(parents=True)
    outside = tmp_path / "private.txt"
    outside.write_text("must not export")
    (runtime / "error.log").symlink_to(outside)
    assert summarize(runtime, tmp_path)["logs"] == []
    with pytest.raises(ValueError, match="isolated"):
        summarize(tmp_path / "external", tmp_path)
