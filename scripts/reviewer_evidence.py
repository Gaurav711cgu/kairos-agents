"""Validate genuine published capture bundles without importing application dependencies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

TERMINAL = {"completed", "failed", "cancelled", "unknown", "timed_out"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_bytes(root: Path, metadata: dict) -> bytes:
    relative = Path(metadata["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Evidence path escapes package")
    target = root / relative
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Evidence object missing or outside package")
    data = target.read_bytes()
    if len(data) != metadata["bytes"] or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
        raise ValueError("Evidence object digest or size mismatch")
    return data


def validate_package(root: Path) -> tuple[dict, dict]:
    """Check every byte, snapshot digest, ordered step and capture reference before import."""
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_bytes())
    if manifest.get("version") != "published-evidence-v1":
        raise ValueError("Unsupported evidence package version")
    blobs = {}
    for key, metadata in manifest["blobs"].items():
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key) or metadata["sha256"] != key:
            raise ValueError("Invalid content-addressed object key")
        blobs[key] = file_bytes(root, metadata)
    records = {}
    for identifier, metadata in manifest["records"].items():
        if str(UUID(identifier)) != identifier:
            raise ValueError("Invalid investigation identifier")
        record = json.loads(file_bytes(root, metadata))
        if record["id"] != identifier or record["status"] not in TERMINAL or record["published"] is not True:
            raise ValueError("Only terminal published investigations may be imported")
        if record.get("integrity", {}).get("verified") is not True:
            raise ValueError("Unverified investigation cannot be imported")
        version = record.get("registry_version", "repository-cases-v1")
        if digest({"case": record["task_snapshot"], "registry_version": version}) != record["task_digest"]:
            raise ValueError("Case snapshot digest mismatch")
        if digest(record["config_snapshot"]) != record["config_digest"]:
            raise ValueError("Configuration snapshot digest mismatch")
        references = {item["sha256"]: item["bytes"] for item in record["artifacts"]}
        for key, size in references.items():
            if key not in blobs or len(blobs[key]) != size:
                raise ValueError("Investigation artifact reference missing or wrong size")
        for sequence, step in enumerate(record["steps"], 1):
            if step["seq"] != sequence or step["investigation_id"] != identifier:
                raise ValueError("Investigation steps are not contiguous and ordered")
            if step["state"] not in {"pending", "captured"} or step["kind"] not in {"context", "model", "tool"}:
                raise ValueError("Invalid captured step state")
            if step["state"] == "captured" and step["result"] is None:
                raise ValueError("Captured step lacks result")
            if step["state"] == "pending" and step["result"] is not None:
                raise ValueError("Pending step contains a result")
            for field in ("request", "result"):
                capture = step[field]
                if capture is None:
                    continue
                key = capture["sha256"]
                if key not in references or key not in blobs:
                    raise ValueError("Captured step references an undeclared object")
                if digest(capture["body"]) != key or json.loads(blobs[key]) != capture["body"]:
                    raise ValueError("Captured body differs from original artifact bytes")
        records[identifier] = record
    if not records:
        raise ValueError("Evidence package contains no investigations")
    return records, blobs
