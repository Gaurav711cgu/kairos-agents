"""Exposure-aware selection and descriptive retrieval evaluation, without inference.

Reference-derived labels belong only to a private offline scorer. They are proxy
labels for maintainer localization, not proof that another repair is incorrect.
The CLI starts no model, database, container or network request.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re

VERSION = "retrieval-study011-v1"
MAX_INPUT = 64 * 1024**2
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,179}\Z")
OUTCOMES = {"verified_repair", "failed_checks", "invalid_patch", "invalid_response",
            "environment_failure", "timeout", "no_patch", "unknown_dispatch",
            "cancelled", "unattempted"}
PROXY = ("Reference changed-source paths and original-line ranges are localization "
         "proxies. They neither define every valid repair nor establish repair effectiveness.")


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode()


def fingerprint(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Input must be an ordinary file")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT:
        raise ValueError("Input exceeds its size limit")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def load(path):
    path = Path(path)
    fingerprint(path)
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = item
        return result
    def constant(_):
        raise ValueError("Non-finite JSON number")
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=constant)


def save(path, value, *, private=False):
    """Never overwrite a frozen artifact with different bytes."""
    path = Path(path)
    raw = canonical(value)
    if path.is_symlink():
        raise ValueError("Output cannot be a symbolic link")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Frozen output differs; use a new study identity")
        if private and path.stat().st_mode & 0o077:
            raise ValueError("Private scorer material must have mode 0600")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def rows(value, key):
    result = value.get(key) if isinstance(value, dict) else value
    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
        raise ValueError("Expected an explicit list of " + key)
    return result


def issue_digest(issue):
    return hashlib.sha256(" ".join(str(issue).lower().split()).encode()).hexdigest()


def exposure_inventory(history_root):
    """Inspect only declared public evidence paths, never private runtime/auth."""
    root = Path(history_root).resolve(strict=True)
    records_root = root / "dashboard/evidence/records"
    if not records_root.is_dir():
        raise ValueError("Historical public records are unavailable")
    records = [load(path) for path in sorted(records_root.glob("*.json"))]
    if not records:
        raise ValueError("Historical public record collection is empty")
    ledger = defaultdict(set)
    issue_hashes = set()

    def add(identifier, reason, issue=None):
        if not isinstance(identifier, str) or not ID.fullmatch(identifier):
            raise ValueError("Invalid historical task identifier")
        ledger[identifier].add(reason)
        if isinstance(issue, str) and issue.strip():
            issue_hashes.add(issue_digest(issue))

    for record in records:
        add(record["task_id"], "Published investigation", record.get("task_snapshot", {}).get("issue"))
    for path in sorted((root / "cases").glob("*.json")):
        value = load(path)
        for case in value.get("cases", value.get("records", [])):
            add(case.get("id") or case.get("instance_id"), "Historical registration or source provenance",
                case.get("issue") or case.get("problem_statement"))
    for relative in ("evidence/build004/qualification", "evidence/build006/qualification",
                     "evidence/build007/qualification"):
        for path in sorted((root / relative).glob("*.json")):
            value = load(path)
            case = value.get("case", {})
            add(value.get("id", path.stem), "Historical qualification, including exclusions",
                case.get("issue"))
    registry = root / "evidence/build007/registry.json"
    if registry.exists():
        for case in load(registry).get("cases", []):
            add(case["id"], "Frozen build007 registration", case.get("issue"))
    followup = root / "evidence/repair010/attempts.json"
    followup_rows = rows(load(followup), "attempts") if followup.exists() else []
    for attempt in followup_rows:
        add(attempt["case"], "Exposed repair010 development diagnostic")

    successes = [record for record in records if record.get("outcome") == "verified_repair"]
    positive_patches = defaultdict(set)
    for record in successes:
        for step in record.get("steps", []):
            result = (step.get("result") or {}).get("body", {})
            if step.get("name") == "propose_patch" and not result.get("error") and isinstance(result.get("patch"), str):
                positive_patches[record["task_id"]].add(hashlib.sha256(result["patch"].encode()).hexdigest())
    audit = {
        "public_records": len(records), "unique_record_tasks": len({r["task_id"] for r in records}),
        "record_outcomes": dict(sorted(Counter(r.get("outcome", "unreported") for r in records).items())),
        "record_model_calls": sum(r.get("model_calls", 0) for r in records),
        "verified_trajectories": len(successes),
        "verified_unique_tasks": len({r["task_id"] for r in successes}),
        "verified_unique_rendered_patches": sum(len(patches) for patches in positive_patches.values()),
        "verified_patch_counts_by_task": {task: len(patches) for task, patches in sorted(positive_patches.items())},
        "followup010_attempts": len(followup_rows),
        "training_data_ready": False,
        "training_use": ("An exposure/error-regression corpus, not one independent positive example per record. "
                         "Do not train failed patches as successful repairs. Group by issue and revision, "
                         "deduplicate patch bytes, and retain all failed/unknown outcomes. "
                         "Post-hoc checks are separate from original investigation outcomes."),
    }
    return {"version": VERSION, "scope": "Audited public history only; public model-training contamination remains unknown",
            "audit": audit, "exposed_task_count": len(ledger),
            "exposures": [{"instance_id": identifier, "reasons": sorted(reasons)}
                          for identifier, reasons in sorted(ledger.items())],
            "exposed_issue_digests": sorted(issue_hashes)}


def dataset_rows(path):
    values = rows(load(path), "records")
    identifiers = set()
    for value in values:
        identifier = value.get("instance_id")
        if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in identifiers:
            raise ValueError("Dataset IDs must be valid and unique")
        identifiers.add(identifier)
        if not all(isinstance(value.get(key), str) and value[key].strip()
                   for key in ("repo", "base_commit", "problem_statement")):
            raise ValueError("Dataset requires repository, base commit and issue text")
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value["repo"]) or
                not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", value["base_commit"])):
            raise ValueError("Dataset repository and source revision must be canonical")
    return values


def safe_source_path(name):
    if not isinstance(name, str):
        raise ValueError("Invalid source localization path")
    path = PurePosixPath(name)
    if (not name or "\\" in name or path.is_absolute() or
            path.as_posix() != name or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Invalid source localization path")
    return path


def private_labels(patch):
    """Keep only Python source localization proxies, never the repair text."""
    if not isinstance(patch, str) or not patch.strip():
        raise ValueError("Private scoring requires an actual captured reference patch")
    files = set()
    regions = set()
    name = None
    line = 0
    removed_anchor = None
    for raw in patch.splitlines():
        if raw.startswith("+++ "):
            candidate = raw[4:]
            if candidate == "/dev/null":
                continue
            if not candidate.startswith("b/"):
                raise ValueError("Reference diff is not a canonical source patch")
            candidate = candidate[2:]
            path = safe_source_path(candidate)
            name = candidate if (path.suffix == ".py" and not any(
                part in {"test", "tests", "testing"} or part.startswith("test_") for part in path.parts)) else None
            if name:
                files.add(name)
            continue
        if raw.startswith("--- a/"):
            # Deletions keep their original source path if +++ is /dev/null.
            candidate = raw[6:]
            path = safe_source_path(candidate)
            name = candidate if path.suffix == ".py" and not any(
                part in {"test", "tests", "testing"} or part.startswith("test_") for part in path.parts) else None
            continue
        match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", raw)
        if match:
            line = int(match[1])
            removed_anchor = None
            if name:
                files.add(name)
            continue
        if not name or not line:
            continue
        if raw.startswith("-"):
            removed_anchor = line
            regions.add((name, line, line)); line += 1
        elif raw.startswith("+"):
            anchor = removed_anchor if removed_anchor is not None else max(1, line)
            regions.add((name, anchor, anchor))
        elif raw.startswith(" "):
            line += 1
            removed_anchor = None
    combined = []
    for name, start, end in sorted(regions):
        if combined and combined[-1]["path"] == name and combined[-1]["end_line"] + 1 == start:
            combined[-1]["end_line"] = end
        else:
            combined.append({"path": name, "start_line": start, "end_line": end})
    return {"changed_files": sorted(files),
            "original_regions": combined}


def select(dataset, history_root, count, development_count, seed, repositories=(), retrospective=False):
    if type(count) is not int or not 1 <= count <= 300 or not 0 <= development_count < count:
        raise ValueError("Select 1–300 candidates and fewer development than total candidates")
    if retrospective and development_count:
        raise ValueError("Retrospective exposed cases cannot be labeled development or holdout")
    data = dataset_rows(dataset)
    inventory = exposure_inventory(history_root)
    exposed = {item["instance_id"] for item in inventory["exposures"]}
    known_issues = set(inventory["exposed_issue_digests"])
    candidates, exclusions, issues = [], [], set()
    for row in sorted(data, key=lambda value: value["instance_id"]):
        identifier = row["instance_id"]
        digest = issue_digest(row["problem_statement"])
        reason = ("Not an exposed retrospective task" if retrospective and identifier not in exposed else
                  "Historical task exposure" if not retrospective and identifier in exposed else
                  "Issue text duplicates historical exposure" if not retrospective and digest in known_issues else
                  "Outside the preregistered repository set" if repositories and row["repo"] not in repositories else
                  "Duplicate issue text inside candidate dataset" if digest in issues else None)
        if reason:
            exclusions.append({"instance_id": identifier, "reason": reason})
        else:
            candidates.append(row); issues.add(digest)
    if len(candidates) < count:
        raise ValueError("Insufficient unexposed candidates; qualification or success must not choose replacements")
    # Hash ordering is stable across Python versions and independent of dataset order.
    ranked = sorted(candidates, key=lambda value: hashlib.sha256(
        (str(seed) + "\0" + value["instance_id"]).encode()).hexdigest())
    chosen = ranked[:count]
    public_cases = [{"instance_id": value["instance_id"], "repository": value["repo"],
                     "base_commit": value["base_commit"], "issue": value["problem_statement"],
                     "split": "retrospective" if retrospective else
                         "development" if index < development_count else "holdout"}
                    for index, value in enumerate(chosen)]
    public = {"version": VERSION, "dataset": fingerprint(dataset),
              "exposure_ledger_sha256": hashlib.sha256(canonical(inventory)).hexdigest(),
              "seed": str(seed), "repositories": sorted(repositories), "candidates": public_cases,
              "candidate_pool": [row["instance_id"] for row in ranked], "exclusions": exclusions,
              "mode": "exposed-retrospective" if retrospective else "prospective-selection",
              "candidate_counts_by_repository": dict(sorted(Counter(row["repo"] for row in ranked).items())),
              "status": "Frozen candidate selection; cases are not yet independently qualified",
              "scope": ("Already exposed historical cases; retrospective retrieval diagnostics only. No fresh evaluation claim."
                        if retrospective else "New to this study's audited history, not proven unseen in model training. No inference performed.")}
    gold = {"version": VERSION, "dataset": fingerprint(dataset), "proxy_limit": PROXY,
            "instances": {row["instance_id"]: private_labels(row.get("patch", "")) for row in chosen}}
    return public, gold


def select_to_files(args):
    public_path, gold_path = Path(args.output).resolve(), Path(args.private_gold).resolve()
    if gold_path.is_relative_to(public_path.parent):
        raise ValueError("Private gold must be outside the public manifest directory")
    public, gold = select(args.dataset, args.history_root, args.count, args.development_count,
                          args.seed, args.repository, getattr(args, "retrospective", False))
    save(gold_path, gold, private=True)
    save(public_path, public)
    return {"selected": len(public["candidates"]), "qualification_performed": False,
            "inference_calls": 0, "private_labels_published": False}


def freeze(cohort, profile, retrieval, budgets, sources, output):
    if not sources:
        raise ValueError("Freeze requires explicit logical source names and paths")
    names = {}
    for name, path in sources:
        safe_source_path(name)
        if name in names:
            raise ValueError("Duplicate frozen source name")
        names[name] = fingerprint(path)
    for config in (profile, retrieval, budgets, cohort):
        if not isinstance(load(config), dict):
            raise ValueError("Frozen configuration must be a JSON object")
    value = {"version": VERSION, "sources": names, "cohort": fingerprint(cohort),
             "evaluation_source": fingerprint(Path(__file__)),
             "profile": fingerprint(profile), "retrieval": fingerprint(retrieval),
             "budgets": fingerprint(budgets),
             "scope": "Content freeze only; no model execution or claim that qualification passed"}
    save(output, value)
    return value


def ranked_rows(path):
    path = Path(path)
    if path.suffix == ".jsonl":
        fingerprint(path)
        values = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    else:
        value = load(path)
        values = rows(value, "results")
    index = {}
    for value in values:
        identifier = value.get("instance_id")
        if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in index:
            raise ValueError("Ranked results require valid, unique instance IDs")
        index[identifier] = value
    return index


def case_metrics(regions, gold):
    if not isinstance(regions, list):
        raise ValueError("Completed ranking requires an actual region list")
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError("Ranked region must be an object")
        safe_source_path(region.get("path"))
        if (type(region.get("start_line")) is not int or type(region.get("end_line")) is not int or
                not 1 <= region["start_line"] <= region["end_line"] <= 10_000_000):
            raise ValueError("Ranked source range is invalid")
    changed = set(gold["changed_files"])
    if not changed:
        return None
    result = {"mrr": next((1 / rank for rank, region in enumerate(regions, 1)
                            if region["path"] in changed), 0.0)}
    original = gold["original_regions"]
    for cutoff in (1, 5, 10):
        selected = regions[:cutoff]
        paths = {region["path"] for region in selected}
        result[f"file_recall_at_{cutoff}"] = len(paths & changed) / len(changed)
        result[f"file_hit_at_{cutoff}"] = float(bool(paths & changed))
        covered = sum(any(region["path"] == target["path"] and
                          region["start_line"] <= target["start_line"] and
                          region["end_line"] >= target["end_line"] for region in selected)
                      for target in original)
        result[f"whole_changed_region_recall_at_{cutoff}"] = covered / len(original) if original else None
        result[f"whole_changed_region_hit_at_{cutoff}"] = float(covered > 0) if original else None
    return result


def summarize(index, gold):
    if not set(index).issubset(gold):
        raise ValueError("Ranked output contains cases outside the private frozen cohort")
    metrics, outcomes = {}, Counter()
    for identifier in gold:
        row = index.get(identifier)
        status = row.get("status", "completed") if row else "unattempted"
        if status not in {"completed", "environment_failure", "unattempted", "timeout", "unknown"}:
            raise ValueError("Unsupported retrieval outcome")
        outcomes[status] += 1
        if status != "completed":
            continue
        item = case_metrics(row.get("regions", row.get("ranked_regions")), gold[identifier])
        if item is not None:
            metrics[identifier] = item
        else:
            outcomes["no_source_proxy_labels"] += 1
    keys = next(iter(metrics.values()), {}).keys()
    means = {key: sum(row[key] for row in metrics.values() if row[key] is not None) /
             sum(row[key] is not None for row in metrics.values())
             if any(row[key] is not None for row in metrics.values()) else None for key in keys}
    return {"cohort_cases": len(gold), "scored_cases": len(metrics),
            "outcomes": dict(sorted(outcomes.items())), "means": means, "per_case": metrics}


def paired_bootstrap(left, right, repetitions=2000, seed="011"):
    if not 100 <= repetitions <= 10_000:
        raise ValueError("Bootstrap repetitions must be between 100 and 10000")
    common = sorted(set(left) & set(right))
    if not common:
        return {"paired_cases": 0, "differences": {}, "scope": "No completed paired cases"}
    generator = random.Random(str(seed))
    keys = next(iter(left.values())).keys()
    differences = {}
    for key in keys:
        values = [right[identifier][key] - left[identifier][key] for identifier in common
                  if left[identifier][key] is not None and right[identifier][key] is not None]
        if not values:
            continue
        estimates = sorted(sum(generator.choice(values) for _ in values) / len(values)
                           for _ in range(repetitions))
        differences[key] = {"mean_difference": sum(values) / len(values), "paired_cases": len(values),
                            "percentile_95_interval": [estimates[math.floor(.025 * (repetitions - 1))],
                                                       estimates[math.ceil(.975 * (repetitions - 1))]]}
    return {"paired_cases": len(common), "repetitions": repetitions, "seed": str(seed),
            "differences": differences,
            "scope": "Descriptive issue-paired bootstrap; small samples do not establish superiority or a release gate"}


def score(private_gold, ranked, comparison=None, repetitions=2000, seed="011"):
    gold = load(private_gold)
    if gold.get("version") != VERSION or not isinstance(gold.get("instances"), dict):
        raise ValueError("Unsupported private localization labels")
    first = summarize(ranked_rows(ranked), gold["instances"])
    result = {"version": VERSION, "proxy_limit": PROXY, "primary": first,
              "denominator": "Means use completed cases with source labels; all missing and infrastructure outcomes remain counted separately"}
    if comparison:
        second = summarize(ranked_rows(comparison), gold["instances"])
        result["comparison"] = second
        result["paired_difference"] = paired_bootstrap(first["per_case"], second["per_case"], repetitions, seed)
    return result


def export_predictions(attempts_path, output, model_name, dataset=None, strategy=None):
    if not isinstance(model_name, str) or not model_name.strip() or len(model_name) > 300:
        raise ValueError("An explicit model/configuration identity is required")
    attempts = rows(load(attempts_path), "attempts")
    if strategy:
        attempts = [row for row in attempts if row.get("configuration", row.get("strategy")) == strategy]
    expected = {row["instance_id"] for row in dataset_rows(dataset)} if dataset else None
    predictions, ledger, identifiers = [], [], set()
    for row in attempts:
        identifier = row.get("instance_id", row.get("task_id", row.get("case")))
        outcome = row.get("outcome")
        if (not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in identifiers or
                outcome not in OUTCOMES or (expected is not None and identifier not in expected)):
            raise ValueError("Attempt identities/outcomes must be unique and belong to the selected dataset")
        identifiers.add(identifier)
        patch = row.get("model_patch", row.get("patch", ""))
        if not isinstance(patch, str) or len(patch.encode()) > 1024**2:
            raise ValueError("Model patch must be captured, bounded text")
        if outcome == "verified_repair" and not patch:
            raise ValueError("Verified outcome has no captured patch; do not invent predictions")
        included = outcome != "unattempted"
        if included:
            predictions.append({"instance_id": identifier, "model_name_or_path": model_name, "model_patch": patch})
        ledger.append({"instance_id": identifier, "outcome": outcome, "prediction_included": included})
    if expected is not None:
        ledger.extend({"instance_id": identifier, "outcome": "unattempted", "prediction_included": False}
                      for identifier in sorted(expected - identifiers))
    predictions.sort(key=lambda row: row["instance_id"])
    ledger.sort(key=lambda row: row["instance_id"])
    raw = b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode() for row in predictions)
    output = Path(output)
    if output.is_symlink() or (output.exists() and output.read_bytes() != raw):
        raise ValueError("Frozen prediction export differs")
    sidecar = {"version": VERSION, "dataset_cases": len(expected) if expected is not None else None,
               "prediction_cases": len(predictions), "outcomes": ledger,
               "all_dataset_cases_attempted": expected is not None and bool(expected) and
                   {row["instance_id"] for row in predictions} == expected,
               "official_harness_executed": False,
               "scope": "Official SWE-bench prediction schema only; no official score or denominator claim is generated"}
    save(output.with_suffix(output.suffix + ".outcomes.json"), sidecar)
    if not output.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(raw)
    return sidecar


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    actions = command.add_subparsers(dest="action", required=True)
    inventory = actions.add_parser("inventory")
    inventory.add_argument("--history-root", type=Path, required=True)
    inventory.add_argument("--output", type=Path)
    selection = actions.add_parser("select")
    selection.add_argument("--dataset", type=Path, required=True)
    selection.add_argument("--history-root", type=Path, required=True)
    selection.add_argument("--output", type=Path, required=True)
    selection.add_argument("--private-gold", type=Path, required=True)
    selection.add_argument("--count", type=int, required=True)
    selection.add_argument("--development-count", type=int, default=0)
    selection.add_argument("--seed", required=True)
    selection.add_argument("--repository", action="append", default=[])
    selection.add_argument("--retrospective", action="store_true",
                           help="Select exposed cases only; never label this mode fresh evaluation")
    freezing = actions.add_parser("freeze")
    for name in ("cohort", "profile", "retrieval", "budgets", "output"):
        freezing.add_argument("--" + name, type=Path, required=True)
    freezing.add_argument("--source", action="append", required=True, help="Logical source name=explicit file path")
    scoring = actions.add_parser("score")
    scoring.add_argument("--private-gold", type=Path, required=True)
    scoring.add_argument("--ranked", type=Path, required=True)
    scoring.add_argument("--comparison", type=Path)
    scoring.add_argument("--output", type=Path, required=True)
    scoring.add_argument("--bootstrap-repetitions", type=int, default=2000)
    scoring.add_argument("--seed", default="011")
    exporting = actions.add_parser("export")
    exporting.add_argument("--attempts", type=Path, required=True)
    exporting.add_argument("--output", type=Path, required=True)
    exporting.add_argument("--model-name", required=True)
    exporting.add_argument("--dataset", type=Path)
    exporting.add_argument("--strategy")
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.action == "inventory":
            result = exposure_inventory(args.history_root)
            if args.output:
                save(args.output, result)
        elif args.action == "select":
            result = select_to_files(args)
        elif args.action == "freeze":
            sources = []
            for source in args.source:
                if "=" not in source:
                    raise ValueError("Source must be logical-name=explicit-path")
                name, path = source.split("=", 1)
                sources.append((name, Path(path)))
            result = freeze(args.cohort, args.profile, args.retrieval, args.budgets, sources, args.output)
        elif args.action == "score":
            result = score(args.private_gold, args.ranked, args.comparison, args.bootstrap_repetitions, args.seed)
            save(args.output, result)
        else:
            result = export_predictions(args.attempts, args.output, args.model_name, args.dataset, args.strategy)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"passed": False, "action": args.action,
                          "error_type": type(error).__name__, "detail": str(error)[:500]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
