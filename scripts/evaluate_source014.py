"""Separate held-out evaluator for the frozen source-matching014 pilot.

This consumes a development-selected inference-only JSON head. It cannot load
optimizer state, fit parameters, select checkpoints or update training results.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
from pathlib import Path
import random

import torch
from torch.nn import functional as F

if importlib.util.find_spec("scripts.retrieval_adapter014"):
    from scripts import retrieval_adapter014 as adapter
else:
    import retrieval_adapter014 as adapter

BOOTSTRAP = {"seed": 1401401, "replicates": 2000, "confidence": 0.95,
             "unit": "paired query/function within the single held-out repository",
             "limitation": "Conditional descriptive intervals; functions are related and repository-level generalization is not estimated."}


def load_holdout(data_directory, expected_frozen_sha256):
    """Delegate private admission to the separate evaluator-owned source module."""
    try:
        from scripts.evaluate_functions014 import load_for_evaluation014
    except ModuleNotFoundError as error:
        if error.name != "scripts.evaluate_functions014":
            raise
        from evaluate_functions014 import load_for_evaluation014
    rows, identity = load_for_evaluation014(data_directory, expected_frozen_sha256)
    adapter.require(identity["evaluation_only"] is True and identity["split"] == "holdout",
                    "held-out admission must be evaluator-only")
    return sorted(rows, key=lambda row: row["example_id"]), identity


def load_holdout_cache(path, expected_sha256, rows, identity, expected_encoder):
    raw = adapter.read_bytes(path)
    adapter.require(adapter.is_hash(expected_sha256) and adapter.sha(raw) == expected_sha256, "held-out cache hash mismatch")
    cache = adapter.json_bytes(raw)
    adapter.require(set(cache) == {"schema_version", "frozen_sha256", "encoder", "rows"}
                    and cache["schema_version"] == adapter.CACHE_VERSION
                    and cache["frozen_sha256"] == identity["frozen_sha256"], "held-out cache identity mismatch")
    encoder = cache["encoder"]
    adapter.require(encoder == expected_encoder and set(encoder) == set(adapter.ENCODER) | {"profile_sha256"}
                    and all(encoder[key] == value for key, value in adapter.ENCODER.items())
                    and adapter.is_hash(encoder["profile_sha256"]), "held-out encoder differs from selected adapter")
    originals, vectors = {row["example_id"]: row for row in rows}, {}
    for row in cache["rows"]:
        adapter.require(set(row) == {"example_id", "query_sha256", "code_sha256", "query", "code"}, "held-out cache row fields mismatch")
        name = row["example_id"]
        adapter.require(name in originals and name not in vectors, "unknown or duplicate held-out embedding")
        adapter.require(all(row[field + "_sha256"] == originals[name][field + "_sha256"] for field in ("query", "code")),
                        "held-out cache text hash mismatch")
        values = []
        for field in ("query", "code"):
            vector = row[field]
            adapter.require(type(vector) is list and len(vector) == encoder["dimension"]
                            and all(type(value) in (int, float) and math.isfinite(value) for value in vector), "invalid held-out vector")
            tensor = torch.tensor(vector, dtype=torch.float32)
            norm = float(torch.linalg.vector_norm(tensor))
            adapter.require(torch.isfinite(tensor).all().item() and 0.99 <= norm <= 1.01, "held-out vector not normalized")
            values.append(F.normalize(tensor, dim=0))
        vectors[name] = tuple(values)
    adapter.require(set(vectors) == set(originals), "held-out cache must cover exact sealed rows")
    return vectors


def paired_intervals(paired):
    generator = random.Random(BOOTSTRAP["seed"])
    keys = tuple(paired[0]["delta"])
    samples = {key: [] for key in keys}
    for _ in range(BOOTSTRAP["replicates"]):
        indices = [generator.randrange(len(paired)) for _ in paired]
        for key in keys:
            samples[key].append(sum(paired[index]["delta"][key] for index in indices) / len(indices))
    result = {}
    for key, values in samples.items():
        values.sort()
        result[key] = {"lower": values[int((len(values) - 1) * 0.025)],
                       "upper": values[int((len(values) - 1) * 0.975)]}
    return {**BOOTSTRAP, "method": "percentile bootstrap of paired macro-mean differences", "delta_intervals": result}


@torch.no_grad()
def score_holdout(rows, vectors, model, *, device="cpu"):
    """Rank each structural target among every sealed held-out function."""
    rows = sorted(rows, key=lambda row: row["example_id"])
    queries = torch.stack([vectors[row["example_id"]][0] for row in rows]).to(device)
    codes = torch.stack([vectors[row["example_id"]][1] for row in rows]).to(device)
    scores = {"base": (queries @ codes.T).cpu(), "adapter": (model(queries) @ model(codes).T).cpu()}
    paired = []
    for target, row in enumerate(rows):
        record = {"example_id": row["example_id"], "repository": row["repository"]}
        for arm, matrix in scores.items():
            order = sorted(range(len(rows)), key=lambda index: (-float(matrix[target, index]), rows[index]["example_id"]))
            rank = order.index(target) + 1
            record[arm] = {"rank": rank, "mrr": 1 / rank, **{f"recall@{k}": float(rank <= k) for k in adapter.PROTOCOL["recall_k"]}}
        record["delta"] = {key: record["adapter"][key] - record["base"][key] for key in record["base"] if key != "rank"}
        paired.append(record)
    summary = {arm: {key: sum(row[arm][key] for row in paired) / len(paired)
                     for key in paired[0]["delta"]} for arm in ("base", "adapter", "delta")}
    return {"queries": len(rows), "candidates_per_query": len(rows), "summary": summary, "paired": paired,
            "mrr_comparison": {"improved": sum(row["delta"]["mrr"] > 0 for row in paired),
                               "unchanged": sum(row["delta"]["mrr"] == 0 for row in paired),
                               "regressed": sum(row["delta"]["mrr"] < 0 for row in paired)},
            "uncertainty": paired_intervals(paired)}


def evaluate_source_holdout(data_directory, expected_frozen_sha256, cache_path, expected_cache_sha256,
                            inference_directory, expected_inference_manifest_sha256, *, device="cpu"):
    rows, identity = load_holdout(data_directory, expected_frozen_sha256)
    model, exported = adapter.load_inference_projection(inference_directory, expected_inference_manifest_sha256, device=device)
    adapter.require(exported["manifest"]["data_kind"] == "source-only-docstring-retrieval-pilot"
                    and exported["manifest"]["frozen_sha256"] == identity["frozen_sha256"], "selected adapter data identity mismatch")
    vectors = load_holdout_cache(cache_path, expected_cache_sha256, rows, identity, exported["config"]["encoder"])
    return {"schema_version": "kairos-source-holdout-evaluation014-v1", "data_kind": identity["data_kind"],
            "frozen_sha256": identity["frozen_sha256"], "cache_sha256": expected_cache_sha256,
            "inference_manifest_sha256": expected_inference_manifest_sha256,
            "selected_step": exported["config"]["selected_step"],
            "evaluator_implementation_sha256": adapter.sha(Path(__file__).read_bytes()),
            "encoder": exported["config"]["encoder"],
            "scope": "Source-only docstring-to-own-function matching in one held-out repository. Other functions are unjudged contrastive candidates.",
            "selection": "Adapter selected using development only before this evaluator loads held-out rows.",
            "limitations": ["No independent semantic relevance labels, issue-family claims, repair outcomes, or official benchmark score.",
                            "Potential pretrained encoder contamination is unknown; related functions limit query-bootstrap inference."],
            **score_holdout(rows, vectors, model, device=device)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data", "cache", "adapter", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("frozen", "cache", "adapter-manifest"):
        parser.add_argument("--" + name + "-sha256", required=True)
    args = parser.parse_args()
    try:
        adapter.require(not args.output.exists() and not args.output.is_symlink(), "evaluation output must be new")
        report = evaluate_source_holdout(args.data, args.frozen_sha256, args.cache, args.cache_sha256,
                                         args.adapter, args.adapter_manifest_sha256)
        args.output.write_bytes(adapter.canonical(report) + b"\n")
        print(adapter.canonical({"queries": report["queries"], "summary": report["summary"]}).decode())
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"Rejected: {error}\n")


if __name__ == "__main__":
    main()
