"""Synthetic unit fixtures test reporting rules, never claim a measured repair score."""
import copy
import json

import pytest
from scripts.repair_report013 import identity, load, main, summarize


@pytest.fixture
def study():
    arms = [{"arm_id": name, "model_name_or_path": "exact-provider/model-revision",
             "configuration_sha256": digit * 64}
            for name, digit in [("baseline_context6", "a"), ("retrieval6", "b"), ("retrieval10", "c")]]
    frozen = {"study_id": "unit-fixture", "scope": "Synthetic test input only",
              "cases": ["case-1", "case-2", "case-3"], "arms": arms}
    rows = [{**arm, "instance_id": case, "outcome": outcome, "calls": 1}
            for arm in arms for case, outcome in zip(frozen["cases"],
                ["verified_repair", "failed_checks", "unknown_dispatch"])]
    return frozen, {"study_sha256": identity(frozen), "attempts": rows}


def probability(row, value=.8):
    row["independent_checks_started_at"] = "2026-10-16T01:00:01+00:00"
    row["confidence"] = {"experiment_id": "confidence-v1", "abstained": False,
                         "probability": value, "captured_at": "2026-10-16T01:00:00Z"}


def test_missing_costs_and_cases_are_visible_without_zero_imputation(study):
    frozen, ledger = study
    ledger["attempts"].pop()
    report = summarize(frozen, ledger, 100)
    arm = report["arms"]["retrieval10"]
    assert (arm["intent_to_run"], arm["attempted"], arm["completed_grading"], arm["missing_ledger"]) == (3, 2, 2, 1)
    assert arm["missing_case_ids"] == ["case-3"]
    assert arm["costs"]["input_tokens"] == {"observed_attempts": 0, "missing_attempts": 2,
                                             "observed_sum": None, "complete_sum": None}
    assert report["arms"]["baseline_context6"]["outcomes"]["unknown_dispatch"] == 1
    assert arm["verified_per_attempted"] == .5


@pytest.mark.parametrize("mutation", ["duplicate", "case", "arm", "model", "config", "outcome", "cost", "freeze"])
def test_malformed_ledger_and_identity_fail_closed(study, mutation):
    frozen, ledger = study
    row = ledger["attempts"][0]
    if mutation == "duplicate":
        ledger["attempts"].append(copy.deepcopy(row))
    elif mutation == "freeze":
        frozen["scope"] = "Changed after ledger identity"
    else:
        field, value = {"case": ("instance_id", "unselected"), "arm": ("arm_id", "new"),
            "model": ("model_name_or_path", "other-model"), "config": ("configuration_sha256", "d" * 64),
            "outcome": ("outcome", "passed"), "cost": ("calls", True)}[mutation]
        row[field] = value
    with pytest.raises((ValueError, TypeError)):
        summarize(frozen, ledger)


def test_paired_matching_excludes_unknown_and_missing_and_reproduces_seed(study):
    frozen, ledger = study
    ledger["attempts"][3]["outcome"] = "failed_checks"
    ledger["attempts"][4]["outcome"] = "verified_repair"
    ledger["attempts"][5]["outcome"] = "verified_repair"
    report = summarize(frozen, ledger, 137, "seed")
    assert report == summarize(frozen, ledger, 137, "seed")
    paired = report["comparisons"][0]
    assert paired["paired_case_ids"] == ["case-1", "case-2"]
    assert paired["excluded_case_ids"] == ["case-3"]
    assert paired["mean_difference"] == 0
    assert paired["percentile_95_interval"] == [-1, 1]


@pytest.mark.parametrize("failure", ["invalid_patch", "invalid_response", "no_patch", "budget_exhausted"])
def test_primary_pairs_keep_workflow_failures_instead_of_selective_grading(study, failure):
    frozen, ledger = study
    ledger["attempts"][1]["outcome"] = failure
    ledger["attempts"][4]["outcome"] = "verified_repair"
    report = summarize(frozen, ledger, 100)
    primary, secondary = report["comparisons"][0], report["graded_only_comparisons"][0]
    assert primary["intent_to_run_pairs"] == 3 and primary["paired_cases"] == 2
    assert primary["mean_difference"] == .5
    assert secondary["paired_cases"] == 1 and secondary["mean_difference"] == 0
    assert primary["excluded_outcomes"]["case-3"]["left"] == "unknown_dispatch"


def test_one_or_no_graded_pair_has_explicit_small_sample_limits(study):
    frozen, ledger = study
    for row in ledger["attempts"]:
        row["outcome"] = "unknown_dispatch"
    empty = summarize(frozen, ledger, 100)["comparisons"][0]
    assert empty["paired_cases"] == 0 and empty["mean_difference"] is None
    for index in (0, 3):
        ledger["attempts"][index]["outcome"] = "verified_repair"
    pair = summarize(frozen, ledger, 100)["comparisons"][0]
    assert pair["paired_cases"] == 1 and pair["percentile_95_interval"] == [0, 0]
    assert "does not establish superiority" in pair["scope"]


def test_confidence_scores_only_graded_outcomes_and_keeps_abstentions(study):
    frozen, ledger = study
    for row in ledger["attempts"][:3]:
        probability(row)
    ledger["attempts"][3]["confidence"] = {"experiment_id": "confidence-v1", "abstained": True}
    report = summarize(frozen, ledger, 100)
    confidence = report["arms"]["baseline_context6"]["confidence"]
    assert confidence["scored"] == 2 and confidence["brier_score"] == pytest.approx(.34)
    assert confidence["unscorable_outcome"] == 1
    assert confidence["reliability_bins"][-1]["count"] == 2
    assert report["arms"]["retrieval6"]["confidence"]["abstentions"] == 1
    assert report["arms"]["retrieval10"]["confidence"]["brier_score"] is None
    assert report["confidence_by_model"]["exact-provider/model-revision"]["scored"] == 2


@pytest.mark.parametrize("change", ["late", "equal", "missing_time", "naive", "nan", "bool", "range", "abstain"])
def test_confidence_leakage_and_invalid_probabilities_rejected(study, change):
    frozen, ledger = study
    row = ledger["attempts"][0]
    probability(row)
    confidence = row["confidence"]
    if change == "missing_time":
        del row["independent_checks_started_at"]
    elif change in ("late", "equal", "naive"):
        confidence["captured_at"] = {"late": "2026-10-16T01:00:02Z", "equal": row["independent_checks_started_at"],
                                     "naive": "2026-10-16T01:00:00"}[change]
    elif change == "abstain":
        confidence["abstained"] = True
    else:
        confidence["probability"] = {"nan": float("nan"), "bool": True, "range": 1.01}[change]
    with pytest.raises((ValueError, TypeError)):
        summarize(frozen, ledger)


def test_parser_rejects_duplicate_keys_and_cli_reports_errors(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text('{"attempts":[],"attempts":[]}')
    with pytest.raises(ValueError, match="Duplicate"):
        load(bad)
    assert main(["--frozen", str(bad), "--attempts", str(bad)]) == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False
