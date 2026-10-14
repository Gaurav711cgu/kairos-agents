"""Boundary checks use isolated fixtures, never published model evidence."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.reviewer_evidence import canonical, digest, validate_package


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "evidence"; (root / "records").mkdir(parents=True); (root / "blobs").mkdir()
    identifier = str(uuid4()); body = {"fixture": "original capture"}; key = digest(body)
    (root / "blobs" / key).write_bytes(canonical(body))
    case = {"id": "fixture"}; config = {"version": "fixture"}
    record = {"id": identifier, "status": "completed", "published": True, "integrity": {"verified": True},
        "task_snapshot": case, "task_digest": digest({"case": case, "registry_version": "repository-cases-v1"}),
        "config_snapshot": config, "config_digest": digest(config), "artifacts": [{"sha256": key, "bytes": len(canonical(body))}],
        "steps": [{"investigation_id": identifier, "seq": 1, "kind": "tool", "name": "fixture", "state": "captured",
            "request": {"sha256": key, "body": body}, "result": {"sha256": key, "body": body}}]}
    path = root / "records" / (identifier + ".json"); path.write_bytes(canonical(record))
    manifest = {"version": "published-evidence-v1", "records": {identifier: {"path": "records/" + identifier + ".json",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}},
        "blobs": {key: {"path": "blobs/" + key, "sha256": key, "bytes": len(canonical(body))}}}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root, identifier, key, record, manifest


def write_record(root, identifier, record, manifest):
    path = root / "records" / (identifier + ".json"); path.write_bytes(canonical(record))
    manifest["records"][identifier].update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
    (root / "manifest.json").write_text(json.dumps(manifest))


def test_valid_package_preserves_original_bytes(package):
    root, identifier, key, record, _ = package
    records, blobs = validate_package(root)
    assert records[identifier] == record
    assert blobs[key] == canonical(record["steps"][0]["request"]["body"])


@pytest.mark.parametrize("mutation", ["byte_corruption", "missing_object", "escaped_path", "symlink_escape"])
def test_artifact_integrity_and_path_boundaries(package, mutation, tmp_path):
    root, _, key, _, manifest = package; path = root / "blobs" / key
    if mutation == "byte_corruption": path.write_bytes(b"corrupt")
    elif mutation == "missing_object": path.unlink()
    elif mutation == "escaped_path":
        manifest["blobs"][key]["path"] = "../private.txt"
        (root / "manifest.json").write_text(json.dumps(manifest))
    else:
        outside = tmp_path / "private.txt"; outside.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(outside)
    with pytest.raises(ValueError): validate_package(root)


@pytest.mark.parametrize("mutation", ["sequence", "snapshot", "capture", "private", "active", "missing_result"])
def test_semantic_tampering_fails_even_with_updated_file_hash(package, mutation):
    root, identifier, _, record, manifest = package
    if mutation == "sequence": record["steps"][0]["seq"] = 2
    elif mutation == "snapshot": record["config_snapshot"]["version"] = "changed"
    elif mutation == "capture": record["steps"][0]["request"]["body"] = {"fixture": "replacement"}
    elif mutation == "private": record["published"] = False
    elif mutation == "active": record["status"] = "running"
    else: record["steps"][0]["result"] = None
    write_record(root, identifier, record, manifest)
    with pytest.raises(ValueError): validate_package(root)


def test_pending_unknown_dispatch_is_preserved_without_a_result(package):
    root, identifier, _, record, manifest = package
    record["status"] = "unknown"; step = record["steps"][0]; step.update(kind="model", state="pending", result=None)
    write_record(root, identifier, record, manifest)
    assert validate_package(root)[0][identifier]["steps"][0]["result"] is None
