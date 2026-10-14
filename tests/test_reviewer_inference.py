"""Opt-in inference lifecycle tests use no Docker, database, model or network."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import reviewer, reviewer_inference as inference


def test_preflight_is_read_only_and_binds_the_same_manifest(tmp_path, monkeypatch):
    checkout = tmp_path / "relocated checkout"
    cache = tmp_path / "external cache"
    cache.mkdir(); checkout.mkdir()
    manifest = checkout / "evidence/build004/inference-coder-mac.json"
    manifest.parent.mkdir(parents=True)
    profile = {"files": [{"path": "models/pinned.gguf", "sha256": "weight-digest"}]}
    manifest.write_text(json.dumps(profile))
    monkeypatch.setattr(inference, "ROOT", checkout)
    monkeypatch.setattr(inference.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(inference.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(inference, "require_ports", lambda ports: None)
    monkeypatch.setattr(inference.study007_runtime, "verify_model", lambda paths, name: profile)
    monkeypatch.setattr(inference, "storage_guard", lambda *_: {})
    import kairos_api.investigations.registry as registry
    observed = []
    class Cases:
        def __init__(self, manifest, runtime): observed.append((manifest, runtime))
        def get(self, identifier): return {"id": identifier, "split": "development"}
        def verify(self, case): observed.append(case["id"])
    monkeypatch.setattr(registry, "CaseRegistry", Cases)
    runtime = tmp_path / "private runtime"
    settings = inference.preflight(runtime, cache, session_seconds=600)
    assert not runtime.exists()
    assert settings.cache == cache
    assert settings.case_root == cache
    assert observed[-1] == "django__django-11066"
    assert settings.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    env = settings.environment()
    assert env["KAIROS_INVESTIGATION_MODEL_MANIFEST"] == str(manifest)
    assert env["KAIROS_INVESTIGATION_ROOT"] == str(cache)
    assert env["KAIROS_INVESTIGATION_MODEL_URL"] == "http://127.0.0.1:8130"


@pytest.mark.parametrize("seconds", [0, 59, 3601])
def test_invalid_duration_never_starts_services(tmp_path, seconds):
    with pytest.raises(ValueError, match="60 and 3600"):
        inference.preflight(tmp_path / "runtime", session_seconds=seconds)
    assert not (tmp_path / "runtime").exists()


def test_incompatible_platform_refuses_provider_substitution(tmp_path, monkeypatch):
    monkeypatch.setattr(inference.platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError, match="no provider substitution"):
        inference.preflight(tmp_path / "runtime")
    assert not (tmp_path / "runtime").exists()


def test_model_hash_failure_happens_before_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(reviewer, "active_state", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(reviewer, "require_ports", lambda *_: None)
    monkeypatch.setattr(inference, "preflight", lambda *_: (_ for _ in ()).throw(ValueError("Pinned runtime/model hash mismatch")))
    monkeypatch.setattr(reviewer, "ensure_docker", lambda: pytest.fail("Docker started before hash checks"))
    with pytest.raises(ValueError, match="hash mismatch"):
        reviewer.serve(tmp_path, "fullstack", with_inference=True)


def test_running_control_plane_cannot_silently_enable_inference(tmp_path, monkeypatch):
    owner = reviewer.ensure_runtime(tmp_path)["owner"]
    reviewer.private_json(tmp_path / "state.json", {"owner": owner, "mode": "fullstack",
        "supervisor": {"pid": 42, "identity": "owned"}, "processes": []})
    monkeypatch.setattr(reviewer, "is_owned_process", lambda _: True)
    with pytest.raises(RuntimeError, match="inference setting differs"):
        reviewer.active_state(tmp_path, "fullstack", True)


class Process:
    sequence = 40
    def __init__(self, argv=None, **kwargs):
        Process.sequence += 1
        self.pid = Process.sequence
        self.argv = argv
        self.env = kwargs.get("env")
        self.alive = True
        self.terminated = False
    def poll(self): return None if self.alive else 0
    def terminate(self): self.terminated = True; self.alive = False
    def wait(self, timeout=None): return 0
    def kill(self): self.alive = False


def session(tmp_path, monkeypatch, enabled=True, fail_attestation=False):
    events = []; processes = []; model = Process()
    log = SimpleNamespace(close=lambda: events.append("model-log-closed"))
    settings = SimpleNamespace(
        session_seconds=60,
        environment=lambda: {"KAIROS_INVESTIGATION_MODEL_MANIFEST": "pinned.json",
                             "KAIROS_INVESTIGATION_ROOT": "prepared cases",
                             "KAIROS_INVESTIGATION_MODEL_URL": "http://127.0.0.1:8130"},
        receipt=lambda: {"profile": "coder"})
    monkeypatch.setattr(reviewer, "active_state", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(reviewer, "require_ports", lambda *_: None)
    monkeypatch.setattr(inference, "preflight", lambda *_: settings if enabled else pytest.fail("Inference started implicitly"))
    monkeypatch.setattr(reviewer, "ensure_docker", lambda: events.append("docker"))
    monkeypatch.setattr(reviewer, "ensure_python", lambda *_: Path("python"))
    monkeypatch.setattr(inference, "verify_image", lambda *_: events.append("image"))
    monkeypatch.setattr(reviewer, "prepare_web", lambda *_: (tmp_path, {"DATABASE_URL": "isolated database"}))
    monkeypatch.setattr(reviewer, "ready", lambda *_: None)
    monkeypatch.setattr(reviewer, "process_record", lambda process: {"pid": process.pid, "identity": "owned"})
    monkeypatch.setattr(reviewer.signal, "signal", lambda *_: None)
    def spawn(argv, **kwargs):
        process = Process(argv, **kwargs); processes.append(process); return process
    monkeypatch.setattr(reviewer.subprocess, "Popen", spawn)
    monkeypatch.setattr(inference, "start", lambda _: (model, log))
    def finish(process, output):
        process.terminate(); output.close(); events.append("model-stopped")
    monkeypatch.setattr(inference, "finish", finish)
    monkeypatch.setattr(reviewer, "stop_runtime", lambda _: events.append("owned-containers-stopped"))
    calls = []
    def command(argv, *args, **kwargs):
        calls.append((argv, kwargs.get("env")))
        if "attest" in argv and fail_attestation: raise RuntimeError("Loaded model differs")
    monkeypatch.setattr(reviewer, "command", command)
    clock = iter([0, 61])
    monkeypatch.setattr(reviewer.time, "monotonic", lambda: next(clock))
    def idle(_): raise KeyboardInterrupt()
    monkeypatch.setattr(reviewer.time, "sleep", idle)
    return events, processes, model, calls


def test_opt_in_starts_real_modules_with_consistent_environment_and_stops(tmp_path, monkeypatch):
    events, processes, model, calls = session(tmp_path, monkeypatch)
    reviewer.serve(tmp_path, "fullstack", with_inference=True)
    assert any(p.argv[-1] == "kairos_api.investigations.worker" for p in processes)
    assert any("kairos_api.app:app" in p.argv for p in processes)
    for process in processes:
        assert process.env["KAIROS_INVESTIGATION_MODEL_MANIFEST"] == "pinned.json"
        assert process.env["KAIROS_INVESTIGATION_ROOT"] == "prepared cases"
        assert process.terminated
    assert any("attest" in argv and env["KAIROS_INVESTIGATION_MODEL_MANIFEST"] == "pinned.json" for argv, env in calls)
    assert model.terminated
    assert events[-1] == "owned-containers-stopped"
    assert json.loads((tmp_path / "services.json").read_text())["ready"] is False
    assert json.loads((tmp_path / "state.json").read_text())["processes"] == []


def test_attestation_failure_stops_model_api_and_owned_containers(tmp_path, monkeypatch):
    events, processes, model, calls = session(tmp_path, monkeypatch, fail_attestation=True)
    with pytest.raises(RuntimeError, match="Loaded model differs"):
        reviewer.serve(tmp_path, "fullstack", with_inference=True)
    assert model.terminated
    assert all(p.terminated for p in processes)
    assert not any(p.argv[-1] == "kairos_api.investigations.worker" for p in processes)
    assert events[-1] == "owned-containers-stopped"


def test_default_fullstack_never_starts_a_model_or_worker(tmp_path, monkeypatch):
    events, processes, model, calls = session(tmp_path, monkeypatch, enabled=False)
    reviewer.serve(tmp_path, "fullstack")
    assert model.alive
    assert not any(p.argv[-1] == "kairos_api.investigations.worker" for p in processes)
    assert not any("attest" in argv for argv, env in calls)
    assert "model-stopped" not in events


def test_demo_rejects_live_execution_before_startup(tmp_path):
    with pytest.raises(ValueError, match="only in fullstack"):
        reviewer.serve(tmp_path, "demo", with_inference=True)


def test_missing_image_does_not_pull_or_run_an_unreviewed_image(monkeypatch):
    calls = []
    monkeypatch.setattr(inference.subprocess, "run", lambda argv, **_: calls.append(argv) or SimpleNamespace(returncode=1, stdout=""))
    with pytest.raises(RuntimeError, match="reviewed case recipe"):
        inference.verify_image(SimpleNamespace(case={"image": "sha256:prepared"}))
    assert calls == [["docker", "image", "inspect", "sha256:prepared", "--format", "{{.Id}}"]]


def test_plain_python_opt_in_reexecutes_the_locked_environment_before_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(reviewer.sys, "argv", ["reviewer", "fullstack", "--with-inference", "--runtime", str(tmp_path)])
    monkeypatch.setattr(reviewer, "require_versions", lambda **_: None)
    interpreter = tmp_path / "venv/bin/python"
    monkeypatch.setattr(reviewer, "ensure_python", lambda _: interpreter)
    monkeypatch.setattr(reviewer, "ensure_docker", lambda: pytest.fail("Host interpreter started Docker"))
    monkeypatch.setenv("DATABASE_URL", "unrelated-private-database")
    calls = []
    monkeypatch.setattr(reviewer.subprocess, "call", lambda argv, **kwargs: calls.append((argv, kwargs)) or 0)
    assert reviewer.main() == 0
    argv, options = calls[0]
    assert argv[:3] == [str(interpreter), "-m", "scripts.reviewer"]
    assert "--with-inference" in argv
    assert argv[-2:] == ["--runtime", str(tmp_path)]
    assert "DATABASE_URL" not in options["env"]


def test_storage_counts_reviewer_files_and_disjoint_cases_once(tmp_path, monkeypatch):
    runtime = tmp_path / "reviewer"; cache = tmp_path / "cache"
    cases = tmp_path / "external cases"
    for root in (runtime, cache, cases): root.mkdir()
    (runtime / "private environment").write_bytes(b"a" * 5)
    (cache / "weight").write_bytes(b"b" * 7)
    (cases / "snapshot").write_bytes(b"c" * 11)
    monkeypatch.setattr(inference.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3))
    assert inference.storage_guard(runtime, cache, cases)["owned_bytes"] == 23
    nested = cache / "cases"; nested.mkdir(); (nested / "snapshot").write_bytes(b"d" * 3)
    assert inference.storage_guard(runtime, cache, nested)["owned_bytes"] == 15
    monkeypatch.setattr(inference.study007_runtime, "CAPACITY", 14)
    with pytest.raises(ValueError, match="6GiB"):
        inference.storage_guard(runtime, cache, nested)


def test_current_locked_venv_does_not_reexecute_recursively(tmp_path, monkeypatch):
    monkeypatch.setattr(reviewer.sys, "argv", ["reviewer", "fullstack", "--with-inference", "--runtime", str(tmp_path)])
    monkeypatch.setattr(reviewer.sys, "prefix", str(tmp_path / "venv"))
    monkeypatch.setattr(reviewer, "require_versions", lambda **_: None)
    monkeypatch.setattr(reviewer, "ensure_python", lambda _: tmp_path / "venv/bin/python")
    monkeypatch.setattr(reviewer.subprocess, "call", lambda *_args, **_kwargs: pytest.fail("Recursive interpreter reexecution"))
    calls = []
    monkeypatch.setattr(reviewer, "serve", lambda *args, **kwargs: calls.append(kwargs))
    assert reviewer.main() == 0
    assert calls[0]["with_inference"] is True


@pytest.mark.parametrize("change", ["profile", "model_cache", "case_root"])
def test_running_inference_rejects_changed_model_or_paths(tmp_path, monkeypatch, change):
    owner = reviewer.ensure_runtime(tmp_path)["owner"]
    cache = tmp_path / "cache"; cases = tmp_path / "cases"
    reviewer.private_json(tmp_path / "state.json", {"owner": owner, "mode": "fullstack",
        "inference_enabled": True, "supervisor": {"pid": 42, "identity": "owned"}, "processes": []})
    captured = {"profile": "coder", "model_cache": str(cache), "case_root": str(cases)}
    reviewer.private_json(tmp_path / "inference-config.json", captured)
    monkeypatch.setattr(reviewer, "is_owned_process", lambda _: True)
    requested = {"model_profile": "qwen3" if change == "profile" else "coder",
                 "model_cache": cache / "different" if change == "model_cache" else cache,
                 "case_root": cases / "different" if change == "case_root" else cases}
    with pytest.raises(RuntimeError, match="model profile or prepared paths differ"):
        reviewer.active_state(tmp_path, "fullstack", True, **requested)
    assert json.loads((tmp_path / "inference-config.json").read_text()) == captured


def test_matching_inference_reuses_original_session_deadline(tmp_path, monkeypatch, capsys):
    owner = reviewer.ensure_runtime(tmp_path)["owner"]
    cache = tmp_path / "cache"; cache.mkdir()
    reviewer.private_json(tmp_path / "state.json", {"owner": owner, "mode": "fullstack",
        "inference_enabled": True, "supervisor": {"pid": 42, "identity": "owned"}, "processes": []})
    reviewer.private_json(tmp_path / "inference-config.json", {
        "profile": "coder", "model_cache": str(cache), "case_root": str(cache), "session_seconds": 900})
    monkeypatch.setattr(reviewer, "is_owned_process", lambda _: True)
    assert reviewer.active_state(tmp_path, "fullstack", True, model_cache=cache / ".") is True
    assert "does not extend it" in capsys.readouterr().out
    assert json.loads((tmp_path / "inference-config.json").read_text())["session_seconds"] == 900


def test_model_receipt_failure_terminates_unreturned_child(tmp_path, monkeypatch):
    runtime = inference.study007_runtime
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(runtime, "verify_model", lambda *_: {"files": [{"path": "models/pinned.gguf"}]})
    monkeypatch.setattr(runtime, "storage_guard", lambda *_: {})
    class Client:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def get(self, _): raise runtime.httpx.ConnectError("Unused local port")
    monkeypatch.setattr(runtime.httpx, "Client", Client)
    process = Process()
    opened = []
    def spawn(*_args, **kwargs): opened.append(kwargs["stdout"]); return process
    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    monkeypatch.setattr(runtime, "save", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("Receipt write failed")))
    with pytest.raises(OSError, match="Receipt write failed"):
        runtime.start_model({"cache": tmp_path / "cache", "state": tmp_path / "state"}, "coder")
    assert process.terminated
    assert opened[0].closed


def test_model_spawn_failure_closes_open_log(tmp_path, monkeypatch):
    runtime = inference.study007_runtime
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(runtime, "verify_model", lambda *_: {"files": [{"path": "models/pinned.gguf"}]})
    monkeypatch.setattr(runtime, "storage_guard", lambda *_: {})
    class Client:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def get(self, _): raise runtime.httpx.ConnectError("Unused local port")
    monkeypatch.setattr(runtime.httpx, "Client", Client)
    opened = []
    def spawn(*_args, **kwargs):
        opened.append(kwargs["stdout"])
        raise OSError("Spawn failed")
    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    with pytest.raises(OSError, match="Spawn failed"):
        runtime.start_model({"cache": tmp_path / "cache", "state": tmp_path / "state"}, "coder")
    assert opened[0].closed


def test_initial_state_write_failure_stops_provisioned_containers(tmp_path, monkeypatch):
    events, processes, model, calls = session(tmp_path, monkeypatch)
    original = reviewer.private_json
    def write(path, value):
        if path.name == "state.json": raise OSError("Initial state write failed")
        original(path, value)
    monkeypatch.setattr(reviewer, "private_json", write)
    with pytest.raises(OSError, match="Initial state write failed"):
        reviewer.serve(tmp_path, "fullstack", with_inference=True)
    assert "docker" in events
    assert events[-1] == "owned-containers-stopped"
    assert not processes
    assert model.alive  # No model was started.


@pytest.mark.parametrize("receipt", ["state.json", "services.json"])
def test_final_receipt_write_failure_cannot_skip_teardown(tmp_path, monkeypatch, receipt):
    events, processes, model, calls = session(tmp_path, monkeypatch)
    original = reviewer.private_json
    def write(path, value):
        final = (path.name == "state.json" and value.get("supervisor", "missing") is None) or (
            path.name == "services.json" and value.get("ready", True) is False)
        if path.name == receipt and final: raise OSError("Final receipt write failed")
        original(path, value)
    monkeypatch.setattr(reviewer, "private_json", write)
    with pytest.raises(OSError, match="Final receipt write failed"):
        reviewer.serve(tmp_path, "fullstack", with_inference=True)
    assert model.terminated
    assert all(process.terminated for process in processes)
    assert "model-log-closed" in events
    assert events[-1] == "owned-containers-stopped"


def test_signal_restore_failure_cannot_skip_process_or_model_cleanup(tmp_path, monkeypatch):
    events, processes, model, calls = session(tmp_path, monkeypatch)
    signal_calls = []
    def handler(*args):
        signal_calls.append(args)
        if len(signal_calls) > 1: raise OSError("Signal restore failed")
    monkeypatch.setattr(reviewer.signal, "signal", handler)
    with pytest.raises(OSError, match="Signal restore failed"):
        reviewer.serve(tmp_path, "fullstack", with_inference=True)
    assert model.terminated
    assert all(process.terminated for process in processes)
    assert "model-log-closed" in events
    assert events[-1] == "owned-containers-stopped"


def test_corrupt_process_state_still_stops_independently_owned_containers(tmp_path, monkeypatch):
    from scripts import reviewer_runtime as runtime
    owner = runtime.ensure_runtime(tmp_path)["owner"]
    (tmp_path / "state.json").write_text("corrupt JSON")
    monkeypatch.setattr(runtime, "terminate_owned", lambda _: pytest.fail("Unverified process was signalled"))
    monkeypatch.setattr(runtime, "docker_inspect", lambda *_: {
        "Config": {"Labels": {runtime.LABEL: owner}}, "State": {"Running": True}})
    calls = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda argv, **_: calls.append(argv))
    with pytest.raises(RuntimeError, match="after independent owned-container cleanup"):
        runtime.stop(tmp_path)
    assert [argv[-1] for argv in calls] == [runtime.resource_names(tmp_path)[kind] for kind in ("keycloak", "postgres")]


def test_process_owner_mismatch_and_conflicting_label_preserve_each_unverified_resource(tmp_path, monkeypatch):
    from scripts import reviewer_runtime as runtime
    owner = runtime.ensure_runtime(tmp_path)["owner"]
    runtime.private_json(tmp_path / "state.json", {"owner": "another-owner", "supervisor": {"pid": 42}})
    monkeypatch.setattr(runtime, "terminate_owned", lambda _: pytest.fail("Unverified process was signalled"))
    names = runtime.resource_names(tmp_path)
    def inspect(_kind, name):
        label = "another-owner" if name == names["keycloak"] else owner
        return {"Config": {"Labels": {runtime.LABEL: label}}, "State": {"Running": True}}
    monkeypatch.setattr(runtime, "docker_inspect", inspect)
    calls = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda argv, **_: calls.append(argv))
    with pytest.raises(RuntimeError, match="another owner") as error:
        runtime.stop(tmp_path)
    assert "Process state owner mismatch" in str(error.value)
    assert [argv[-1] for argv in calls] == [names["postgres"]]


def test_process_stop_failure_does_not_skip_other_processes_or_containers(tmp_path, monkeypatch):
    from scripts import reviewer_runtime as runtime
    owner = runtime.ensure_runtime(tmp_path)["owner"]
    runtime.private_json(tmp_path / "state.json", {"owner": owner,
        "supervisor": {"pid": 42, "identity": "owned"},
        "processes": [{"pid": 43, "identity": "owned"}]})
    stopped = []
    def terminate(record):
        stopped.append(record["pid"])
        if record["pid"] == 42: raise OSError("Process stop failed")
        return True
    monkeypatch.setattr(runtime, "terminate_owned", terminate)
    monkeypatch.setattr(runtime, "docker_inspect", lambda *_: {
        "Config": {"Labels": {runtime.LABEL: owner}}, "State": {"Running": True}})
    calls = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda argv, **_: calls.append(argv))
    with pytest.raises(RuntimeError, match="Process stop failed"):
        runtime.stop(tmp_path)
    assert stopped == [42, 43]
    assert len(calls) == 2


@pytest.mark.parametrize("record", [{"pid": 0, "identity": None}, {"pid": -1, "identity": "owned"},
                                   {"pid": True, "identity": "owned"}, {"pid": 42, "identity": None},
                                   {"pid": 42, "identity": ""}, "corrupt"])
def test_invalid_process_identity_cannot_authorize_a_signal(monkeypatch, record):
    from scripts import reviewer_runtime as runtime
    monkeypatch.setattr(runtime, "process_identity", lambda _: pytest.fail("Invalid PID was inspected"))
    monkeypatch.setattr(runtime.os, "kill", lambda *_: pytest.fail("Unverified process was signalled"))
    assert runtime.terminate_owned(record) is False


def test_git_private_state_checks_every_file_in_a_real_checkout(tmp_path):
    import subprocess
    from scripts.verify_reviewer005 import private_files_ignored
    subprocess.run(['git','init','--quiet',str(tmp_path)],check=True,capture_output=True)
    subprocess.run(['git','config','core.excludesFile','/dev/null'],cwd=tmp_path,check=True,capture_output=True)
    private=tmp_path/'.runtime';private.mkdir()
    files=[private/'identity.local.json',private/'application.env']
    for file in files:file.write_text('synthetic test content')
    (tmp_path/'.gitignore').write_text('.runtime/\n')
    assert private_files_ignored(tmp_path,files)
    (tmp_path/'.gitignore').write_text('.runtime/identity.local.json\n')
    assert not private_files_ignored(tmp_path,files)
