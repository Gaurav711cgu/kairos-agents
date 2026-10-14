"""One reviewer entry point. All mutable state and services belong to reviewer005.

Examples: python3 -m scripts.reviewer demo
          python3 -m scripts.reviewer fullstack
          python3 -m scripts.reviewer fullstack --with-inference --model-cache /path/to/prepared/cache
          python3 -m scripts.reviewer check --fullstack
          python3 -m scripts.reviewer repair
          python3 -m scripts.reviewer stop
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import xml.etree.ElementTree as ET

from scripts.reviewer_evidence import validate_package
from scripts.reviewer_runtime import (ensure_runtime, is_owned_process, private_json, process_record,
    require_ports, resource_names, stop as stop_runtime)

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
BUILD_NAME = ".next-reviewer005"
from scripts.acceptance007 import BACKEND_PATTERNS, backend_files


def environment(runtime, mode="recorded", include_setup=False):
    # Caller shell settings must never connect the reviewer to an existing database or model.
    env = {key: value for key, value in os.environ.items() if not key.startswith("KAIROS_") and key not in {"DATABASE_URL", "TEST_DATABASE_URL"}}
    env.update(PYTHONPATH=str(ROOT), KAIROS_REVIEWER_RUNTIME=str(runtime), KAIROS_REVIEWER_STATE=str(runtime / "services.json"),
        KAIROS_REVIEWER_URL="http://127.0.0.1:3310", KAIROS_EVIDENCE_MODE=mode, KAIROS_EVIDENCE_DIR=str(DASHBOARD / "evidence"),
        KAIROS_NEXT_BUILD_DIR=BUILD_NAME, KAIROS_TEST_PYTHON=str(runtime / "venv/bin/python"), HOSTNAME="127.0.0.1", PORT="3310", NEXT_TELEMETRY_DISABLED="1")
    if mode == "live":
        values = dict(line.split("=", 1) for line in (runtime / "application.env").read_text().splitlines() if line and not line.startswith("#"))
        env.update(values)
        if include_setup:
            setup = dict(line.split("=", 1) for line in (runtime / "migration.env").read_text().splitlines() if line)
            env.update(setup)
    return env


def require_versions(node=True):
    if sys.version_info < (3, 12): raise RuntimeError("Python 3.12 or newer is required")
    if node:
        for executable in ("node", "npm"):
            if not shutil.which(executable): raise RuntimeError("Node.js 24 and npm are required")
        value = subprocess.check_output(["node", "--version"], text=True).strip()
        if int(value.removeprefix("v").split(".")[0]) != 24:
            raise RuntimeError("Use Node.js 24 for the locked reviewer release")


def command(argv, runtime, name, cwd=ROOT, env=None, timeout=600):
    logs = runtime / "checks"; logs.mkdir(exist_ok=True)
    path = logs / (name + ".log")
    print(name + "…", flush=True)
    stamp = datetime.now(timezone.utc).isoformat(); started = time.monotonic()
    timed_out = False
    with path.open("w") as output:
        path.chmod(0o600)
        try:
            result = subprocess.run(argv, cwd=cwd, env=env or environment(runtime), stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            returncode = 124; timed_out = True
    receipt = {"name": name, "started_at": stamp, "command": argv, "returncode": returncode, "timed_out": timed_out, "elapsed_seconds": round(time.monotonic() - started, 3), "log": str(path)}
    private_json(logs / (name + ".receipt.json"), receipt)
    if returncode: raise RuntimeError(name + " failed; inspect " + str(path))
    return receipt


def ensure_node(runtime):
    lock = hashlib.sha256((DASHBOARD / "package-lock.json").read_bytes()).hexdigest()
    receipt = runtime / "node-install.json"
    if receipt.exists() and json.loads(receipt.read_text()).get("lock_sha256") == lock and (DASHBOARD / "node_modules/next/package.json").exists():
        return
    command(["npm", "ci", "--no-audit"], runtime, "node-install", cwd=DASHBOARD)
    private_json(receipt, {"lock_sha256": lock, "node": subprocess.check_output(["node", "--version"], text=True).strip()})


def ensure_python(runtime):
    path = runtime / "venv"; interpreter = path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lock = hashlib.sha256((ROOT / "requirements-api.lock").read_bytes() + (ROOT / "requirements-reviewer.lock").read_bytes()).hexdigest(); receipt = runtime / "python-install.json"
    if not interpreter.exists():
        # Standalone macOS Python needs its original shared-library layout.
        venv.create(path, with_pip=True, symlinks=os.name != "nt")
    if not receipt.exists() or json.loads(receipt.read_text()).get("lock_sha256") != lock:
        command([str(interpreter), "-m", "pip", "install", "-r", str(ROOT / "requirements-reviewer.lock")], runtime, "python-install")
        private_json(receipt, {"lock_sha256": lock, "python": subprocess.check_output([str(interpreter), "--version"], text=True).strip()})
    return interpreter


def ensure_docker():
    if not shutil.which("docker"): raise RuntimeError("Docker is required for full-stack checks and repair reproduction")
    result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True)
    if result.returncode and sys.platform == "darwin":
        subprocess.run(["open", "-a", "Docker"], capture_output=True, check=True)
        for _ in range(120):
            if subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True).returncode == 0: return
            time.sleep(1)
    elif result.returncode == 0: return
    raise RuntimeError("Docker daemon is unavailable; start it and retry")


def prepare_web(runtime, mode):
    ensure_node(runtime); validate_package(DASHBOARD / "evidence")
    env = environment(runtime, mode)
    command(["npm", "run", "build"], runtime, "website-build-" + mode, cwd=DASHBOARD, env=env)
    directory = DASHBOARD / BUILD_NAME; web = directory / "standalone"
    if not (web / "server.js").exists(): raise RuntimeError("Production standalone entry point missing after build")
    shutil.copytree(directory / "static", web / BUILD_NAME / "static", dirs_exist_ok=True)
    shutil.copytree(DASHBOARD / "public", web / "public", dirs_exist_ok=True)
    # The server-only absolute package setting is stable even when Next traces a different source tree layout.
    return web, env


def ready(url, process, deadline=90):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if process.poll() is not None: raise RuntimeError("Owned service exited during startup; inspect reviewer runtime logs")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200: return
        except (urllib.error.URLError, TimeoutError): pass
        time.sleep(0.5)
    raise RuntimeError("Owned service startup deadline exceeded")


def active_state(runtime, mode, with_inference=False, *, model_cache=None,
                 case_root=None, model_profile="coder"):
    path = runtime / "state.json"
    if path.exists():
        value = json.loads(path.read_text()); owner = ensure_runtime(runtime)["owner"]
        if value.get("owner") != owner: raise RuntimeError("Reviewer process state owner mismatch")
        if value.get("supervisor") and is_owned_process(value["supervisor"]):
            if value.get("mode") != mode: raise RuntimeError("Another reviewer mode is running; stop it before changing modes")
            if value.get("inference_enabled", False) != with_inference:
                raise RuntimeError("Reviewer inference setting differs; stop owned services before changing it")
            if with_inference:
                cache = Path(model_cache or ROOT / ".runtime/investigations").expanduser().resolve()
                cases = Path(case_root or cache).expanduser().resolve()
                configuration = runtime / "inference-config.json"
                if configuration.is_symlink() or not configuration.is_file():
                    raise RuntimeError("Running inference configuration is unavailable; stop owned services before restart")
                captured = json.loads(configuration.read_text())
                requested = {"profile": model_profile, "model_cache": str(cache), "case_root": str(cases)}
                if any(captured.get(key) != item for key, item in requested.items()):
                    raise RuntimeError("Running model profile or prepared paths differ; stop owned services before changing them")
            print("Reviewer " + mode + " already running: http://127.0.0.1:3310", flush=True)
            if with_inference:
                print("Reusing the original live session deadline; this command does not extend it.", flush=True)
            return True
        if any(is_owned_process(item) for item in value.get("processes", [])):
            raise RuntimeError("Orphaned owned services remain; run reviewer stop before restart")
    return False


def serve(runtime, mode, no_build=False, *, with_inference=False, model_cache=None,
          case_root=None, model_profile="coder", session_seconds=900):
    if with_inference and mode != "fullstack":
        raise ValueError("Live inference is available only in fullstack mode")
    owner = ensure_runtime(runtime)["owner"]
    if active_state(runtime, mode, with_inference, model_cache=model_cache,
                    case_root=case_root, model_profile=model_profile): return
    require_ports([3310] + ([8310] if mode == "fullstack" else []))
    inference = None
    if with_inference:
        from scripts import reviewer_inference
        # Validate existing weights, source, storage and port ownership before
        # Docker, database provisioning or model execution starts.
        inference = reviewer_inference.preflight(runtime, model_cache, case_root,
                                                model_profile, session_seconds)
    interpreter = None
    try:
        if mode == "fullstack":
            ensure_docker(); interpreter = ensure_python(runtime)
            if inference: reviewer_inference.verify_image(inference)
            command([str(interpreter), "-m", "scripts.reviewer_services", "prepare", "--runtime", str(runtime), "--evidence", str(DASHBOARD / "evidence")],
                    runtime, "fullstack-provision", timeout=300)
        evidence_mode = "live" if mode == "fullstack" else "recorded"
        if no_build:
            web = DASHBOARD / BUILD_NAME / "standalone"; env = environment(runtime, evidence_mode)
            if not (web / "server.js").exists(): raise RuntimeError("Production build missing")
        else: web, env = prepare_web(runtime, evidence_mode)
        if inference:
            env.update(inference.environment())
            private_json(runtime / "inference-config.json", inference.receipt())
    except BaseException:
        if mode == "fullstack": stop_runtime(runtime)
        raise
    processes = []; logs = []
    def interrupted(*_): raise KeyboardInterrupt()
    try:
        state = {"owner": owner, "mode": mode, "inference_enabled": with_inference,
                 "supervisor": process_record(type("Process", (), {"pid": os.getpid()})()), "processes": []}
        private_json(runtime / "state.json", state)
        prior = signal.signal(signal.SIGTERM, interrupted)
    except BaseException:
        # Provisioning already started owned containers. Failure to record the
        # supervisor or install its handler cannot leave those containers running.
        if mode == "fullstack": stop_runtime(runtime)
        raise
    def launch(name, argv, cwd=ROOT):
        path = runtime / (name + ".log"); log = path.open("a"); path.chmod(0o600); logs.append(log)
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT); processes.append(process)
        state["processes"].append(process_record(process)); private_json(runtime / "state.json", state)
        return process
    model_process = model_log = None
    try:
        if mode == "fullstack":
            api = launch("api", [str(interpreter), "-m", "uvicorn", "kairos_api.app:app", "--host", "127.0.0.1", "--port", "8310", "--no-access-log"])
            ready("http://127.0.0.1:8310/api/health", api)
        if inference:
            model_process, model_log = reviewer_inference.start(inference)
            state["processes"].append(process_record(model_process))
            private_json(runtime / "state.json", state)
            command([str(interpreter), "-m", "scripts.reviewer_inference", "attest"],
                    runtime, "local-inference-attestation", env=env, timeout=30)
            launch("investigation-worker", [str(interpreter), "-m", "kairos_api.investigations.worker"])
        website = launch("website", ["node", "server.js"], web); ready("http://127.0.0.1:3310", website)
        private_json(runtime / "services.json", {"owner": owner, "mode": mode, "web": "http://127.0.0.1:3310",
            "api": "http://127.0.0.1:8310" if mode == "fullstack" else None,
            "inference": bool(inference), "worker": bool(inference), "ready": True,
            "session_seconds": inference.session_seconds if inference else None})
        print("Reviewer " + mode + " ready: http://127.0.0.1:3310. Ctrl-C stops owned services; stored data remains.", flush=True)
        if mode == "fullstack": print("Synthetic sign-in credentials are private: " + str(runtime / "identity.local.json"), flush=True)
        deadline = time.monotonic() + inference.session_seconds if inference else None
        if inference:
            print(f"Local model and worker ready. Session stops after {inference.session_seconds} seconds; investigation results and volumes remain.", flush=True)
        while True:
            if any(process.poll() is not None for process in processes): raise RuntimeError("Owned service exited; inspect reviewer runtime logs")
            if model_process is not None and model_process.poll() is not None:
                raise RuntimeError("Owned local model exited; inspect the private inference log")
            if deadline is not None and time.monotonic() >= deadline:
                print("Live session duration reached; stopping owned services.", flush=True)
                break
            time.sleep(1)
    except KeyboardInterrupt: pass
    finally:
        primary_failure = sys.exc_info()[0] is not None
        cleanup_failure = None
        def cleanup(operation):
            nonlocal cleanup_failure
            try: operation()
            except BaseException as error:
                if cleanup_failure is None: cleanup_failure = error
        def wait_owned(process):
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        # Each teardown runs even if an earlier signal, process, log or receipt
        # operation fails. Preserve the original execution error when present.
        cleanup(lambda: signal.signal(signal.SIGTERM, prior))
        for process in reversed(processes):
            cleanup(lambda process=process: process.terminate() if process.poll() is None else None)
        for process in processes:
            cleanup(lambda process=process: wait_owned(process))
        if model_process is not None:
            cleanup(lambda: reviewer_inference.finish(model_process, model_log))
        for log in logs: cleanup(log.close)
        state.update(supervisor=None, processes=[])
        cleanup(lambda: private_json(runtime / "state.json", state))
        cleanup(lambda: private_json(runtime / "services.json", {"owner": owner, "mode": mode,
            "ready": False, "inference": False, "worker": False}))
        if mode == "fullstack": cleanup(lambda: stop_runtime(runtime))
        if cleanup_failure is not None and not primary_failure: raise cleanup_failure


def background(runtime, mode):
    path = runtime / (mode + "-supervisor.log"); log = path.open("w"); path.chmod(0o600)
    process = subprocess.Popen([sys.executable, "-m", "scripts.reviewer", mode, "--runtime", str(runtime), "--no-build"],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=environment(runtime))
    return process, log


def shutdown(process, log):
    if process.poll() is None: process.terminate()
    try: process.wait(timeout=30)
    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    log.close()


def run_checks(runtime, fullstack):
    started = datetime.now(timezone.utc).isoformat(); checks = []; omissions = []
    interpreter = ensure_python(runtime); ensure_node(runtime)
    env = environment(runtime)
    for name, argv in (("frontend-boundary", ["npm", "run", "test:boundary"]), ("frontend-client", ["npm", "run", "test:client"]),
                       ("recorded-package", ["npm", "run", "test:recorded"]), ("frontend-lint", ["npm", "run", "lint"])):
        checks.append(command(argv, runtime, name, cwd=DASHBOARD, env=env))
    prepare_web(runtime, "recorded")
    checks.append(command(["npm", "run", "typecheck"], runtime, "frontend-types", cwd=DASHBOARD, env=env))
    process, log = background(runtime, "demo")
    try:
        ready("http://127.0.0.1:3310", process)
        checks.append(command([str(DASHBOARD / "node_modules/.bin/playwright"), "install", "chromium"], runtime, "browser-install", cwd=DASHBOARD, env=env))
        checks.append(command([str(DASHBOARD / "node_modules/.bin/playwright"), "test", "--config", "playwright.recorded.config.ts"], runtime, "recorded-browser", cwd=DASHBOARD, env=env))
    finally: shutdown(process, log)
    require_ports([3104,8195])
    fixture_env={**env,'KAIROS_TEST_PYTHON':str(interpreter),'KAIROS_NEXT_BUILD_DIR':'.next-fixture007',
                 'PLAYWRIGHT_JSON_OUTPUT_FILE':str(runtime/'checks/fixture-browser.json')}
    checks.append(command([str(DASHBOARD/'node_modules/.bin/playwright'),'test','--config','playwright.config.ts',
                           '--reporter=list,json'],runtime,'fixture-browser',cwd=DASHBOARD,env=fixture_env))
    if fullstack:
        ensure_docker()
        # Provisioning happens before live services and does not touch the earlier local installation.
        checks.append(command([str(interpreter), "-m", "scripts.reviewer_services", "prepare", "--runtime", str(runtime), "--evidence", str(DASHBOARD / "evidence")], runtime, "fullstack-provision", timeout=300))
        env = environment(runtime, "live", include_setup=True)
        xml = runtime / "checks/backend.xml"
        checks.append(command([str(interpreter), "-m", "pytest", *backend_files(), "-q", "--tb=short", "--junitxml=" + str(xml)], runtime, "backend", env=env))
        # Runtime evidence mode is explicit. Rebuild live for configurations that evaluate server modules during build.
        prepare_web(runtime, "live"); process, log = background(runtime, "fullstack")
        try:
            ready("http://127.0.0.1:8310/api/health", process, 180); ready("http://127.0.0.1:3310", process, 180)
            checks.append(command([str(interpreter), "-m", "scripts.verify_reviewer005", "--runtime", str(runtime)], runtime, "private-state", env=env))
            checks.append(command([str(DASHBOARD / "node_modules/.bin/playwright"), "test", "--config", "playwright.reviewer.config.ts"], runtime, "live-browser", cwd=DASHBOARD, env=env))
        finally: shutdown(process, log)
    else:
        xml = runtime / "checks/backend.xml"
        checks.append(command([str(interpreter), "-m", "pytest", *backend_files(), "-q", "--tb=short", "--junitxml=" + str(xml)], runtime, "backend", env=env))
        omissions.append("PostgreSQL and actual OIDC journeys were not selected; use check --fullstack for full acceptance.")
    omissions.extend(["Real model/Docker opt-in probes retain separate build004 receipts; no inference was run.",
                      "Historical repair reproduction is a separate reviewer repair command and receipt.",
                      "Capacity and frozen model studies were preserved rather than rerun."])
    tree = ET.parse(xml); cases = tree.findall(".//testcase")
    checks = [json.loads(path.read_text()) for path in sorted((runtime / "checks").glob("*.receipt.json"))
              if json.loads(path.read_text()).get("started_at", "") >= started]
    receipt = {"version": "reviewer-acceptance-v1", "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "fullstack": fullstack, "passed": all(item["returncode"] == 0 for item in checks), "checks": checks,
        "backend": {"tests": len(cases), "skipped": sum(item.find("skipped") is not None for item in cases),
                    "failed": sum(item.find("failure") is not None or item.find("error") is not None for item in cases)},
        "omissions": omissions, "backend_scope": list(BACKEND_PATTERNS), "inference_calls": 0}
    private_json(runtime / "acceptance.json", receipt)
    print("Reviewer checks passed. Aggregate receipt: " + str(runtime / "acceptance.json"), flush=True)


def check(runtime, fullstack):
    require_ports([3310] + ([8310] if fullstack else []))
    started = datetime.now(timezone.utc).isoformat()
    try:
        run_checks(runtime, fullstack)
    except BaseException as error:
        receipts = []
        for path in sorted((runtime / "checks").glob("*.receipt.json")):
            value = json.loads(path.read_text())
            if value.get("started_at", "") >= started: receipts.append(value)
        private_json(runtime / "acceptance.json", {"version": "reviewer-acceptance-v1", "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(), "fullstack": fullstack, "passed": False,
            "checks": receipts, "failure": type(error).__name__, "inference_calls": 0})
        # There is no successful aggregate receipt when an acceptance phase stops early.
        if fullstack: stop_runtime(runtime)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["demo", "fullstack", "repair", "check", "stop"])
    parser.add_argument("--runtime", type=Path, default=Path(os.environ.get("KAIROS_REVIEWER_RUNTIME", str(ROOT / ".runtime/reviewer005"))))
    parser.add_argument("--fullstack", action="store_true", help="Add PostgreSQL and actual OIDC journeys to check")
    parser.add_argument("--recorded-only", action="store_true", help="Omit Docker/PostgreSQL/OIDC; receipt records this limitation")
    parser.add_argument("--no-build", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--with-inference", action="store_true", help="Start the pinned local model and real worker in fullstack mode")
    parser.add_argument("--model-cache", type=Path, help="Existing pinned runtime/model cache; weights are reused, never downloaded")
    parser.add_argument("--case-root", type=Path, help="Prepared root containing cases/<registered task ID>; defaults to model cache")
    parser.add_argument("--model-profile", choices=["coder", "qwen3"], default="coder", help="Pinned local inference profile (default: coder)")
    parser.add_argument("--session-seconds", type=int, default=900, help="Opt-in live session duration, 60–3600 seconds (default: 900)")
    args = parser.parse_args(); runtime = args.runtime.expanduser().absolute()
    try:
        if args.with_inference and args.mode != "fullstack":
            raise ValueError("--with-inference requires fullstack mode")
        if not args.with_inference and (args.model_cache is not None or args.case_root is not None):
            raise ValueError("--model-cache and --case-root require --with-inference")
        require_versions(node=args.mode in {"demo", "fullstack", "check"})
        ensure_runtime(runtime)
        if args.with_inference:
            # A clean checkout may be launched by a standard-library-only host
            # Python. Install the locked reviewer environment before importing
            # the source/model preflight helpers, then use that interpreter for
            # the owned supervisor as well as API and worker. This light setup
            # precedes Docker and never downloads model weights.
            interpreter = ensure_python(runtime)
            # Compare virtual-environment prefixes: symlinked Python binaries
            # can resolve to the same host executable while loading different
            # site-packages.
            if Path(sys.prefix).resolve() != (runtime / "venv").resolve():
                return subprocess.call([str(interpreter), "-m", "scripts.reviewer",
                                        *sys.argv[1:], "--runtime", str(runtime)],
                                       cwd=ROOT, env=environment(runtime))
        if args.mode == "stop": print(json.dumps(stop_runtime(runtime)), flush=True)
        elif args.mode in {"demo", "fullstack"}:
            serve(runtime, args.mode, args.no_build, with_inference=args.with_inference,
                  model_cache=args.model_cache, case_root=args.case_root,
                  model_profile=args.model_profile, session_seconds=args.session_seconds)
        elif args.mode == "repair":
            ensure_docker(); interpreter = ensure_python(runtime)
            command([str(interpreter), "-m", "scripts.reviewer_repair", "--runtime", str(runtime), "--evidence", str(DASHBOARD / "evidence")], runtime, "repair", timeout=900)
            print("Repair receipt: " + str(runtime / "repair-reproduction.json"), flush=True)
        elif args.mode == "check": check(runtime, args.fullstack and not args.recorded_only)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr); return 1
    except KeyboardInterrupt: return 130
    except Exception:
        # Provider/database exceptions can carry private configuration. Keep diagnostic details in private runtime only.
        import traceback
        path = runtime / "error.log"; path.write_text(traceback.format_exc()); path.chmod(0o600)
        print("Reviewer operation failed. Private diagnostic: " + str(path), file=sys.stderr); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
