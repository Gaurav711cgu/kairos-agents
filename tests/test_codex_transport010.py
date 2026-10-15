"""Transport safety checks use mocked subprocesses; no inference or credentials."""
import hashlib
import json
import os
from pathlib import Path
import signal
from types import SimpleNamespace
import subprocess
import threading
from unittest.mock import Mock

import pytest
import scripts.repair010.codex_transport010 as transport


def flat(**overrides):
    return {"action": "final_result", "query": "", "path": "", "start_line": 1,
            "edits": [], "summary": "Insufficient evidence", **overrides}


def event_bytes(text, *, usage=None, tool=None):
    values = [{"type": "thread.started", "thread_id": "public-test"},
              {"type": "turn.started"}]
    if tool:
        values.append({"type": "item.started", "item": {"id": "one", "type": tool}})
    values.extend([{"type": "item.completed", "item": {"id": "reply", "type": "agent_message", "text": text}},
                   {"type": "turn.completed", **({"usage": usage} if usage is not None else {})}])
    return b"".join(json.dumps(value).encode() + b"\n" for value in values)


@pytest.fixture
def provider(tmp_path, monkeypatch):
    executable = tmp_path / "mock-codex"
    executable.write_bytes(b"pinned fake binary; never executed")
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    def local_preflight(argv, **kwargs):
        assert kwargs["env"].get("OPENAI_API_KEY") is None
        stdout = b"codex-cli 0.162.1\n" if argv[-1] == "--version" else b""
        stderr = b"Logged in using ChatGPT\n" if argv[-1] == "status" else b""
        return subprocess.CompletedProcess(argv, 0, stdout, stderr)
    monkeypatch.setattr(transport.subprocess, "run", local_preflight)
    context = {"allowed_actions": ["final_result", "search"],
               "selection": {"approved_source": "src"},
               "reference_bindings": {}, "source_catalog": []}
    monkeypatch.setattr(transport, "build_context010", lambda *a: (
        {"prompt": "Public issue and captured original source", "schema": {"type": "object"}}, context))
    value = transport.CodexInvestigator010(tmp_path / "runtime", executable,
                                         "codex-cli 0.162.1", digest)
    value.verify_profile()
    return value


def prepare(provider):
    return provider.prepare({}, "loop-v7", [], {"calls_remaining": 6})[0]


def mock_complete(provider, monkeypatch, *, final=None, events=None, code=0):
    text = json.dumps(flat()) if final is None else final
    stream = event_bytes(text, usage={"input_tokens": 42, "cached_input_tokens": 7, "output_tokens": 11}) if events is None else events
    process = SimpleNamespace(returncode=code, pid=987654)
    popen = Mock(return_value=process)
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    stopped = []
    monkeypatch.setattr(provider, "_terminate", lambda process: stopped.append(process.pid))
    def capture(process, directory, prompt, timeout, event_parser):
        assert (directory / "intent.json").is_file()
        assert (directory / "schema.json").is_file()
        assert (directory / "public-cwd").is_dir()
        assert list((directory / "public-cwd").iterdir()) == []
        (directory / "stdout.jsonl").write_bytes(stream)
        (directory / "stderr.txt").write_bytes(b"")
        (directory / "final.txt").write_text(text)
        event_parser.feed(stream, final=True)
        return code
    monkeypatch.setattr(provider, "_capture", capture)
    return popen, stopped


def receipt(provider):
    return json.loads((provider.last_dispatch / "receipt.json").read_text())


