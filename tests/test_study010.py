"""Offline command tests. No PostgreSQL, Docker or inference execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import scripts.study010 as study010


def args(tmp_path, **values):
    return argparse.Namespace(checkout=tmp_path, manifest=None, case_root=None,
                              task_id=None, runtime=None, codex=None, **values)


def test_cli_identity_only_runs_version_and_login_status_and_never_auth_files(tmp_path):
    binary = tmp_path / "codex"; binary.write_bytes(b"pinned binary")
    calls = []
    def command(argv, **settings):
        calls.append(argv)
        output = b"codex-cli 0.162.1\n" if argv[-1] == "--version" else b"Logged in using ChatGPT\n"
        return subprocess.CompletedProcess(argv, 0, output, b"")
    helpers = (object, lambda: {"HOME": "existing home"}, object, object, "reviewed-unresolved-python-v1")
    with patch.object(study010, "_helpers", return_value=helpers), \
            patch.object(study010, "_command", side_effect=command), \
            patch.object(study010.shutil, "which", return_value=str(binary)):
        path, identity = study010.cli_identity010()
    assert path == binary
    assert identity["cli_sha256"] == hashlib.sha256(b"pinned binary").hexdigest()
    assert identity["uses_chatgpt_account"] and not identity["uses_api_key"]
    assert identity["requested_model"] == "gpt-6.1-sol"
    assert identity["resolved_model"] is None
    assert len(calls) == 2
    assert calls[0][-1] == "--version" and calls[1][-2:] == ["login", "status"]
    assert all("exec" not in call for call in calls)


@pytest.mark.parametrize("message,code", [(b"Logged in using API key", 0),
                                          (b"Not logged in", 0),
                                          (b"Logged in using ChatGPT", 1)])
def test_api_login_and_failed_status_refused(tmp_path, message, code):
    binary = tmp_path / "codex"; binary.write_bytes(b"binary")
    results = [subprocess.CompletedProcess([], 0, b"codex-cli 0.162.1", b""),
               subprocess.CompletedProcess([], code, message, b"")]
    with patch.object(study010, "_helpers", return_value=(object, lambda: {}, object, object, "kind")), \
            patch.object(study010, "_command", side_effect=results):
        with pytest.raises(ValueError, match="ChatGPT CLI login"):
            study010.cli_identity010(binary)


def test_doctor_is_read_only_and_starts_no_runtime(tmp_path):
    options = args(tmp_path)
    before = list(tmp_path.iterdir())
    with patch.object(study010, "cli_identity010", return_value=(Path("/bin/codex"), {"cli_version": "pinned"})), \
            patch.object(study010, "registered_task010", return_value=(None, None)), \
            patch.object(study010.shutil, "disk_usage", return_value=SimpleNamespace(free=8*1024**3)), \
            patch.object(study010.shutil, "which", return_value=None), \
            patch.object(study010.subprocess, "run", side_effect=AssertionError("No subprocess allowed here")):
        result = study010.doctor010(options)
    assert result["passed"]
    assert result["inference_started"] is result["docker_started"] is result["database_started"] is False
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize("manifest,case_root,task", [(Path("manifest"), None, None),
                                                    (None, Path("root"), None),
                                                    (None, None, "task")])
def test_registration_requires_consistent_explicit_paths(manifest, case_root, task):
    with pytest.raises(ValueError):
        study010.registered_task010(manifest, case_root, task)


def test_historical_case_rejected_before_reference_based_registry_get(tmp_path):
    class Registry:
        def __init__(self, manifest, root): pass
        def manifest(self):
            return {"cases": [{"id": "old", "split": "development", "qualified": True}]}
        def get(self, identifier):
            raise AssertionError("Historical reference lookup must not occur")
    with patch.object(study010, "_helpers", return_value=(object, object, object, Registry, "reviewed-unresolved-python-v1")):
        with pytest.raises(ValueError, match="historical and held-out"):
            study010.registered_task010(tmp_path / "manifest", tmp_path, "old")


def test_unresolved_task_validation_uses_own_registry(tmp_path):
    task = {"id": "new-task", "task_kind": "reviewed-unresolved-python-v1", "split": "unresolved"}
    class Registry:
        def __init__(self, manifest, root): self.paths = manifest, root
        def manifest(self): return {"cases": [task]}
        def get(self, identifier): assert identifier == "new-task"; return task
    with patch.object(study010, "_helpers", return_value=(object, object, object, Registry, "reviewed-unresolved-python-v1")):
        registry, actual = study010.registered_task010(tmp_path / "manifest", tmp_path, "new-task")
    assert actual == task and registry.paths == (tmp_path / "manifest", tmp_path)


def test_report_validates_saved_hashes_without_services(tmp_path):
    artifact = tmp_path / "record.json"; artifact.write_text('{"outcome":"failed_checks"}')
    result = {"version": study010.VERSION, "task_id": "new-task", "status": "completed",
              "outcome": "failed_checks", "cli_dispatches": 2, "patches": 1, "checks": 1,
              "scope": "One reviewed task", "evidence_hashes": {"record.json": study010._sha(artifact)}}
    study010._immutable(tmp_path / "result.json", result)
    with patch.object(study010.subprocess, "run", side_effect=AssertionError("No services")):
        report = study010.report010(tmp_path)
    assert report["evidence_verified"] and not report["verified"]
    assert report["cli_dispatches"] == 2
    artifact.write_text("corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        study010.report010(tmp_path)


@pytest.mark.parametrize("name", ["../outside", "/outside", "folder/../outside", "folder\\outside"])
def test_report_rejects_malicious_evidence_paths(tmp_path, name):
    study010._immutable(tmp_path / "result.json", {"version": study010.VERSION,
                                                  "evidence_hashes": {name: "a" * 64}})
    with pytest.raises(ValueError, match="escapes"):
        study010.report010(tmp_path)


def test_existing_runtime_never_redispatched(tmp_path):
    options = args(tmp_path)
    options.runtime = tmp_path / "owned"; options.runtime.mkdir()
    task = {"id": "new-task"}
    case_root = tmp_path / "registered"; case_directory = case_root / "cases/new-task"
    case_directory.mkdir(parents=True)
    registry = SimpleNamespace(runtime=case_root, directory=lambda _: case_directory)
    with patch.object(study010, "registered_task010", return_value=(registry, task)), \
            patch.object(study010, "cli_identity010", return_value=(Path("/codex"), {})), \
            patch.object(study010.subprocess, "run", side_effect=AssertionError("No dispatch or service")):
        result = study010.run010(options)
    assert result["status"] == "incomplete" and result["automatic_redispatch"] is False


def test_unknown_dispatch_is_not_reported_as_verified(tmp_path):
    study010._immutable(tmp_path / "result.json", {
        "version": study010.VERSION, "task_id": "new-task", "status": "unknown",
        "outcome": "unknown_dispatch", "cli_dispatches": 1, "patches": 0, "checks": 0,
        "scope": "Uncertain provider dispatch preserved", "evidence_hashes": {}})
    result = study010.report010(tmp_path)
    assert not result["verified"] and not result["automatic_redispatch"]


def test_duplicate_and_oversized_receipt_refused(tmp_path):
    receipt = tmp_path / "result.json"; receipt.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError, match="Duplicate"):
        study010._load(receipt)
    with patch.object(study010, "MAX_JSON_BYTES", 4):
        with pytest.raises(ValueError, match="bounded"):
            study010._load(receipt)


def test_options_work_before_or_after_subcommand():
    parser = study010.parser010()
    for argv in (["--task-id", "new-task", "--manifest", "manifest.json", "validate-task", "--case-root", "cases"],
                 ["validate-task", "--task-id", "new-task", "--manifest", "manifest.json", "--case-root", "cases"]):
        parsed = parser.parse_args(argv)
        assert parsed.task_id == "new-task" and parsed.manifest == Path("manifest.json")
        assert parsed.case_root == Path("cases")


def test_main_failure_is_explicit_machine_readable(capsys):
    assert study010.main(["report"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["operation"] == "report" and not output["passed"]


def test_setup_failure_preserves_receipt_and_restores_manifest_environment(tmp_path, monkeypatch):
    source = tmp_path / "registered/source/package"; source.mkdir(parents=True)
    (source / "logic.py").write_text("def value():\n    return 1\n")
    class Registry:
        runtime = tmp_path / "registered"
        def directory(self, case): return tmp_path / "registered"
        def fingerprint(self, case): return "a" * 64
    options = args(tmp_path)
    options.runtime = tmp_path / "new private runtime"
    monkeypatch.setenv("KAIROS_INVESTIGATION_MODEL_MANIFEST", "preserve existing manifest")
    def fail_setup(argv, **settings):
        assert "initdb" in argv[0]
        raise subprocess.CalledProcessError(1, argv)
    with patch.object(study010, "registered_task010", return_value=(Registry(), {"id": "new-task"})), \
            patch.object(study010, "cli_identity010", return_value=(Path("/codex"), {"cli_version": "pinned", "cli_sha256": "b" * 64})), \
            patch.object(study010, "_helpers", return_value=(object, object, object, object, "kind")), \
            patch.object(study010, "_source_identity", return_value={"logical.py": "c" * 64}), \
            patch("scripts.study007_runtime.storage_guard", return_value={}), \
            patch.object(study010.shutil, "which", side_effect=lambda name: "/fake/" + name), \
            patch.object(study010.subprocess, "run", side_effect=fail_setup):
        result = study010.run010(options)
    assert result["outcome"] == "environment_failure" and not result["verified"]
    assert result["cli_dispatches"] == 0 and result["evidence_verified"]
    assert result["failure"]["type"] == "CalledProcessError"
    assert study010.os.environ["KAIROS_INVESTIGATION_MODEL_MANIFEST"] == "preserve existing manifest"
    assert (options.runtime / "result.json").stat().st_mode & 0o777 == 0o600
    assert options.runtime.stat().st_mode & 0o777 == 0o700


def test_main_reports_unknown_or_incomplete_as_failure(capsys):
    for status in ("unknown", "incomplete", "failed"):
        with patch.object(study010, "report010", return_value={"status": status}):
            assert study010.main(["report", "--runtime", "existing"]) == 1
        capsys.readouterr()


def test_future_profile_requests_one_explicit_model_without_relabelling_captures():
    assert study010.REQUESTED_MODEL == "gpt-6.1-sol"
    assert study010.GENERATION["requested_model"] == "gpt-6.1-sol"
    assert "CLI default" not in study010.GENERATION["model_selection"]
    assert study010.GENERATION["output_tokens_limit"] is None


@pytest.mark.parametrize("placement", ["case", "source", "verifier-child", "case-parent", "registry-parent"])
def test_runtime_overlap_rejected_before_any_write(tmp_path, placement):
    root = tmp_path / "registered"; directory = root / "cases/new-task"
    source = directory / "source"; source.mkdir(parents=True)
    registry = SimpleNamespace(runtime=root, directory=lambda _: directory)
    options = args(tmp_path)
    options.runtime = {"case": directory, "source": source / "owned",
                       "verifier-child": directory / "private-state",
                       "case-parent": directory.parent,
                       "registry-parent": tmp_path}[placement]
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    with patch.object(study010, "registered_task010", return_value=(registry, {"id": "new-task"})), \
            patch.object(study010, "cli_identity010", side_effect=AssertionError("No CLI preflight")):
        with pytest.raises(ValueError, match="overlaps"):
            study010.run010(options)
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before


def test_runtime_link_rejected_before_resolution(tmp_path):
    root = tmp_path / "registered"; directory = root / "cases/new-task"
    directory.mkdir(parents=True)
    link = tmp_path / "alias"; link.symlink_to(directory, target_is_directory=True)
    registry = SimpleNamespace(runtime=root, directory=lambda _: directory)
    with pytest.raises(ValueError, match="symlinks"):
        study010.checked_runtime010(link / "owned", registry, {"id": "new-task"})


@pytest.mark.parametrize("source", ["experiment", "result"])
def test_existing_runtime_task_conflict_refused_without_redispatch(tmp_path, source):
    runtime = tmp_path / "owned"; runtime.mkdir()
    if source == "experiment":
        study010._immutable(runtime / "experiment.json", {"task_id": "other-task"})
    else:
        study010._immutable(runtime / "result.json", {
            "version": study010.VERSION, "task_id": "other-task", "status": "completed",
            "outcome": "failed_checks", "cli_dispatches": 1, "patches": 1, "checks": 1,
            "scope": "Existing task", "evidence_hashes": {}})
    with patch.object(study010.subprocess, "run", side_effect=AssertionError("No execution")):
        with pytest.raises(ValueError, match="different registered task"):
            study010.existing_runtime010(runtime, "new-task")


def test_source_identity_reads_real_installed_helper_layout_and_own_script(tmp_path):
    """Filename strings must remain filenames when imports are packaged."""
    checkout = tmp_path / "checkout with spaces"
    helper_directory = checkout / "scripts/repair010"
    helper_directory.mkdir(parents=True)
    helpers = ("feedback010.py", "codex_context010.py", "codex_transport010.py", "unresolved_registry010.py")
    expected = {}
    for index, filename in enumerate(helpers):
        path = helper_directory / filename
        path.write_text(f"# Installed helper {index}; real filename, not an import name.\n")
        expected["scripts/repair010/" + filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    backend = checkout / "kairos_api/investigations"
    backend.mkdir(parents=True)
    worker = backend / "worker.py"; worker.write_text("# Existing worker snapshot.\n")
    expected["kairos_api/investigations/worker.py"] = hashlib.sha256(worker.read_bytes()).hexdigest()
    expected["scripts/study010.py"] = hashlib.sha256(Path(study010.__file__).read_bytes()).hexdigest()
    actual = study010._source_identity(checkout)
    assert actual == expected
    assert not any("scripts.repair010." in filename for filename in actual)


def test_contending_run_refused_before_provider_database_or_runtime_creation(tmp_path):
    root = tmp_path / "registered"; directory = root / "cases/new-task"
    directory.mkdir(parents=True)
    registry = SimpleNamespace(runtime=root, directory=lambda _: directory)
    options = args(tmp_path)
    options.runtime = tmp_path / "new execution"
    untouched = tmp_path / "unrelated.txt"; untouched.write_text("preserve")
    with study010.runner_lock010(tmp_path):
        with patch.object(study010, "registered_task010", return_value=(registry, {"id": "new-task"})), \
                patch.object(study010, "cli_identity010", side_effect=AssertionError("No provider preflight")), \
                patch.object(study010.subprocess, "run", side_effect=AssertionError("No service execution")):
            with pytest.raises(ValueError, match="Another optional investigation"):
                study010.run010(options)
        assert not options.runtime.exists()
    assert untouched.read_text() == "preserve"
    assert (tmp_path / ".runtime/study010/runner.lock").is_file()


def test_runner_lock_releases_on_failure_and_keeps_same_inode(tmp_path):
    lock = tmp_path / ".runtime/study010/runner.lock"
    with pytest.raises(RuntimeError, match="fixture failure"):
        with study010.runner_lock010(tmp_path):
            before = lock.stat().st_ino
            assert lock.stat().st_mode & 0o777 == 0o600
            assert lock.parent.stat().st_mode & 0o777 == 0o700
            raise RuntimeError("fixture failure")
    assert lock.stat().st_ino == before
    with study010.runner_lock010(tmp_path):
        assert lock.stat().st_ino == before
    assert lock.exists()


@pytest.mark.parametrize("placement", ["directory", "file"])
def test_runner_lock_refuses_symlinks_without_changing_target(tmp_path, placement):
    target = tmp_path / "unrelated"; target.mkdir()
    sentinel = target / "keep.txt"; sentinel.write_text("untouched")
    runtime = tmp_path / ".runtime"; runtime.mkdir()
    if placement == "directory":
        (runtime / "study010").symlink_to(target, target_is_directory=True)
    else:
        directory = runtime / "study010"; directory.mkdir()
        (directory / "runner.lock").symlink_to(sentinel)
    with pytest.raises((ValueError, OSError)):
        with study010.runner_lock010(tmp_path):
            pytest.fail("A symbolic lock must not authorize a run")
    assert sentinel.read_text() == "untouched"


def test_existing_runtime_report_does_not_create_or_take_global_lock(tmp_path):
    root = tmp_path / "registered"; directory = root / "cases/new-task"
    directory.mkdir(parents=True)
    registry = SimpleNamespace(runtime=root, directory=lambda _: directory)
    options = args(tmp_path)
    options.runtime = tmp_path / "saved"; options.runtime.mkdir()
    with patch.object(study010, "registered_task010", return_value=(registry, {"id": "new-task"})), \
            patch.object(study010, "runner_lock010", side_effect=AssertionError("Reports take no lock")):
        result = study010.run010(options)
    assert result["status"] == "incomplete"
    assert not (tmp_path / ".runtime").exists()
