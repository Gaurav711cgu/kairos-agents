"""Isolated Codex CLI transport with no Kairos redispatch in experiment010.

Internal provider retries remain CLI-controlled and unavailable; the no-retry
claim applies only to Kairos redispatch.

This adapter uses existing local ChatGPT CLI authentication. It neither reads nor
copies authentication files and never accepts API credentials. Each CLI dispatch
is separately captured; it is not a claim about internal provider request counts
or the historical local model's token limits. No native CLI tool is authorized.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
from uuid import uuid4

from scripts.repair010.codex_context010 import build_context010, normalize_action010

VERSION = "codex-cli-transport-experimental011-v1"
ALLOWED_MODEL_ID = "gpt-6.1-sol"
MAX_CAPTURE_BYTES = 1024 * 1024
MAX_DISPATCHES = 6
MAX_DISPATCH_SECONDS = 120.0
MAX_DIAGNOSTICS = 16
MAX_DIAGNOSTIC_BYTES = 4096
DISABLED_FEATURES = (
    "shell_tool", "apps", "multi_agent", "hooks", "memories", "remote_plugin",
    "skill_mcp_dependency_install", "shell_snapshot", "plugins", "skill_search",
    "browser_use", "computer_use", "view_image", "image_generation", "tool_suggest",
    "code_mode", "code_mode_host", "goals", "sleep_tool", "unbounded_connection_retries",
)
CONFIG = (
    'web_search="disabled"', "project_doc_max_bytes=0",
    'model_provider="openai"', 'forced_login_method="chatgpt"',
    "features.skip_host_skill_discovery=true", "skills.include_instructions=false",
    "skills.bundled.enabled=false", "cloud.skills.enabled=false",
    "orchestrator.mcp.enabled=false",
    'history.persistence="none"',
)


class CodexDispatchUnknown010(Exception):
    """A started or attempted CLI dispatch must not be automatically sent again."""


class CodexProfileError010(Exception):
    """The configured local CLI/authentication does not match the frozen profile."""


class _CaptureStop(Exception):
    pass


def _canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _immutable(path, raw):
    """Create a private, fsynced file, refusing existing or symbolic targets."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _private_directory(path):
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise ValueError("Private runtime directory is not a real directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def subprocess_environment010(environment=None):
    """Allow only operating-system configuration and the normal auth home.

    A whitelist excludes provider API keys, bearer tokens, endpoint overrides,
    injected profiles and inherited thread configuration, including credentials
    for providers unrelated to this experiment. CODEX_HOME is reused unchanged.
    """
    source = os.environ if environment is None else environment
    allowed = {"HOME", "PATH", "USER", "LOGNAME", "TMPDIR", "LANG", "TERM",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "CODEX_HOME", "SYSTEMROOT"}
    return {key: value for key, value in source.items()
            if key in allowed or key.startswith(("LC_", "CODEX_SANDBOX", "CODEX_APPROVAL",
                                                  "CODEX_SECURITY", "CODEX_ENFORCED", "CODEX_NETWORK"))}


def _strict_loads(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate JSON key")
            value[key] = item
        return value

    def constant(_):
        raise ValueError("Non-finite JSON value")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


class _Events:
    def __init__(self):
        self.buffer = b""
        self.turn_completed = False
        self.last_message = None
        self.usage = None
        self.types = []
        self.diagnostics = []
        self.diagnostics_omitted = 0

    def feed(self, raw, *, final=False):
        self.buffer += raw
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            self._line(line)
        if final and self.buffer:
            self._line(self.buffer)
            self.buffer = b""

    def _line(self, line):
        if not line.strip():
            return
        try:
            event = _strict_loads(line.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise _CaptureStop("invalid_jsonl_event") from None
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise _CaptureStop("invalid_jsonl_event")
        kind = event["type"]
        self.types.append(kind)
        if kind in {"item.started", "item.updated", "item.completed"}:
            item = event.get("item")
            if not isinstance(item, dict):
                raise _CaptureStop("invalid_cli_item")
            if item.get("type") == "error":
                # The CLI emits feature-availability warnings as error items,
                # before a turn starts. These grant no execution authority. A
                # terminal outer error or turn.failed remains a failed dispatch.
                message = item.get("message")
                if not isinstance(message, str):
                    raise _CaptureStop("invalid_cli_diagnostic")
                raw = message.encode("utf-8")
                if len(self.diagnostics) < MAX_DIAGNOSTICS:
                    self.diagnostics.append({"event_type": kind, "item_type": "error",
                        "message": message if len(raw) <= MAX_DIAGNOSTIC_BYTES else None,
                        "message_bytes": len(raw), "message_sha256": _sha(raw),
                        "message_omitted": len(raw) > MAX_DIAGNOSTIC_BYTES})
                else:
                    self.diagnostics_omitted += 1
            elif item.get("type") not in {"agent_message", "reasoning"}:
                raise _CaptureStop("native_tool_attempt")
            if kind == "item.completed" and item["type"] == "agent_message":
                if not isinstance(item.get("text"), str):
                    raise _CaptureStop("invalid_agent_message")
                self.last_message = item["text"]
        elif kind == "turn.completed":
            self.turn_completed = True
            usage = event.get("usage")
            if usage is not None:
                fields = {"input_tokens", "cached_input_tokens", "output_tokens"}
                if (not isinstance(usage, dict)
                        or any(type(value) is not int or value < 0
                               for key, value in usage.items() if key in fields)):
                    raise _CaptureStop("invalid_usage")
                self.usage = {key: usage[key] for key in fields if key in usage}
        elif kind in {"turn.failed", "error"}:
            raise _CaptureStop("cli_reported_failure")
        elif kind not in {"thread.started", "turn.started"}:
            raise _CaptureStop("unrecognized_cli_event")


class CodexInvestigator010:
    """Use one pinned, authenticated CLI as an external structured-action model."""

    def __init__(self, runtime, executable, expected_version, expected_sha256, model_id=None, max_dispatches=MAX_DISPATCHES):
        if model_id is not None and (type(model_id) is not str or model_id != ALLOWED_MODEL_ID):
            raise CodexProfileError010("Only the explicitly supported model gpt-6.1-sol may be selected")
        if type(max_dispatches) is not int or max_dispatches not in {1, 6, 10}:
            raise CodexProfileError010("A frozen CLI profile must allow exactly 1, 6 or 10 dispatches")
        self._max_dispatches = max_dispatches
        self._model_id = model_id
        self.runtime = Path(runtime).absolute()
        _private_directory(self.runtime)
        self.dispatches = self.runtime / "dispatches"
        self.contexts = self.runtime / "contexts"
        _private_directory(self.dispatches)
        _private_directory(self.contexts)
        self.executable = Path(executable).resolve(strict=True)
        if not self.executable.is_file():
            raise CodexProfileError010("Pinned CLI executable is not a regular file")
        self.expected_version = expected_version
        self.expected_sha256 = expected_sha256
        self._prepared = {}
        self._profile = None
        self.last_dispatch = None

    @property
    def model_id(self):
        """The requested model is immutable; it is not a resolved-model receipt."""
        return self._model_id

    @property
    def max_dispatches(self):
        """Frozen transport ceiling; each investigation may have a lower budget."""
        return self._max_dispatches

    def verify_profile(self):
        if _sha(self.executable.read_bytes()) != self.expected_sha256:
            raise CodexProfileError010("Pinned CLI executable hash changed")
        environment = subprocess_environment010()
        try:
            version = subprocess.run([str(self.executable), "--no-daemon", "--version"],
                                     capture_output=True, timeout=10, check=False,
                                     env=environment)
            status = subprocess.run([str(self.executable), "--no-daemon", "-c",
                                     'forced_login_method="chatgpt"', "login", "status"],
                                    capture_output=True, timeout=10, check=False,
                                    env=environment)
        except (OSError, subprocess.TimeoutExpired):
            raise CodexProfileError010("Local CLI preflight failed") from None
        if any(len(item.stdout) + len(item.stderr) > MAX_CAPTURE_BYTES for item in (version, status)):
            raise CodexProfileError010("Local CLI preflight output exceeds capture limit")
        try:
            observed = version.stdout.decode("utf-8").strip()
        except UnicodeError:
            raise CodexProfileError010("Local CLI version output is invalid") from None
        if version.returncode != 0 or observed != self.expected_version:
            raise CodexProfileError010("Pinned CLI version does not match")
        auth = (status.stdout + b"\n" + status.stderr).decode("utf-8", errors="replace").lower()
        chatgpt = "logged in using chatgpt" in auth or "logged in with chatgpt" in auth
        api_key = "api key" in auth or "api_key" in auth or "apikey" in auth
        if status.returncode != 0 or not chatgpt or api_key:
            raise CodexProfileError010("This experiment requires existing ChatGPT authentication")
        profile = {"provider": VERSION, "cli_version": observed,
                   "cli_sha256": self.expected_sha256, "uses_chatgpt_account": True,
                   "uses_api_key": False, "model_override": self.model_id,
                   "requested_model": self.model_id, "resolved_model": None,
                   "model_identity_note": ("CLI default model; model identity is unavailable from this preflight"
                       if self.model_id is None else
                       "Explicit CLI model request; execution has not independently confirmed resolved model identity"),
                   "internal_provider_retries": "CLI-controlled/unavailable",
                   "kairos_automatic_redispatch": False,
                   "max_cli_dispatches": self.max_dispatches,
                   "usage_scope": "Actual CLI token usage when supplied; CLI dispatch count is not internal provider request count"}
        if self._profile is not None and self._profile != profile:
            raise CodexProfileError010("CLI profile changed during the investigation")
        self._profile = profile
        return dict(profile)

    def prepare(self, case, configuration, observations, budgets):
        if budgets.get("calls_remaining", 0) > self.max_dispatches:
            raise CodexProfileError010("Investigation calls exceed the frozen CLI dispatch profile")
        request, context = build_context010(case, configuration, observations, budgets)
        context = {**context, "provider_identity": {"provider": VERSION,
            "requested_model": self.model_id, "resolved_model": None,
            "max_cli_dispatches": self.max_dispatches}}
        prompt_hash = _sha(request["prompt"].encode("utf-8"))
        context_path = self.contexts / (prompt_hash + ".json")
        raw = _canonical(context)
        if context_path.exists():
            if context_path.is_symlink() or context_path.read_bytes() != raw:
                raise ValueError("Captured context differs for the same public prompt")
        else:
            _immutable(context_path, raw)
        request = {**request, "cli_dispatch_id": uuid4().hex,
                   "provider": VERSION, "requested_model": self.model_id,
                   "resolved_model": None, "max_cli_dispatches": self.max_dispatches,
                   "prompt_sha256": prompt_hash,
                   "schema_sha256": _sha(_canonical(request["schema"]))}
        self._prepared[request["cli_dispatch_id"]] = (_sha(_canonical(request)), context)
        return request, {**context, "provider_profile": self._profile,
                         "native_tools_authorized": False,
                         "subscription_usage": "Uses the existing signed-in Codex plan; no API billing fallback"}

    def _argv(self, directory):
        argv = [str(self.executable), "--no-daemon", "exec", "--ignore-user-config", "--strict-config",
                "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                "--json", "--color", "never", "--output-schema", str(directory / "schema.json"),
                "--output-last-message", str(directory / "final.txt"),
                "-C", str(directory / "public-cwd")]
        if self.model_id is not None:
            argv.extend(["--model", self.model_id])
        for feature in DISABLED_FEATURES:
            argv.extend(["--disable", feature])
        for config in CONFIG:
            argv.extend(["-c", config])
        return argv + ["-"]

    def __call__(self, request, remaining_seconds):
        identifier = request.get("cli_dispatch_id") if isinstance(request, dict) else None
        if (isinstance(identifier, str) and len(identifier) == 32
                and (self.dispatches / identifier).exists()):
            raise CodexDispatchUnknown010("This dispatch already has an intent; it will not be resent")
        prepared = self._prepared.get(identifier)
        if (prepared is None or prepared[0] != _sha(_canonical(request))
                or not isinstance(identifier, str) or len(identifier) != 32):
            raise ValueError("CLI dispatch was not prepared or its captured request changed")
        if (type(remaining_seconds) not in {int, float}
                or not math.isfinite(remaining_seconds) or remaining_seconds <= 0):
            raise ValueError("CLI dispatch requires a positive remaining deadline")
        if self._profile is None:
            raise CodexProfileError010("CLI preflight must complete before any dispatch")
        # Recheck the binary immediately before every dispatch; no auth file is opened.
        if _sha(self.executable.read_bytes()) != self.expected_sha256:
            raise CodexProfileError010("Pinned CLI executable hash changed")
        if len(list(self.dispatches.iterdir())) >= self.max_dispatches:
            raise CodexDispatchUnknown010("CLI dispatch limit reached; no request was resent")
        directory = self.dispatches / identifier
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            raise CodexDispatchUnknown010("This dispatch already has an intent; it will not be resent") from None
        self.last_dispatch = directory
        _private_directory(directory / "public-cwd")
        timeout = min(MAX_DISPATCH_SECONDS, float(remaining_seconds))
        prompt = request["prompt"].encode("utf-8")
        _immutable(directory / "prompt.txt", prompt)
        _immutable(directory / "schema.json", _canonical(request["schema"]))
        _immutable(directory / "context.json", _canonical(prepared[1]))
        argv = self._argv(directory)
        intent = {"provider": VERSION, "dispatch_id": identifier, "created_at": _now(),
                  "request_sha256": prepared[0], "prompt_sha256": _sha(prompt),
                  "schema_sha256": request["schema_sha256"], "timeout_seconds": timeout,
                  "argv": argv, "profile": self._profile, "automatic_redispatch": False,
                  "native_tools_authorized": False,
                  "requested_model": self.model_id, "resolved_model": None,
                  "max_cli_dispatches": self.max_dispatches}
        _immutable(directory / "intent.json", _canonical(intent))
        self._prepared.pop(identifier)
        start = time.monotonic()
        events = _Events()
        process = None
        outcome, reason, returncode = "unknown_dispatch", None, None
        final, normalized, normalization_error = None, None, None
        final_truncation = None
        try:
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=subprocess_environment010(),
                                       start_new_session=True, cwd=str(directory / "public-cwd"))
            returncode = self._capture(process, directory, prompt, timeout, events)
            if returncode != 0:
                raise _CaptureStop("nonzero_cli_exit")
            if not events.turn_completed:
                raise _CaptureStop("completion_event_unavailable")
            final = self._read_final(directory / "final.txt")
            if not final:
                raise _CaptureStop("final_response_unavailable")
            try:
                final_text = final.decode("utf-8")
            except UnicodeError:
                raise _CaptureStop("invalid_final_encoding") from None
            if events.last_message is None or events.last_message.strip() != final_text.strip():
                raise _CaptureStop("final_response_event_mismatch")
            try:
                normalized = normalize_action010(_strict_loads(final_text), prepared[1])
            except (ValueError, TypeError, KeyError) as error:
                # Capture invalid output as a model result so the worker can report
                # invalid_response; it must not be mistaken for transport uncertainty.
                normalization_error = type(error).__name__ + ": " + str(error)[:300]
            outcome = "captured_model_response"
        except _CaptureStop as error:
            reason = str(error)
        except (OSError, subprocess.SubprocessError):
            reason = "cli_process_or_capture_failure"
        finally:
            if process is not None:
                try:
                    self._terminate(process)
                except (OSError, subprocess.SubprocessError):
                    outcome, reason = "unknown_dispatch", "owned_process_cleanup_failure"
                returncode = process.returncode
            final_path = directory / "final.txt"
            if final is None:
                try:
                    final_truncation = self._bound_final(final_path)
                    final = self._read_final(final_path)
                except (OSError, _CaptureStop):
                    pass
            receipt = {"provider": VERSION, "dispatch_id": identifier,
                       "outcome": outcome, "reason": reason, "returncode": returncode,
                       "elapsed_seconds": time.monotonic() - start, "finished_at": _now(),
                       "usage": events.usage, "usage_unavailable": events.usage is None,
                       "cli_event_types": events.types,
                       "cli_diagnostics": events.diagnostics,
                       "cli_diagnostics_omitted": events.diagnostics_omitted,
                       "normalization_error": normalization_error,
                       "normalized_action": normalized,
                       "capture_limit_bytes": MAX_CAPTURE_BYTES,
                       "final_output_truncation": final_truncation,
                       "capture_hashes": self._capture_hashes(directory),
                       "requested_model": self.model_id, "resolved_model": None,
                       "max_cli_dispatches": self.max_dispatches, "automatic_redispatch": False}
            _immutable(directory / "receipt.json", _canonical(receipt))
        if outcome != "captured_model_response":
            raise CodexDispatchUnknown010("CLI dispatch uncertainty: " + (reason or "capture_incomplete"))
        content = json.dumps(normalized, ensure_ascii=False) if normalized is not None else json.dumps(
            {"invalid_flat_action": normalization_error, "raw_response_sha256": _sha(final),
             "raw_response_bytes": len(final)}, ensure_ascii=False)
        response = {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                    "experiment010": {"provider": VERSION, "dispatch_id": identifier,
                                      "normalization_error": normalization_error,
                                      "requested_model": self.model_id, "resolved_model": None,
                                      "max_cli_dispatches": self.max_dispatches, "usage_scope": "CLI turn tokens"}}
        if events.usage is not None:
            mapping = {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens",
                       "cached_input_tokens": "cached_prompt_tokens"}
            response["usage"] = {mapping[key]: value for key, value in events.usage.items()}
            if "input_tokens" in events.usage and "output_tokens" in events.usage:
                response["usage"]["total_tokens"] = events.usage["input_tokens"] + events.usage["output_tokens"]
        _immutable(directory / "response.json", _canonical(response))
        return response

    @staticmethod
    def _read_final(path):
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return b""
        except OSError:
            raise _CaptureStop("final_response_not_regular") from None
        with os.fdopen(descriptor, "rb") as stream:
            details = os.fstat(stream.fileno())
            if not stat.S_ISREG(details.st_mode):
                raise _CaptureStop("final_response_not_regular")
            if details.st_size > MAX_CAPTURE_BYTES:
                raise _CaptureStop("final_response_exceeds_limit")
            raw = stream.read(MAX_CAPTURE_BYTES + 1)
            if len(raw) > MAX_CAPTURE_BYTES:
                raise _CaptureStop("final_response_exceeds_limit")
            os.fchmod(stream.fileno(), 0o600)
            return raw

    @staticmethod
    def _bound_final(path):
        try:
            descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "r+b") as stream:
            details = os.fstat(stream.fileno())
            if not stat.S_ISREG(details.st_mode):
                raise _CaptureStop("final_response_not_regular")
            if details.st_size <= MAX_CAPTURE_BYTES:
                return None
            stream.truncate(MAX_CAPTURE_BYTES)
            stream.flush()
            os.fsync(stream.fileno())
            return {"original_bytes": details.st_size, "retained_bytes": MAX_CAPTURE_BYTES,
                    "reason": "Final output exceeded its bound; prefix retained after owned process termination"}

    @staticmethod
    def _capture_hashes(directory):
        values = {}
        for name in ("stdout.jsonl", "stderr.txt", "final.txt"):
            path = directory / name
            try:
                if stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= MAX_CAPTURE_BYTES:
                    values[name] = _sha(path.read_bytes())
            except FileNotFoundError:
                continue
        return values

    @staticmethod
    def _terminate(process):
        """Signal only our owned group; reap its parent and remaining descendants."""
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # A parent may exit before its descendants. Reaping the parent alone does
        # not establish group shutdown, so kill any surviving owned group as well.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)

    def _capture(self, process, directory, prompt, timeout, events):
        deadline = time.monotonic() + timeout
        counts = {"stdout": 0, "stderr": 0}
        selector = selectors.DefaultSelector()
        sent = 0
        outputs = {}
        try:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
                path = directory / ("stdout.jsonl" if name == "stdout" else "stderr.txt")
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                outputs[name] = os.fdopen(descriptor, "wb")
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise _CaptureStop("dispatch_timeout")
                # Detect oversized or symbolic final output while the process runs.
                self._read_final(directory / "final.txt")
                for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                    stream, name = key.fileobj, key.data
                    if name == "stdin":
                        try:
                            written = os.write(stream.fileno(), prompt[sent:sent + 8192])
                            sent += written
                        except (BrokenPipeError, BlockingIOError):
                            if process.poll() is None:
                                continue
                            written = 0
                        if sent >= len(prompt) or (not written and process.poll() is not None):
                            selector.unregister(stream)
                            stream.close()
                        continue
                    try:
                        raw = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not raw:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    room = MAX_CAPTURE_BYTES - counts[name]
                    outputs[name].write(raw[:room])
                    counts[name] += len(raw)
                    if counts[name] > MAX_CAPTURE_BYTES:
                        raise _CaptureStop(name + "_exceeds_limit")
                    if name == "stdout":
                        events.feed(raw)
            events.feed(b"", final=True)
            left = deadline - time.monotonic()
            if left <= 0:
                raise _CaptureStop("dispatch_timeout")
            try:
                return process.wait(timeout=left)
            except subprocess.TimeoutExpired:
                raise _CaptureStop("dispatch_timeout") from None
        finally:
            selector.close()
            for output in outputs.values():
                output.flush()
                os.fsync(output.fileno())
                output.close()
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