def test_success_has_private_intent_usage_and_tool_free_cli(provider, monkeypatch):
    request = prepare(provider)
    popen, stopped = mock_complete(provider, monkeypatch)
    response = provider(request, 500)
    assert json.loads(response["choices"][0]["message"]["content"]) == {"action": "final_result", "summary": "Insufficient evidence"}
    assert response["usage"] == {"prompt_tokens": 42, "completion_tokens": 11, "cached_prompt_tokens": 7, "total_tokens": 53}
    args, kwargs = popen.call_args
    argv = args[0]
    assert argv[:4] == [str(provider.executable), "--no-daemon", "exec", "--ignore-user-config"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--strict-config" in argv and "--ephemeral" in argv
    assert not any(value in argv for value in ("--model", "--ignore-rules", "--dangerously-bypass-approvals-and-sandbox"))
    for feature in transport.DISABLED_FEATURES:
        assert ["--disable", feature] == argv[argv.index(feature)-1:argv.index(feature)+1]
    assert 'forced_login_method="chatgpt"' in argv
    assert 'web_search="disabled"' in argv
    assert not any("model_providers.openai" in item for item in argv)
    assert kwargs["start_new_session"] is True
    assert kwargs["cwd"] == str(provider.last_dispatch / "public-cwd")
    assert stopped == [987654]
    captured = receipt(provider)
    assert captured["outcome"] == "captured_model_response"
    assert captured["usage"]["input_tokens"] == 42
    assert captured["automatic_redispatch"] is False
    assert captured["resolved_model"] is None
    assert (provider.last_dispatch / "response.json").exists()
    assert json.loads((provider.last_dispatch / "intent.json").read_text())["timeout_seconds"] == 120
    assert os.stat(provider.last_dispatch / "intent.json").st_mode & 0o777 == 0o600
    assert os.stat(provider.runtime).st_mode & 0o777 == 0o700


def test_environment_excludes_tokens_endpoints_threads_and_keeps_original_auth_home():
    original = {"HOME": "/private/home", "CODEX_HOME": "/private/auth", "PATH": "/bin",
                "OPENAI_API_KEY": "secret", "GOOGLE_API_KEY": "secret", "CUSTOM_API_TOKEN": "secret",
                "OPENAI_BASE_URL": "https://attacker.invalid", "CODEX_THREAD_ID": "parent",
                "CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "app", "CODEX_SANDBOX_NETWORK_DISABLED": "1",
                "LANG": "en_US.UTF-8", "LC_ALL": "C"}
    actual = transport.subprocess_environment010(original)
    assert actual == {key: original[key] for key in ("HOME", "CODEX_HOME", "PATH", "LANG", "LC_ALL", "CODEX_SANDBOX_NETWORK_DISABLED")}
    assert original["OPENAI_API_KEY"] == "secret"


@pytest.mark.parametrize("status,code", [(b"Logged in using an API key: secret", 0), (b"Not logged in", 1), (b"Logged in using ChatGPT; API key enabled", 0)])
def test_preflight_refuses_other_auth_without_recording_status(provider, monkeypatch, status, code):
    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0 if argv[-1] == "--version" else code,
            b"codex-cli 0.162.1" if argv[-1] == "--version" else b"", b"" if argv[-1] == "--version" else status)
    monkeypatch.setattr(transport.subprocess, "run", run)
    with pytest.raises(transport.CodexProfileError010, match="ChatGPT authentication"):
        provider.verify_profile()
    assert all(b"secret" not in path.read_bytes() for path in provider.runtime.rglob("*") if path.is_file())


def test_changed_binary_and_changed_version_refused_before_dispatch(provider, monkeypatch):
    request = prepare(provider)
    provider.executable.write_bytes(b"changed")
    popen = Mock()
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    with pytest.raises(transport.CodexProfileError010, match="hash changed"):
        provider(request, 2)
    popen.assert_not_called()
    assert list(provider.dispatches.iterdir()) == []


def test_changed_request_and_unprepared_request_do_not_execute(provider, monkeypatch):
    request = prepare(provider)
    popen = Mock()
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    with pytest.raises(ValueError, match="changed"):
        provider({**request, "prompt": "injected"}, 2)
    with pytest.raises(ValueError):
        provider({"cli_dispatch_id": "0" * 32}, 2)
    popen.assert_not_called()


def test_no_repeat_after_success(provider, monkeypatch):
    request = prepare(provider)
    popen, _ = mock_complete(provider, monkeypatch)
    provider(request, 1)
    with pytest.raises(transport.CodexDispatchUnknown010, match="not be resent"):
        provider(request, 1)
    assert popen.call_count == 1


