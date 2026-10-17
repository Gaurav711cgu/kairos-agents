"""Describe a frozen repair study from captured attempts; never run or retry work."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

VERSION = "repair-report013-v1"
GRADED = {"verified_repair": 1, "failed_checks": 0}
KNOWN = {**GRADED, "invalid_patch": 0, "invalid_response": 0, "no_patch": 0, "budget_exhausted": 0}
OUTCOMES = set(KNOWN) | {"environment_failure", "infrastructure_error", "provider_unavailable",
                       "timeout", "unknown_dispatch", "cancelled", "unattempted"}
COSTS = ("calls", "checks", "input_tokens", "output_tokens", "elapsed_seconds")
SCOPE = ("Custom curated repair subset; no official SWE-bench score. Descriptive issue-paired "
         "uncertainty with small samples does not establish superiority or a release gate.")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024**2:
        raise ValueError("Input must be an ordinary file of at most 64 MiB")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("Non-finite JSON number")
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=constant)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 500


def timestamp(value):
    if not isinstance(value, str):
        raise TypeError("Confidence requires timestamp evidence")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include its timezone")
    return result


def number(value, field):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            (isinstance(value, float) and not math.isfinite(value)) or value < 0 or
            (field != "elapsed_seconds" and type(value) is not int)):
        raise ValueError("Invalid nonnegative cost: " + field)
    return value


def validate(frozen, ledger):
    if not isinstance(frozen, dict) or not all(text(frozen.get(key)) for key in ("study_id", "scope")):
        raise ValueError("Frozen study_id and scope are required")
    cases, arms = frozen.get("cases"), frozen.get("arms")
    if (not isinstance(cases, list) or not cases or not all(text(case) for case in cases) or
            len(set(cases)) != len(cases)):
        raise ValueError("Frozen cases must be explicit, nonempty and unique")
    if not isinstance(arms, list) or len(arms) < 2:
        raise ValueError("At least two explicit frozen arms are required")
    arm_map = {}
    for arm in arms:
        if (not isinstance(arm, dict) or not text(arm.get("arm_id")) or
                not text(arm.get("model_name_or_path")) or
                not isinstance(arm.get("configuration_sha256"), str) or
                not re.fullmatch(r"[0-9a-f]{64}", arm["configuration_sha256"]) or
                arm["arm_id"] in arm_map):
            raise ValueError("Frozen arms need unique IDs, exact models and configuration SHA256")
        arm_map[arm["arm_id"]] = arm
    if not isinstance(ledger, dict) or ledger.get("study_sha256") != identity(frozen):
        raise ValueError("Ledger does not match frozen study identity")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise TypeError("Explicit attempts list is required")
    indexed = {}
    for row in attempts:
        if not isinstance(row, dict):
            raise TypeError("Attempt must be an object")
        case, arm_id = row.get("instance_id"), row.get("arm_id")
        if not isinstance(case, str) or case not in cases or not isinstance(arm_id, str) or arm_id not in arm_map:
            raise ValueError("Attempt lies outside frozen cases or arms")
        key = (case, arm_id)
        if key in indexed:
            raise ValueError("Duplicate case/arm; retries need a separately frozen study")
        arm = arm_map[arm_id]
        if any(row.get(field) != arm[field] for field in ("model_name_or_path", "configuration_sha256")):
            raise ValueError("Attempt model/configuration differs from frozen arm")
        if not isinstance(row.get("outcome"), str) or row["outcome"] not in OUTCOMES:
            raise ValueError("Unknown outcome; do not infer success from process status")
        for field in COSTS:
            if row.get(field) is not None:
                number(row[field], field)
        confidence(row)  # Validate even probabilities whose outcomes cannot be scored.
        indexed[key] = row
    return cases, arm_map, indexed


def confidence(row):
    value = row.get("confidence")
    if value is None:
        return "unavailable", None
    if (not isinstance(value, dict) or not text(value.get("experiment_id")) or
            type(value.get("abstained")) is not bool):
        raise ValueError("Confidence requires a separate experiment identity and explicit abstention")
    probability = value.get("probability")
    if value["abstained"]:
        if probability is not None:
            raise ValueError("An abstention cannot also provide a probability")
        return "abstained", None
    if probability is None:
        return "unavailable", None
    if (isinstance(probability, bool) or not isinstance(probability, (int, float)) or
            not 0 <= probability <= 1 or not math.isfinite(probability)):
        raise ValueError("Confidence probability must be in [0, 1]")
    if timestamp(value.get("captured_at")) >= timestamp(row.get("independent_checks_started_at")):
        raise ValueError("Confidence must be captured strictly before independent checks")
    return "available", probability


def calibration(rows, bin_count):
    counts: Counter[str] = Counter()
    bins: list[list[tuple[float, int]]] = [[] for _ in range(bin_count)]
    per_case = []
    for row in rows:
        state, probability = confidence(row)
        counts[state] += 1
        if state != "available":
            continue
        if row["outcome"] not in GRADED:
            counts["unscorable_outcome"] += 1
            continue
        outcome = GRADED[row["outcome"]]
        bins[min(int(probability * bin_count), bin_count - 1)].append((probability, outcome))
        per_case.append({"instance_id": row["instance_id"], "arm_id": row["arm_id"],
                         "experiment_id": row["confidence"]["experiment_id"],
                         "probability": probability, "outcome": outcome,
                         "brier": (probability - outcome) ** 2})
    return {"scored": len(per_case), "unique_cases": len({r["instance_id"] for r in per_case}),
        "brier_score": sum(r["brier"] for r in per_case) / len(per_case) if per_case else None,
        "abstentions": counts["abstained"], "unavailable": counts["unavailable"],
        "unscorable_outcome": counts["unscorable_outcome"], "per_case": per_case,
        "reliability_bins": [{"lower": i / bin_count, "upper": (i + 1) / bin_count,
            "count": len(bucket), "mean_probability": sum(p for p, _ in bucket) / len(bucket) if bucket else None,
            "observed_frequency": sum(y for _, y in bucket) / len(bucket) if bucket else None}
            for i, bucket in enumerate(bins)]}


def costs(rows):
    result = {}
    for field in COSTS:
        values = [row[field] for row in rows if row.get(field) is not None]
        result[field] = {"observed_attempts": len(values), "missing_attempts": len(rows) - len(values),
                         "observed_sum": sum(values) if values else None,
                         "complete_sum": sum(values) if values and len(values) == len(rows) else None}
    return result


def paired(left, right, cases, repetitions, seed, labels=KNOWN):
    # Same case-resampling percentile method as retrieval_study011.paired_bootstrap.
    common = [case for case in cases if case in left and case in right and
              left[case]["outcome"] in labels and right[case]["outcome"] in labels]
    values = [labels[right[case]["outcome"]] - labels[left[case]["outcome"]] for case in common]
    result = {"intent_to_run_pairs": len(cases), "paired_cases": len(common), "paired_case_ids": common,
              "excluded_case_ids": [case for case in cases if case not in common],
              "excluded_outcomes": {case: {"left": left.get(case, {}).get("outcome", "missing_ledger"),
                  "right": right.get(case, {}).get("outcome", "missing_ledger")}
                  for case in cases if case not in common},
              "mean_difference": None, "percentile_95_interval": None,
              "denominator": "Cases with known outcomes in both arms; right minus left",
              "included_outcome_labels": dict(labels),
              "repetitions": repetitions, "seed": str(seed), "scope": SCOPE}
    if values:
        generator = random.Random(str(seed))
        estimates = sorted(sum(generator.choice(values) for _ in values) / len(values)
                           for _ in range(repetitions))
        result.update(mean_difference=sum(values) / len(values), percentile_95_interval=[
            estimates[math.floor(.025 * (repetitions - 1))], estimates[math.ceil(.975 * (repetitions - 1))]])
    return result


def summarize(frozen, ledger, repetitions=2000, seed="013", bin_count=5):
    if type(repetitions) is not int or not 100 <= repetitions <= 10_000:
        raise ValueError("Bootstrap repetitions must be between 100 and 10000")
    if type(bin_count) is not int or not 1 <= bin_count <= 20:
        raise ValueError("Reliability bin count must be between 1 and 20")
    cases, arm_map, indexed = validate(frozen, ledger)
    arms, by_arm = {}, {}
    for arm_id, arm in arm_map.items():
        rows = [indexed[(case, arm_id)] for case in cases if (case, arm_id) in indexed]
        by_arm[arm_id] = {row["instance_id"]: row for row in rows}
        outcomes = Counter(row["outcome"] for row in rows)
        missing = [case for case in cases if (case, arm_id) not in indexed]
        attempted = len(rows) - outcomes["unattempted"]
        completed = sum(outcomes[outcome] for outcome in GRADED)
        arms[arm_id] = {"identity": arm, "intent_to_run": len(cases), "attempted": attempted,
            "completed_grading": completed, "missing_ledger": len(missing), "missing_case_ids": missing,
            "outcomes": {outcome: outcomes[outcome] for outcome in sorted(OUTCOMES)},
            "verified_repairs": outcomes["verified_repair"],
            "verified_per_attempted": outcomes["verified_repair"] / attempted if attempted else None,
            "verified_per_intent_to_run": outcomes["verified_repair"] / len(cases),
            "costs": costs(rows), "confidence": calibration(rows, bin_count)}
    return {"version": VERSION, "study_id": frozen["study_id"], "study_sha256": identity(frozen),
        "declared_scope": frozen["scope"], "scope": SCOPE, "arms": arms,
        "missing_cost_policy": "Null or absent costs stay missing; observed sums are incomplete when any value is missing",
        "unknown_policy": "Infrastructure, invalid, timeout and unknown outcomes are not calibrated as verified failures",
        "comparisons": [{"left": left, "right": right,
            **paired(by_arm[left], by_arm[right], cases, repetitions, seed)}
            for left, right in itertools.combinations(arm_map, 2)],
        "graded_only_comparisons": [{"left": left, "right": right,
            **paired(by_arm[left], by_arm[right], cases, repetitions, seed, GRADED)}
            for left, right in itertools.combinations(arm_map, 2)],
        "confidence_by_model": {model: calibration([row for row in indexed.values()
            if row["model_name_or_path"] == model], bin_count)
            for model in sorted({arm["model_name_or_path"] for arm in arm_map.values()})}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", default="013")
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--bins", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        report = summarize(load(args.frozen), load(args.attempts), args.bootstrap_repetitions, args.seed, args.bins)
        raw = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            if args.output.is_symlink() or (args.output.exists() and args.output.read_text() != raw):
                raise ValueError("Report output already exists with different bytes")
            if not args.output.exists():
                with args.output.open("x") as stream:
                    stream.write(raw)
        print(raw, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"passed": False, "error": type(error).__name__, "detail": str(error)[:500]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
