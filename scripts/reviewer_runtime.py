"""Private reviewer state and ownership checks; never targets unrelated services."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import time

LABEL = "io.kairos.reviewer.owner"


def private_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".pending")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


def process_identity(pid: int):
    """The start time plus full command protects against PID reuse on macOS/Linux."""
    result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart=", "-o", "command="], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def process_record(process):
    identity = process_identity(process.pid)
    if not identity:
        raise RuntimeError("Owned service exited before its identity was recorded")
    return {"pid": process.pid, "identity": identity}


def is_owned_process(record):
    if (not isinstance(record, dict) or type(record.get("pid")) is not int or record["pid"] <= 0
            or not isinstance(record.get("identity"), str) or not record["identity"]):
        return False
    current = process_identity(record["pid"])
    return current is not None and current == record["identity"]


def terminate_owned(record, timeout=12):
    if not is_owned_process(record):
        return False
    os.kill(record["pid"], signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while is_owned_process(record) and time.monotonic() < deadline:
        time.sleep(0.1)
    if is_owned_process(record):
        os.kill(record["pid"], signal.SIGKILL)
    return True


def port_free(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def require_ports(ports):
    for port in ports:
        if not port_free(port):
            raise RuntimeError(f"Port {port} belongs to an existing service; it was preserved")


def ensure_runtime(path: Path):
    if path.is_symlink():
        raise RuntimeError("Reviewer runtime must not be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    identity = path / "owner.json"
    if identity.exists():
        value = json.loads(identity.read_text())
        if value["runtime"] != str(path.resolve()):
            raise RuntimeError("Reviewer state belongs to a different runtime directory")
    else:
        value = {"owner": secrets.token_hex(24), "runtime": str(path.resolve()), "version": "reviewer005"}
        private_json(identity, value)
    return value


def resource_names(runtime: Path):
    suffix = hashlib.sha256(str(runtime.resolve()).encode()).hexdigest()[:10]
    return {kind: f"kairos-reviewer005-{kind}-{suffix}" for kind in ("postgres", "keycloak", "pgdata", "kcdata")}


def docker_inspect(kind, name):
    result = subprocess.run(["docker", kind, "inspect", name], capture_output=True, text=True)
    if result.returncode:
        return None
    return json.loads(result.stdout)[0]


def require_owned_resource(value, owner, kind):
    labels = value.get("Labels") if kind == "volume" else value.get("Config", {}).get("Labels")
    if not labels or labels.get(LABEL) != owner:
        raise RuntimeError("Conflicting Docker resource belongs to another owner; it was preserved")


def stop(runtime: Path):
    if not (runtime / "owner.json").exists():
        return {"processes_stopped": 0, "containers_stopped": 0, "volumes_preserved": True}
    if (runtime / "owner.json").is_symlink():
        raise RuntimeError("Reviewer owner identity must not be a symlink")
    owner = ensure_runtime(runtime)["owner"]
    if not isinstance(owner, str) or not owner:
        raise RuntimeError("Reviewer owner identity is invalid")
    stopped = 0
    errors = []
    def attempt(scope, operation):
        try: return operation()
        except Exception as error:
            errors.append((scope, error)); return None
    state = runtime / "state.json"
    def read_process_state():
        if state.is_symlink(): raise RuntimeError("Process state must not be a symlink")
        value = json.loads(state.read_text())
        if value.get("owner") != owner:
            raise RuntimeError("Process state owner mismatch")
        return value
    value = attempt("Process state", read_process_state) if state.exists() else None
    if value is not None:
        supervisor = value.get("supervisor")
        def stop_supervisor():
            return terminate_owned(supervisor) if supervisor["pid"] != os.getpid() else False
        if supervisor: stopped += int(bool(attempt("Supervisor", stop_supervisor)))
        processes = value.get("processes", [])
        if not isinstance(processes, list):
            errors.append(("Process state", RuntimeError("Owned process list is invalid")))
        else:
            for process in reversed(processes):
                stopped += int(bool(attempt("Owned process", lambda process=process: terminate_owned(process))))
    containers = 0
    for kind in ("keycloak", "postgres"):
        name = resource_names(runtime)[kind]
        def stop_container():
            try: item = docker_inspect("container", name)
            except FileNotFoundError: return False
            if item:
                require_owned_resource(item, owner, "container")
                if item["State"]["Running"]:
                    subprocess.run(["docker", "stop", "--time", "15", name], capture_output=True, check=True)
                    return True
            return False
        containers += int(bool(attempt("Owned " + kind + " container", stop_container)))
    if errors:
        details = "; ".join(scope + ": " + type(error).__name__ + ": " + str(error)
                            for scope, error in errors)
        raise RuntimeError("Reviewer stop encountered errors after independent owned-container cleanup: " + details)
    return {"processes_stopped": stopped, "containers_stopped": containers, "volumes_preserved": True}