def test_existing_intent_is_never_redispatched_after_new_prepare(provider, monkeypatch):
    request = prepare(provider)
    (provider.dispatches / request["cli_dispatch_id"]).mkdir()
    popen = Mock()
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    with pytest.raises(transport.CodexDispatchUnknown010, match="intent"):
        provider(request, 1)
    popen.assert_not_called()


def test_seventh_dispatch_refused_across_provider_runtime(provider, monkeypatch):
    for index in range(6):
        (provider.dispatches / str(index)).mkdir()
    popen = Mock()
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    with pytest.raises(transport.CodexDispatchUnknown010, match="limit"):
        provider(prepare(provider), 1)
    popen.assert_not_called()


@pytest.mark.parametrize("body", ["not json", json.dumps(flat(query="unused malicious value")), '{"action":"final_result","action":"search"}', '{"value":NaN}'])
def test_invalid_model_output_is_captured_and_not_executed(provider, monkeypatch, body):
    request = prepare(provider)
    mock_complete(provider, monkeypatch, final=body)
    result = provider(request, 1)
    invalid = json.loads(result["choices"][0]["message"]["content"])
    assert invalid["raw_response_sha256"] == hashlib.sha256(body.encode()).hexdigest() and "action" not in invalid
    assert result["experiment010"]["normalization_error"]
    assert receipt(provider)["outcome"] == "captured_model_response"
    assert (provider.last_dispatch / "final.txt").read_text() == body


@pytest.mark.parametrize("tool", ["command_execution", "file_change", "mcp_tool_call", "web_search", "image_generation", "unknown_future_tool"])
def test_any_native_tool_event_is_unknown_and_not_retried(provider, monkeypatch, tool):
    text = json.dumps(flat())
    request = prepare(provider)
    popen, stopped = mock_complete(provider, monkeypatch, final=text, events=event_bytes(text, tool=tool))
    with pytest.raises(transport.CodexDispatchUnknown010, match="native_tool_attempt"):
        provider(request, 1)
    assert popen.call_count == 1 and stopped == [987654]
    assert receipt(provider)["reason"] == "native_tool_attempt"
    assert not (provider.last_dispatch / "response.json").exists()


@pytest.mark.parametrize("stream,code,reason", [(b"not-json\n", 0, "invalid_jsonl_event"),
    (b'{"type":"turn.failed"}\n', 1, "cli_reported_failure"),
    (b'{"type":"thread.started"}\n', 0, "completion_event_unavailable"),
    (event_bytes(json.dumps(flat())), 2, "nonzero_cli_exit")])
def test_incomplete_or_failed_cli_is_unknown(provider, monkeypatch, stream, code, reason):
    mock_complete(provider, monkeypatch, events=stream, code=code)
    with pytest.raises(transport.CodexDispatchUnknown010, match=reason):
        provider(prepare(provider), 1)
    assert receipt(provider)["reason"] == reason


def test_final_response_must_match_captured_message(provider, monkeypatch):
    mock_complete(provider, monkeypatch, final=json.dumps(flat(summary="different")), events=event_bytes(json.dumps(flat())))
    with pytest.raises(transport.CodexDispatchUnknown010, match="mismatch"):
        provider(prepare(provider), 1)


def test_spawn_failure_preserves_intent_unknown_and_never_retries(provider, monkeypatch):
    popen = Mock(side_effect=OSError("no subprocess"))
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    request = prepare(provider)
    with pytest.raises(transport.CodexDispatchUnknown010):
        provider(request, 1)
    assert receipt(provider)["reason"] == "cli_process_or_capture_failure"
    assert (provider.last_dispatch / "intent.json").exists()
    with pytest.raises(transport.CodexDispatchUnknown010):
        provider(request, 1)
    assert popen.call_count == 1


def test_timeout_kills_owned_process_and_preserves_unknown(provider, monkeypatch):
    process = SimpleNamespace(returncode=None, pid=123456)
    monkeypatch.setattr(transport.subprocess, "Popen", Mock(return_value=process))
    def timeout(*args):
        raise transport._CaptureStop("dispatch_timeout")
    monkeypatch.setattr(provider, "_capture", timeout)
    stopped = []
    def stop(child):
        stopped.append(child.pid)
        child.returncode = -15
    monkeypatch.setattr(provider, "_terminate", stop)
    with pytest.raises(transport.CodexDispatchUnknown010, match="timeout"):
        provider(prepare(provider), 0.1)
    assert stopped == [123456]
    assert receipt(provider)["returncode"] == -15


