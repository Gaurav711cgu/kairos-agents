"""Evaluator-owned holdout admission; never import this module from a trainer."""
from __future__ import annotations
import ast
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import build_functions014 as protocol
except ImportError:
    import build_functions014 as protocol


def load_for_evaluation014(data_dir, expected_frozen_sha256):
    """Verify the trusted freeze and private receipt chain, then return holdout only.

    This function reads the private evaluator store. It must never be called by
    model-fitting code. It does not fit, encode, or run source code.
    """
    data_dir = Path(data_dir)
    # Reuse public review, fixed repository split, license and allowlist admission.
    train, development, identity = protocol.load_for_training014(data_dir, expected_frozen_sha256)
    frozen = protocol.load(data_dir / "frozen.json")
    private_manifest = protocol.load(data_dir / "manifest.private.json")
    if protocol.sha(protocol.canonical(private_manifest)) != frozen["private_manifest_sha256"]:
        raise ValueError("Frozen private manifest hash mismatch")
    if private_manifest["implementation_sha256"] != protocol.sha(Path(protocol.__file__).read_bytes()):
        raise ValueError("Frozen source preparation implementation drift")
    if private_manifest["source_only_training_data_ready"] is not True or private_manifest["original013_issue_family_training_data_ready"] is not False or private_manifest["function_counts"] != frozen["function_counts"]:
        raise ValueError("Private source-only gate drift")
    for name, expected in private_manifest["files"].items():
        parts = PurePosixPath(name).parts
        if PurePosixPath(name).is_absolute() or any(part in {".", ".."} or not part for part in parts):
            raise ValueError("Unsafe private receipt path")
        path = data_dir / name
        if path.is_symlink() or any((data_dir.joinpath(*parts[:i])).is_symlink() for i in range(1, len(parts))) or not path.is_file() or path.stat().st_size > protocol.MAX_BYTES:
            raise ValueError("Unsafe private evaluator file")
        value = path.read_bytes()
        if len(value) != expected["bytes"] or protocol.sha(value) != expected["sha256"]:
            raise ValueError("Private evaluator file hash mismatch")
    path = data_dir / "evaluation-private/holdout.jsonl"
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    if len(rows) != frozen["function_counts"]["holdout"]:
        raise ValueError("Holdout count drift")
    for row in rows:
        config = frozen["repositories"].get(row["repository"])
        if row["split"] != "holdout" or not config or config["split"] != "holdout" or row["source_commit"] != config["revision"] or row["schema_version"] != protocol.VERSION or row["derivation"] != protocol.DERIVATION:
            raise ValueError("Heldout source identity drift")
        if protocol.sha(protocol.canonical({k: v for k, v in row.items() if k != "example_id"})) != row["example_id"] or protocol.sha(row["query"]) != row["query_sha256"] or protocol.sha(row["code"]) != row["code_sha256"]:
            raise ValueError("Heldout row content hash mismatch")
        if protocol.SECRET.search(row["query"] + row["code"]):
            raise ValueError("Private path or credential pattern in evaluator input")
        ast.parse(row["code"])
    rights = protocol.load(data_dir / "rights.private.json")
    right = rights["pallets/click"]
    if right["spdx"] != "BSD-3-Clause" or not right["training_allowed"] or not right["redistribution_allowed"] or protocol.sha(right["notice"]) != right["evidence_sha256"] or right["revision"] != frozen["repositories"]["pallets/click"]["revision"]:
        raise ValueError("Holdout license evidence invalid")
    all_rows = train + development + rows
    if len({row["example_id"] for row in all_rows}) != len(all_rows) or protocol.deduplicate(all_rows)[1]["removed"]:
        raise ValueError("Holdout duplicate contamination")
    return rows, {**identity, "split": "holdout", "private_manifest_sha256": frozen["private_manifest_sha256"], "holdout_rows_sha256": protocol.sha(path.read_bytes()), "evaluation_only": True}
