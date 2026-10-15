"""Run one reviewed unresolved Python task through the optional Codex provider.

Doctor and task validation never start inference, Docker or PostgreSQL. A run
owns a new private runtime and refuses to redispatch any existing runtime.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_PREFLIGHT_BYTES = 1024 * 1024
VERSION = "reviewed-unresolved-cli010-v1"
REQUESTED_MODEL = "gpt-6.1-sol"
BUDGETS = {"max_calls": 6, "max_patches": 2, "max_checks": 2, "seconds": 600}
GENERATION = {
    "provider": "codex-cli-chatgpt", "requested_model": REQUESTED_MODEL,
    "model_selection": "Explicit requested model; remote weight bytes are not attested",
    "max_dispatch_seconds": 120, "max_prompt_bytes": 65536,
    "output_tokens_limit": None, "thinking_setting": "CLI default",
    "usage": "Existing signed-in ChatGPT/Codex subscription; no API-key billing fallback",
    "harness_automatic_redispatch": False,
    "internal_provider_retries": "CLI-controlled; invocation count is not network request count",
    "local_4096_1024_profile_applies": False,
}


def _sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode()


def _immutable(path, value):
    raw = _canonical(value)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Receipt exceeds its capture limit")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _load(path):
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_size > MAX_JSON_BYTES:
        raise ValueError("Receipt is not a bounded ordinary file")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate receipt JSON key")
            value[key] = item
        return value
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def _helpers():
    from scripts.repair010.codex_transport010 import CodexInvestigator010, subprocess_environment010
    from scripts.repair010.feedback010 import FeedbackWorker010
    from scripts.repair010.unresolved_registry010 import UnresolvedCaseRegistry010, TASK_KIND
    return CodexInvestigator010, subprocess_environment010, FeedbackWorker010, UnresolvedCaseRegistry010, TASK_KIND


def _command(argv, *, timeout=10, environment=None):
    completed = subprocess.run(argv, capture_output=True, timeout=timeout, check=False,
                               env=environment)
    if len(completed.stdout) + len(completed.stderr) > MAX_PREFLIGHT_BYTES:
        raise ValueError("Preflight output exceeds capture limit")
    return completed


def cli_identity010(executable=None):
    """Read binary metadata and existing login status without opening auth files."""
    _, environment_factory, _, _, _ = _helpers()
    found = str(executable) if executable is not None else shutil.which("codex")
    if not found:
        raise ValueError("Installed Codex CLI is unavailable")
    path = Path(found).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Codex executable must be an ordinary file")
    environment = environment_factory()
    version = _command([str(path), "--no-daemon", "--version"], environment=environment)
    status = _command([str(path), "--no-daemon", "-c", 'forced_login_method="chatgpt"',
                       "login", "status"], environment=environment)
    text = (status.stdout + b"\n" + status.stderr).decode(errors="replace").lower()
    if (version.returncode or status.returncode or
            not any(word in text for word in ("logged in using chatgpt", "logged in with chatgpt"))
            or any(word in text for word in ("api key", "api_key", "apikey"))):
        raise ValueError("An existing ChatGPT CLI login is required; API-key fallback is disabled")
    observed = version.stdout.decode().strip()
    if not observed.startswith("codex-cli "):
        raise ValueError("Unrecognized installed CLI identity")
    return path, {"cli_version": observed, "cli_sha256": _sha(path),
                  "uses_chatgpt_account": True, "uses_api_key": False,
                  "requested_model": REQUESTED_MODEL,
                  "resolved_model": None, "internal_provider_retries": "CLI-controlled/unavailable"}


def registered_task010(manifest, case_root, task_id=None):
    """Accept only the explicit reviewed-unresolved task kind, never benchmarks."""
    if (manifest is None) != (case_root is None):
        raise ValueError("--manifest and --case-root must be supplied together")
    if manifest is None:
        if task_id is not None:
            raise ValueError("--task-id requires a manifest and case root")
        return None, None
    _, _, _, registry_class, task_kind = _helpers()
    registry = registry_class(Path(manifest), Path(case_root))
    value = registry.manifest()
    if task_id is None:
        return registry, None
    # Inspect metadata before get/verify so an old reference-based task is never read.
    candidate = next((item for item in value["cases"] if item.get("id") == task_id), None)
    if not candidate or candidate.get("task_kind") != task_kind or candidate.get("split") != "unresolved":
        raise ValueError("Only a registered reviewed unresolved task is accepted; historical and held-out cases are refused")
    case = registry.get(task_id)
    return registry, case


def doctor010(args):
    path, identity = cli_identity010(args.codex)
    registry, case = registered_task010(args.manifest, args.case_root, args.task_id)
    root = Path(args.checkout)
    usage = shutil.disk_usage(root)
    if usage.free < 4 * 1024**3:
        raise ValueError("Storage reserve below 4 GiB")
    return {"operation": "doctor", "passed": True, **identity,
            "cli_discovered": bool(path), "native_postgresql_available": bool(shutil.which("initdb") and shutil.which("pg_ctl")),
            "docker_cli_available": bool(shutil.which("docker")),
            "free_bytes": usage.free, "required_free_bytes": 4 * 1024**3,
            "registered_task": case["id"] if case else None,
            "registry_validated": registry is not None, "inference_started": False,
            "docker_started": False, "database_started": False,
            "scope": "Read-only readiness; does not prove model availability or repair effectiveness"}


def _source_identity(checkout):
    files = {"scripts/study010.py": Path(__file__)}
    for filename in ("feedback010.py", "codex_context010.py", "codex_transport010.py", "unresolved_registry010.py"):
        installed = checkout / "scripts/repair010" / filename
        files["scripts/repair010/" + filename] = installed if installed.is_file() else Path(__file__).with_name(filename)
    for path in sorted((checkout / "kairos_api/investigations").glob("*.py")):
        files[path.relative_to(checkout).as_posix()] = path
    return {name: _sha(path) for name, path in files.items()}


def report010(runtime, expected_version=VERSION):
    """Validate the saved result and its evidence hashes without starting work."""
    root = Path(runtime)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Investigation runtime is unavailable")
    receipt_path = root / "result.json"
    if not receipt_path.exists():
        return {"operation": "report", "status": "incomplete", "automatic_redispatch": False,
                "detail": "Existing runtime is preserved; no new dispatch is authorized"}
    receipt = _load(receipt_path)
    if receipt.get("version") != expected_version:
        raise ValueError("Unsupported investigation receipt version")
    hashes = receipt.get("evidence_hashes")
    if not isinstance(hashes, dict):
        raise ValueError("Investigation evidence hashes are missing")
    for name, expected in hashes.items():
        part = PurePosixPath(name)
        if part.is_absolute() or ".." in part.parts or str(part) != name or "\\" in name:
            raise ValueError("Evidence path escapes the owned runtime")
        path = root.joinpath(*part.parts)
        if any(item.is_symlink() for item in (path, *path.parents) if item != root.parent):
            raise ValueError("Evidence path traverses a symlink")
        if not path.is_file() or _sha(path) != expected:
            raise ValueError("Investigation evidence hash mismatch")
    return {"operation": "report", "status": receipt["status"], "outcome": receipt["outcome"],
            "task_id": receipt["task_id"], "cli_dispatches": receipt["cli_dispatches"],
            "patches": receipt["patches"], "checks": receipt["checks"],
            "verified": receipt["outcome"] == "verified_repair", "evidence_verified": True,
            "source_unchanged": receipt.get("source_unchanged"),
            "failure": receipt.get("failure"), "cleanup_errors": receipt.get("cleanup_errors", []),
            "automatic_redispatch": False, "scope": receipt["scope"]}


def _evidence_hashes(runtime):
    files = [path for path in runtime.rglob("*") if path.is_file() and not path.is_symlink()
             and path.relative_to(runtime).parts[0] not in {"postgres-data"}
             and path.name not in {"result.json", "postgres.log", "postgres-setup.log"}]
    return {path.relative_to(runtime).as_posix(): _sha(path) for path in sorted(files)}


def checked_runtime010(value, registry, case):
    """Keep owned state outside registered source and verification material."""
    original = Path(value).absolute()
    # Inspect the original path first: resolve() would otherwise conceal links.
    for component in (original, *original.parents):
        if component.is_symlink():
            raise ValueError("Owned runtime must not traverse symlinks")
    runtime = original.resolve(strict=False)
    registered = Path(registry.runtime).resolve(strict=True)
    directory = Path(registry.directory(case)).resolve(strict=True)
    if (runtime.is_relative_to(directory) or directory.is_relative_to(runtime)
            or registered.is_relative_to(runtime)):
        raise ValueError("Owned runtime overlaps registered source or verification material")
    return runtime


def existing_runtime010(runtime, task_id, expected_version=VERSION):
    """Inspect an existing runtime without authorizing a changed task or dispatch."""
    experiment_path = runtime / "experiment.json"
    if experiment_path.exists():
        experiment = _load(experiment_path)
        if experiment.get("task_id") != task_id:
            raise ValueError("Existing runtime belongs to a different registered task")
    result = report010(runtime, expected_version=expected_version)
    if result.get("task_id") is not None and result["task_id"] != task_id:
        raise ValueError("Existing runtime result belongs to a different registered task")
    return result


@contextmanager
def runner_lock010(checkout):
    """Permit one optional investigation per checkout on local macOS/Linux.

    Keep the lock inode permanently: unlinking it would let two processes lock
    different inodes at the same pathname. Closing releases the OS lock even
    after an exception or process termination. Windows execution is not claimed.
    """
    if os.name != "posix":
        raise ValueError("The optional investigation lock requires local macOS or Linux")
    import fcntl
    directory = Path(checkout) / ".runtime/study010"
    for component in (directory, *directory.parents):
        if component.is_symlink():
            raise ValueError("Runner lock directory must not traverse symlinks")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    details = directory.lstat()
    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid():
        raise ValueError("Runner lock requires an owned private directory")
    directory.chmod(0o700)
    descriptor = os.open(directory / "runner.lock",
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         0o600)
    try:
        details = os.fstat(descriptor)
        if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
                or details.st_uid != os.getuid()):
            raise ValueError("Runner lock must be an owned ordinary file without links")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise ValueError("Another optional investigation is active; no work was started") from None
            raise
        yield
    finally:
        os.close(descriptor)


def run010(args, *, policy=None):
    """Run one task once. All owned services are stopped through finally cleanup."""
    checkout = Path(args.checkout).resolve(strict=True)
    registry, case = registered_task010(args.manifest, args.case_root, args.task_id)
    if case is None:
        raise ValueError("run requires --manifest, --case-root and --task-id")
    runtime = checked_runtime010(args.runtime or checkout / ".runtime/study010" / case["id"], registry, case)
    if runtime.exists():
        return (existing_runtime010(runtime, case["id"]) if policy is None else
                    existing_runtime010(runtime, case["id"], expected_version=policy.version))
    with runner_lock010(checkout):
        # The other process may have completed between inspection and locking.
        if runtime.exists():
            return (existing_runtime010(runtime, case["id"]) if policy is None else
                    existing_runtime010(runtime, case["id"], expected_version=policy.version))
        if policy is None:
            return _run_new010(args, checkout, registry, case, runtime)
        return _run_new010(args, checkout, registry, case, runtime, policy=policy)


def _run_new010(args, checkout, registry, case, runtime, *, policy=None):
    """Execute only while the checkout-owned nonblocking lock is held."""
    executable, identity = cli_identity010(args.codex)
    from scripts.study007_runtime import storage_guard
    from kairos_api.investigations.repository import InvestigationRepository
    from kairos_api.investigations.sandbox import Workspace
    from kairos_api.investigations.registry import tree_hash
    from kairos_api.migrations import apply
    from kairos_api.model_runtime import digest
    from psycopg.types.json import Jsonb
    provider_class, _, worker_class, _, _ = _helpers()
    from kairos_api.investigations.contracts import CONFIGURATIONS
    version = VERSION if policy is None else policy.version
    configuration = "loop-v7" if policy is None else policy.configuration
    budgets = dict(BUDGETS if policy is None else CONFIGURATIONS[configuration])
    generation_profile = dict(GENERATION if policy is None else policy.generation)
    base_workspace = Workspace if policy is None or policy.workspace_base is None else policy.workspace_base
    if policy is not None:
        provider_class = policy.provider_factory or provider_class
        worker_class = policy.worker_factory or worker_class
    budget_paths = {"cache": registry.runtime, "state": runtime}
    storage_guard(budget_paths, projected=96 * 1024**2)
    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        raise ValueError("Existing native PostgreSQL tools are required")
    if not shutil.which("docker"):
        raise ValueError("Docker CLI is required for disposable verification")
    additional_sources = {}
    if policy is not None:
        for name in policy.source_files:
            relative = Path(name)
            path = checkout / relative
            if (not name or relative.is_absolute() or '..' in relative.parts
                    or path.is_symlink() or not path.resolve(strict=True).is_relative_to(checkout)):
                raise ValueError("Additional policy source escapes the checkout")
            additional_sources[name] = _sha(path)
    source_identity = {**_source_identity(checkout), **additional_sources}
    runtime.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    experiment = {"version": version, "task_id": case["id"], "task_digest": registry.fingerprint(case),
                  "provider": identity, "source": source_identity, "generation": generation_profile,
                  "budgets": budgets, "action_protocol": configuration,
                  "scope": "One reviewed unresolved task; a checked outcome does not establish universal repair ability"}
    if policy is not None:
        experiment["policy"] = policy.metadata
    _immutable(runtime / "experiment.json", experiment)
    _immutable(runtime / "model-profile.json", {"experiment010": experiment})
    repository = provider = None
    running = docker_started = False
    database_start_attempted = False
    database = runtime / "postgres-data"
    record = None
    failure = None
    cleanup_errors = []
    before = tree_hash(registry.directory(case) / "source")
    started = time.monotonic()
    generation = generation_profile
    previous_manifest = os.environ.get("KAIROS_INVESTIGATION_MODEL_MANIFEST")
    os.environ["KAIROS_INVESTIGATION_MODEL_MANIFEST"] = str(runtime / "model-profile.json")

    class ExperimentRepository(InvestigationRepository):
        def enqueue(self, *values, **settings):
            row = super().enqueue(*values, **settings)
            with self.connect() as connection:
                saved = self._row(connection, row["id"], lock=True)
                if saved["model_calls"]:
                    raise ValueError("Existing dispatch configuration cannot be rewritten")
                snapshot = {**saved["config_snapshot"], "generation": generation,
                            "experiment_version": version}
                connection.execute("SET LOCAL synchronous_commit=on")
                connection.execute("UPDATE kairos_investigations SET config_snapshot=%s,config_digest=%s WHERE id=%s",
                                   (Jsonb(snapshot), digest(snapshot), saved["id"]))
            return self.read(row["id"])

    def stop_docker():
        nonlocal docker_started
        if docker_started:
            active = _command(["docker", "ps", "-q"])
            if active.returncode or not active.stdout.strip():
                completed = _command(["docker", "desktop", "stop"], timeout=60)
                if completed.returncode:
                    raise ValueError("Owned Docker shutdown failed")
                docker_started = False

    class SequentialChecks(base_workspace):
        def checks(self, timeout=120):
            nonlocal docker_started
            available = _command(["docker", "info", "--format", "{{.ServerVersion}}"]).returncode == 0
            try:
                if not available:
                    if sys.platform != "darwin":
                        raise ValueError("Start the existing Docker engine before verification on this platform")
                    launch = _command(["open", "-a", "Docker"])
                    if launch.returncode:
                        raise ValueError("Disposable verification engine startup failed")
                    docker_started = True
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        if not _command(["docker", "info", "--format", "{{.ServerVersion}}"]).returncode:
                            break
                        time.sleep(1)
                    else:
                        raise ValueError("Disposable verification engine startup deadline exceeded")
                if _command(["docker", "image", "inspect", case["image"]]).returncode:
                    raise ValueError("Reviewed verifier image unavailable; automatic downloads are disabled")
                return super().checks(timeout)
            finally:
                stop_docker()

    try:
        with (runtime / "postgres-setup.log").open("wb") as log:
            subprocess.run([initdb, "-D", str(database), "-A", "trust", "-U", "study010", "--no-instructions"],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        # TCP is loopback-only. Disable UNIX sockets rather than creating a trust
        # socket in /tmp or exceeding macOS socket-name limits in a deep checkout.
        database_start_attempted = True
        completed = _command([pg_ctl, "-D", str(database), "-l", str(runtime / "postgres.log"),
                              "-o", f'-h 127.0.0.1 -p {port} -k ""', "-w", "start"], timeout=30)
        if completed.returncode:
            raise ValueError("Owned PostgreSQL startup failed")
        running = True
        url = f"postgresql://study010@127.0.0.1:{port}/postgres"
        apply(url)
        repository = ExperimentRepository(url, runtime / "blobs", registry)
        repository.initialize()
        provider = provider_class(runtime / "provider", executable,
                                  identity["cli_version"], identity["cli_sha256"],
                                  model_id=REQUESTED_MODEL)
        worker = worker_class(repository, provider, SequentialChecks)
        record = repository.enqueue("study010", version + ":" + case["id"], case["id"], configuration)
        record = worker.run_once()
        if not record or record["task_id"] != case["id"]:
            raise ValueError("Owned queue returned unexpected work")
        if record["status"] in {"queued", "running"}:
            raise ValueError("Interrupted work is preserved; automatic redispatch is disabled")
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)[:500]}
    finally:
        def cleanup(operation):
            try:
                operation()
            except Exception as error:
                cleanup_errors.append(type(error).__name__)
        if provider is not None and hasattr(provider, "finish"):
            cleanup(provider.finish)
        if repository is not None:
            if record is not None and record.get("id"):
                try:
                    record = repository.read(str(record["id"]), "study010")
                except Exception as error:
                    cleanup_errors.append("FinalRecordRead:" + type(error).__name__)
            cleanup(repository.close)
        def stop_database():
            # pg_ctl can time out after launching the server. The private data
            # directory still identifies only our server, so check it explicitly.
            active = subprocess.run([pg_ctl, "-D", str(database), "status"],
                                    check=False, capture_output=True, timeout=10)
            if active.returncode == 0:
                subprocess.run([pg_ctl, "-D", str(database), "-m", "fast", "-w", "stop"],
                               check=True, capture_output=True, timeout=30)
        if running or database_start_attempted:
            cleanup(stop_database)
        cleanup(stop_docker)
        if previous_manifest is None:
            os.environ.pop("KAIROS_INVESTIGATION_MODEL_MANIFEST", None)
        else:
            os.environ["KAIROS_INVESTIGATION_MODEL_MANIFEST"] = previous_manifest
    after = tree_hash(registry.directory(case) / "source")
    if before != after:
        failure = {"type": "SourceIsolationError", "message": "Original source changed during investigation"}
    if record is not None:
        _immutable(runtime / "record.json", record)
    result = {"version": version, "task_id": case["id"],
              "status": record["status"] if record else "failed",
              "outcome": record["outcome"] if record else "environment_failure",
              "cli_dispatches": record["model_calls"] if record else 0,
              "patches": record["patch_count"] if record else 0,
              "checks": record["check_count"] if record else 0,
              "source_unchanged": before == after, "failure": failure, "cleanup_errors": cleanup_errors,
              "elapsed_seconds": time.monotonic() - started, "new_api_billing_enabled": False,
              "automatic_redispatch": False, "recorded_at": datetime.now(timezone.utc).isoformat(),
              "scope": experiment["scope"], "evidence_hashes": _evidence_hashes(runtime)}
    if failure is not None or cleanup_errors:
        result["status"] = "failed"
        result["outcome"] = "environment_failure"
    _immutable(runtime / "result.json", result)
    return report010(runtime, expected_version=version)


def parser010():
    def options(parser):
        for name in ("manifest", "case-root", "runtime", "codex", "checkout"):
            parser.add_argument("--" + name, type=Path, default=argparse.SUPPRESS)
        parser.add_argument("--task-id", default=argparse.SUPPRESS)
    parser = argparse.ArgumentParser(description=__doc__)
    options(parser)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("doctor", "validate-task", "run", "report"):
        options(commands.add_parser(name))
    parser.set_defaults(manifest=None, case_root=None, task_id=None, runtime=None, codex=None, checkout=ROOT)
    return parser


def main(argv=None):
    args = parser010().parse_args(argv)
    try:
        if args.operation == "doctor":
            result = doctor010(args)
        elif args.operation == "validate-task":
            if not args.task_id:
                raise ValueError("validate-task requires --manifest, --case-root and --task-id")
            registry, case = registered_task010(args.manifest, args.case_root, args.task_id)
            result = {"operation": "validate-task", "passed": True, "task_id": case["id"],
                      "task_digest": registry.fingerprint(case), "reference_repair_required": False}
        elif args.operation == "run":
            result = run010(args)
        else:
            if not args.runtime:
                raise ValueError("report requires --runtime")
            result = report010(args.runtime)
        print(json.dumps(result, sort_keys=True))
        return 1 if (result.get("status") in {"failed", "incomplete", "unknown"}
                     or result.get("outcome") in {"unknown_dispatch", "environment_failure"}) else 0
    except Exception as error:
        print(json.dumps({"operation": args.operation, "passed": False,
                          "error_type": type(error).__name__, "detail": str(error)[:500]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