def test_cleanup_failure_cannot_be_reported_success(provider, monkeypatch):
    mock_complete(provider, monkeypatch)
    def fail(_):
        raise subprocess.TimeoutExpired("owned-process", 2)
    monkeypatch.setattr(provider, "_terminate", fail)
    with pytest.raises(transport.CodexDispatchUnknown010, match="cleanup"):
        provider(prepare(provider), 1)
    assert receipt(provider)["reason"] == "owned_process_cleanup_failure"


def test_missing_usage_not_invented(provider, monkeypatch):
    text = json.dumps(flat())
    mock_complete(provider, monkeypatch, events=event_bytes(text))
    response = provider(prepare(provider), 1)
    assert "usage" not in response
    assert receipt(provider)["usage_unavailable"] is True


def test_partial_usage_not_invented(provider, monkeypatch):
    text = json.dumps(flat())
    mock_complete(provider, monkeypatch, events=event_bytes(text, usage={"input_tokens": 13}))
    response = provider(prepare(provider), 1)
    assert response["usage"] == {"prompt_tokens": 13}


def test_symlink_final_refused_and_target_untouched(tmp_path):
    target = tmp_path / "private"
    target.write_text("never read or change")
    link = tmp_path / "final"
    link.symlink_to(target)
    with pytest.raises(transport._CaptureStop, match="regular"):
        transport.CodexInvestigator010._read_final(link)
    assert target.read_text() == "never read or change"


def test_oversized_final_bound_and_omission_receipt(provider, monkeypatch):
    process = SimpleNamespace(returncode=0, pid=987654)
    monkeypatch.setattr(transport.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(provider, "_terminate", lambda _: None)
    def oversized(process, directory, prompt, timeout, events):
        (directory / "final.txt").write_bytes(b"x" * (transport.MAX_CAPTURE_BYTES + 11))
        provider._read_final(directory / "final.txt")
    monkeypatch.setattr(provider, "_capture", oversized)
    with pytest.raises(transport.CodexDispatchUnknown010, match="exceeds_limit"):
        provider(prepare(provider), 1)
    assert (provider.last_dispatch / "final.txt").stat().st_size == transport.MAX_CAPTURE_BYTES
    assert receipt(provider)["final_output_truncation"]["original_bytes"] == transport.MAX_CAPTURE_BYTES + 11


def test_terminate_only_own_process_group_escalates_and_reaps(monkeypatch):
    process = Mock(pid=123456)
    process.wait.side_effect = [subprocess.TimeoutExpired("owned", 2), -9]
    killpg = Mock()
    monkeypatch.setattr(transport.os, "killpg", killpg)
    transport.CodexInvestigator010._terminate(process)
    assert killpg.call_args_list[0].args == (123456, signal.SIGTERM)
    assert killpg.call_args_list[1].args == (123456, signal.SIGKILL)
    assert process.wait.call_count == 2


class PipeProcess:
    """Real pipes behind a mocked subprocess, to exercise streaming bounds."""
    def __init__(self, stdout, stderr=b""):
        stdin_read, stdin_write = os.pipe()
        self.stdin = os.fdopen(stdin_write, "wb", buffering=0)
        out_read, out_write = os.pipe()
        self.stdout = os.fdopen(out_read, "rb", buffering=0)
        err_read, err_write = os.pipe()
        self.stderr = os.fdopen(err_read, "rb", buffering=0)
        self.returncode = None
        self.pid = 987654
        self.threads = []
        def consume():
            try:
                while os.read(stdin_read, 8192):
                    pass
            except OSError:
                pass
            finally:
                os.close(stdin_read)
        def write(fd, data):
            try:
                while data:
                    count = os.write(fd, data[:8192])
                    data = data[count:]
            except (BrokenPipeError, OSError):
                pass
            finally:
                os.close(fd)
        for target, args in ((consume, ()), (write, (out_write, stdout)), (write, (err_write, stderr))):
            thread = threading.Thread(target=target, args=args, daemon=True)
            thread.start()
            self.threads.append(thread)
    def poll(self):
        return self.returncode
    def wait(self, timeout=None):
        self.returncode = 0
        return 0


@pytest.mark.parametrize("name", ["stdout", "stderr"])
def test_actual_streaming_capture_never_exceeds_limit(provider, tmp_path, name):
    raw = b" " * (transport.MAX_CAPTURE_BYTES + 300)
    process = PipeProcess(raw if name == "stdout" else b"", raw if name == "stderr" else b"")
    directory = tmp_path / "stream"
    directory.mkdir()
    with pytest.raises(transport._CaptureStop, match=name + "_exceeds_limit"):
        provider._capture(process, directory, b"public", 2, transport._Events())
    path = directory / ("stdout.jsonl" if name == "stdout" else "stderr.txt")
    assert path.stat().st_size == transport.MAX_CAPTURE_BYTES
    for thread in process.threads:
        thread.join(timeout=1)


def test_actual_streaming_capture_handles_complete_jsonl_and_prompt(provider, tmp_path):
    stream = event_bytes(json.dumps(flat()), usage={"input_tokens": 1, "output_tokens": 2})
    process = PipeProcess(stream, b"private diagnostic")
    directory = tmp_path / "stream-success"
    directory.mkdir()
    events = transport._Events()
    assert provider._capture(process, directory, b"x" * 64000, 2, events) == 0
    assert events.turn_completed and events.usage["output_tokens"] == 2
    assert (directory / "stdout.jsonl").read_bytes() == stream
    assert (directory / "stderr.txt").read_bytes() == b"private diagnostic"
    for thread in process.threads:
        thread.join(timeout=1)


def test_narrow_valid_action_cannot_bypass_failed_flat_normalization(provider, monkeypatch):
    from pydantic import ValidationError
    from kairos_api.investigations.contracts import ActionV7
    body = json.dumps({"action": "search", "query": "public_symbol"})
    assert ActionV7.validate_python(json.loads(body)).action == "search"
    mock_complete(provider, monkeypatch, final=body)
    response = provider(prepare(provider), 1)
    value = json.loads(response["choices"][0]["message"]["content"])
    with pytest.raises(ValidationError):
        ActionV7.validate_python(value)
    assert value["raw_response_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert (provider.last_dispatch / "final.txt").read_text() == body


def test_reaped_parent_does_not_leave_its_owned_descendants(monkeypatch):
    process = Mock(pid=123456)
    process.wait.return_value = 0
    killpg = Mock()
    monkeypatch.setattr(transport.os, "killpg", killpg)
    transport.CodexInvestigator010._terminate(process)
    assert killpg.call_args_list[-1].args == (123456, signal.SIGKILL)


def test_startup_diagnostic_items_do_not_authorize_tools_or_fail_completed_turn(provider, monkeypatch):
    text = json.dumps(flat())
    warnings = ["Under-development features enabled: skip_host_skill_discovery.",
                "Code Mode is unavailable because code-mode host is disabled."]
    startup = b"".join(json.dumps({"type": "item.completed", "item": {
        "id": str(index), "type": "error", "message": message}}).encode() + b"\n"
        for index, message in enumerate(warnings))
    mock_complete(provider, monkeypatch, events=startup + event_bytes(text))
    response = provider(prepare(provider), 1)
    assert json.loads(response["choices"][0]["message"]["content"])["action"] == "final_result"
    captured = receipt(provider)
    assert captured["outcome"] == "captured_model_response"
    assert [item["message"] for item in captured["cli_diagnostics"]] == warnings
    assert captured["cli_diagnostics_omitted"] == 0


def test_diagnostics_are_bounded_with_exact_hash_and_raw_stdout_retained(provider, monkeypatch):
    text = json.dumps(flat())
    message = "large warning " * 1000
    warning = json.dumps({"type": "item.completed", "item": {
        "type": "error", "message": message}}).encode() + b"\n"
    stream = warning * (transport.MAX_DIAGNOSTICS + 3) + event_bytes(text)
    mock_complete(provider, monkeypatch, events=stream)
    provider(prepare(provider), 1)
    captured = receipt(provider)
    assert len(captured["cli_diagnostics"]) == transport.MAX_DIAGNOSTICS
    assert captured["cli_diagnostics_omitted"] == 3
    diagnostic = captured["cli_diagnostics"][0]
    assert diagnostic["message"] is None and diagnostic["message_omitted"] is True
    assert diagnostic["message_sha256"] == hashlib.sha256(message.encode()).hexdigest()
    assert diagnostic["message_bytes"] == len(message.encode())
    assert (provider.last_dispatch / "stdout.jsonl").read_bytes() == stream


@pytest.mark.parametrize("outer", ["error", "turn.failed"])
def test_outer_errors_still_fail_even_after_diagnostic_warning(provider, monkeypatch, outer):
    startup = json.dumps({"type": "item.completed", "item": {
        "type": "error", "message": "nonfatal startup warning"}}).encode() + b"\n"
    stream = startup + json.dumps({"type": outer, "message": "terminal failure"}).encode() + b"\n"
    mock_complete(provider, monkeypatch, events=stream)
    with pytest.raises(transport.CodexDispatchUnknown010, match="cli_reported_failure"):
        provider(prepare(provider), 1)
    assert len(receipt(provider)["cli_diagnostics"]) == 1


def test_error_item_requires_a_message_and_cannot_hide_tool_item(provider, monkeypatch):
    stream = b'{"type":"item.completed","item":{"type":"error"}}\n'
    mock_complete(provider, monkeypatch, events=stream)
    with pytest.raises(transport.CodexDispatchUnknown010, match="invalid_cli_diagnostic"):
        provider(prepare(provider), 1)


def test_diagnostic_does_not_exempt_a_later_tool_attempt(provider, monkeypatch):
    startup = b'{"type":"item.completed","item":{"type":"error","message":"warning"}}\n'
    stream = startup + event_bytes(json.dumps(flat()), tool="command_execution")
    mock_complete(provider, monkeypatch, events=stream)
    with pytest.raises(transport.CodexDispatchUnknown010, match="native_tool_attempt"):
        provider(prepare(provider), 1)
    assert receipt(provider)["cli_diagnostics"][0]["message"] == "warning"


def test_explicit_supported_model_is_requested_without_inventing_resolved_identity(provider, monkeypatch):
    selected = transport.CodexInvestigator010(provider.runtime / "explicit", provider.executable,
        provider.expected_version, provider.expected_sha256, model_id="gpt-6.1-sol")
    profile = selected.verify_profile()
    assert profile["requested_model"] == "gpt-6.1-sol"
    assert profile["model_override"] == "gpt-6.1-sol"
    assert profile["resolved_model"] is None and profile["uses_api_key"] is False
    request, context = selected.prepare({}, "loop-v7", [], {"calls_remaining": 6})
    assert request["requested_model"] == "gpt-6.1-sol" and request["resolved_model"] is None
    assert context["provider_identity"]["requested_model"] == "gpt-6.1-sol"
    assert context["provider_profile"]["resolved_model"] is None
    popen, _ = mock_complete(selected, monkeypatch)
    response = selected(request, 1)
    argv = popen.call_args.args[0]
    assert argv[argv.index("--model") + 1] == "gpt-6.1-sol"
    assert argv.count("--model") == 1 and 'forced_login_method="chatgpt"' in argv
    assert response["experiment010"]["requested_model"] == "gpt-6.1-sol"
    assert response["experiment010"]["resolved_model"] is None
    assert receipt(selected)["requested_model"] == "gpt-6.1-sol"
    intent = json.loads((selected.last_dispatch / "intent.json").read_text())
    assert intent["requested_model"] == "gpt-6.1-sol" and intent["resolved_model"] is None
    captured_context = json.loads((selected.last_dispatch / "context.json").read_text())
    assert captured_context["provider_identity"]["requested_model"] == "gpt-6.1-sol"


@pytest.mark.parametrize("model_id", ["", "gpt-6.1-sol ", "--dangerously-bypass-approvals-and-sandbox",
    "gpt-6.1-sol --model other", "/private/model", "../model", "other", ["gpt-6.1-sol"], True])
def test_model_argument_injection_and_unsupported_identity_refused_before_side_effects(provider, tmp_path, monkeypatch, model_id):
    runtime = tmp_path / "invalid-model"
    popen = Mock()
    run = Mock()
    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    monkeypatch.setattr(transport.subprocess, "run", run)
    with pytest.raises(transport.CodexProfileError010, match="explicitly supported model"):
        transport.CodexInvestigator010(runtime, provider.executable,
            provider.expected_version, provider.expected_sha256, model_id=model_id)
    assert not runtime.exists()
    popen.assert_not_called()
    run.assert_not_called()


def test_default_model_stays_unspecified_and_identity_remains_unavailable(provider):
    profile = provider.verify_profile()
    request, context = provider.prepare({}, "loop-v7", [], {"calls_remaining": 6})
    assert profile["requested_model"] is None and profile["resolved_model"] is None
    assert profile["model_override"] is None
    assert request["requested_model"] is None and request["resolved_model"] is None
    assert context["provider_identity"]["requested_model"] is None
    assert "--model" not in provider._argv(provider.runtime)


def test_requested_model_property_is_read_only(provider):
    with pytest.raises(AttributeError):
        provider.model_id = "other-model"


@pytest.mark.parametrize("max_dispatches", [0, 2, 7, 11, 100, True, "10", None])
def test_invalid_dispatch_profile_refused_before_runtime_write(provider, tmp_path, max_dispatches):
    destination=tmp_path/"invalid-ceiling"
    with pytest.raises(transport.CodexProfileError010,match="exactly 1, 6 or 10"):
        transport.CodexInvestigator010(destination,provider.executable,
            provider.expected_version,provider.expected_sha256,max_dispatches=max_dispatches)
    assert not destination.exists()


def test_explicit_ten_dispatch_profile_is_frozen_and_default_six_is_unchanged(provider,monkeypatch):
    assert provider.max_dispatches==6
    selected=transport.CodexInvestigator010(provider.runtime/"long-profile",provider.executable,
        provider.expected_version,provider.expected_sha256,model_id="gpt-6.1-sol",max_dispatches=10)
    profile=selected.verify_profile()
    assert profile["max_cli_dispatches"]==10
    request,context=selected.prepare({},"loop-v8",[],{"calls_remaining":10})
    assert request["max_cli_dispatches"]==10
    assert context["provider_identity"]["max_cli_dispatches"]==10
    popen,_=mock_complete(selected,monkeypatch)
    selected(request,1)
    for _ in range(9):selected(prepare(selected),1)
    assert popen.call_count==10
    assert receipt(selected)["max_cli_dispatches"]==10
    assert json.loads((selected.last_dispatch/"intent.json").read_text())["max_cli_dispatches"]==10
    with pytest.raises(transport.CodexDispatchUnknown010,match="limit"):
        selected(prepare(selected),1)
    assert popen.call_count==10
    with pytest.raises(AttributeError):selected.max_dispatches=6


def test_v8_calls_cannot_silently_exceed_default_transport_profile(provider):
    before=list(provider.runtime.rglob("*"))
    with pytest.raises(transport.CodexProfileError010,match="frozen CLI dispatch profile"):
        provider.prepare({},"loop-v8",[],{"calls_remaining":10})
    assert list(provider.runtime.rglob("*"))==before


def test_baseline_transport_refuses_second_dispatch(provider, monkeypatch):
    selected=transport.CodexInvestigator010(provider.runtime/"baseline-profile",provider.executable,
        provider.expected_version,provider.expected_sha256,model_id="gpt-6.1-sol",max_dispatches=1)
    selected.verify_profile()
    request,_=selected.prepare({},"baseline-v8",[],{"calls_remaining":1})
    popen,_=mock_complete(selected,monkeypatch)
    selected(request,1)
    second,_=selected.prepare({},"baseline-v8",[],{"calls_remaining":1})
    with pytest.raises(transport.CodexDispatchUnknown010,match="limit"):
        selected(second,1)
    assert popen.call_count==1
    assert receipt(selected)["max_cli_dispatches"]==1
