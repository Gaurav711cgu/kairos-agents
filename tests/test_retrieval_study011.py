"""Blind selection, honest coverage and exact frozen identities for study011."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.retrieval_study011 import (VERSION, case_metrics, export_predictions,
    exposure_inventory, freeze, main, paired_bootstrap, private_labels,
    score, select, select_to_files)

PATCH = "--- a/package/source.py\n+++ b/package/source.py\n@@ -10,2 +10,2 @@\n-old_value\n+correct_value\n context\n"


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")
    return path


def record(task="repo-1", outcome="failed_checks", patch=PATCH, issue="Known historical issue"):
    return {"task_id": task, "outcome": outcome, "model_calls": 2,
            "task_snapshot": {"issue": issue},
            "steps": [{"name": "propose_patch", "result": {"body": {"patch": patch}}}]}


@pytest.fixture
def history(tmp_path):
    root = tmp_path / "history"
    write(root, "dashboard/evidence/records/one.json", record())
    write(root, "cases/investigations.json", {"cases": [{"id": "registered-2", "issue": "Registered issue"}]})
    write(root, "evidence/build007/qualification/excluded-3.json", {"id": "excluded-3", "qualified": False})
    write(root, "evidence/repair010/attempts.json", {"attempts": [{"case": "diagnostic-4", "outcome": "unknown_dispatch"}]})
    # Private runtime is outside the fixed public audit paths.
    (root / ".runtime").mkdir()
    (root / ".runtime/credentials.json").write_text("not valid JSON; must never be read")
    return root


def dataset(tmp_path, extra=()):
    values = [{"instance_id": f"fresh-{index}", "repo": "reviewed/repo", "base_commit": str(index) * 40,
               "problem_statement": f"Distinct defect {index}", "patch": PATCH,
               "test_patch": "hidden test material", "hints_text": "private hints"}
              for index in range(1, 7)]
    return write(tmp_path, "dataset.json", values + list(extra))


def test_history_groups_repeated_successes_and_keeps_failed_exposures(history):
    for index, (task, patch) in enumerate([("solved-1", PATCH), ("solved-1", PATCH),
                                           ("solved-2", PATCH), ("solved-1", PATCH + "\n")]):
        write(history, f"dashboard/evidence/records/success-{index}.json", record(task, "verified_repair", patch))
    result = exposure_inventory(history)
    assert result["audit"]["public_records"] == 5
    assert result["audit"]["verified_trajectories"] == 4
    assert result["audit"]["verified_unique_tasks"] == 2
    assert result["audit"]["verified_unique_rendered_patches"] == 3
    assert result["audit"]["training_data_ready"] is False
    assert {item["instance_id"] for item in result["exposures"]} >= {"repo-1", "registered-2", "excluded-3", "diagnostic-4"}
    assert "credentials" not in json.dumps(result)


def test_selection_is_blinded_deterministic_and_excludes_history_and_duplicate_issues(tmp_path, history):
    extras = [{"instance_id": "repo-1", "repo": "reviewed/repo", "base_commit": "a" * 40,
               "problem_statement": "A known ID", "patch": PATCH},
              {"instance_id": "different-id", "repo": "reviewed/repo", "base_commit": "b" * 40,
               "problem_statement": " KNOWN   HISTORICAL ISSUE ", "patch": PATCH}]
    path = dataset(tmp_path, extras)
    public, gold = select(path, history, 4, 2, "fixed-seed")
    again, _ = select(path, history, 4, 2, "fixed-seed")
    assert public == again
    assert [row["split"] for row in public["candidates"]] == ["development"] * 2 + ["holdout"] * 2
    assert {row["instance_id"] for row in public["exclusions"]} == {"repo-1", "different-id"}
    serialized = json.dumps(public)
    assert all(secret not in serialized for secret in ["correct_value", "package/source.py", "test_patch", "hints_text"])
    assert all(set(row) == {"instance_id", "repository", "base_commit", "issue", "split"}
               for row in public["candidates"])
    assert all(value["changed_files"] == ["package/source.py"] for value in gold["instances"].values())
    assert "correct_value" not in json.dumps(gold)


def test_private_labels_are_written_outside_public_directory_and_mode0600(tmp_path, history):
    args = SimpleNamespace(dataset=dataset(tmp_path), history_root=history,
                           output=tmp_path / "public/cohort.json", private_gold=tmp_path / "private/gold.json",
                           count=3, development_count=1, seed="011", repository=[])
    assert select_to_files(args)["private_labels_published"] is False
    assert args.private_gold.stat().st_mode & 0o777 == 0o600
    args.private_gold = tmp_path / "public/scorer.json"
    with pytest.raises(ValueError, match="outside"):
        select_to_files(args)


def test_exhausted_pool_and_duplicate_ids_fail_before_execution(tmp_path, history):
    path = dataset(tmp_path)
    with pytest.raises(ValueError, match="Insufficient"):
        select(path, history, 7, 0, "011")
    values = json.loads(path.read_text())
    path.write_text(json.dumps(values + [values[0]]))
    with pytest.raises(ValueError, match="unique"):
        select(path, history, 2, 0, "011")


def test_reference_proxy_excludes_tests_and_rejects_escaped_source():
    patch = PATCH + "--- a/tests/test_fix.py\n+++ b/tests/test_fix.py\n@@ -1 +1 @@\n-old\n+new\n"
    result = private_labels(patch)
    assert result["changed_files"] == ["package/source.py"]
    assert result["original_regions"] == [{"path": "package/source.py", "start_line": 10, "end_line": 10}]
    with pytest.raises(ValueError, match="Invalid source"):
        private_labels(PATCH.replace("package/source.py", "../escaped.py"))
    with pytest.raises(ValueError, match="actual captured"):
        private_labels("")


def test_source_and_all_configuration_hashes_are_frozen(tmp_path):
    source = tmp_path / "retrieval.py"
    source.write_text("initial source\n")
    files = [write(tmp_path, name, {"version": 1}) for name in ["cohort.json", "profile.json", "retrieval.json", "budgets.json"]]
    output = tmp_path / "freeze.json"
    args = (*files, [("scripts/retrieval.py", source)], output)
    freeze(*args)
    original = output.read_bytes()
    freeze(*args)
    assert output.read_bytes() == original
    source.write_text("changed source\n")
    with pytest.raises(ValueError, match="Frozen output differs"):
        freeze(*args)
    assert output.read_bytes() == original


def test_retrospective_selection_labels_exposed_cases_and_never_reuses_holdout_claim(tmp_path, history):
    known = {"instance_id": "repo-1", "repo": "reviewed/repo", "base_commit": "a" * 40,
             "problem_statement": "Known historical issue", "patch": PATCH}
    path = dataset(tmp_path, [known])
    public, _ = select(path, history, 1, 0, "011", retrospective=True)
    assert public["mode"] == "exposed-retrospective"
    assert [row["instance_id"] for row in public["candidates"]] == ["repo-1"]
    assert public["candidates"][0]["split"] == "retrospective"
    with pytest.raises(ValueError, match="cannot be labeled"):
        select(path, history, 2, 1, "011", retrospective=True)


def test_profile_change_cannot_reuse_frozen_study_identity(tmp_path):
    source = tmp_path / "source.py"; source.write_text("source")
    files = [write(tmp_path, name, {"version": 1}) for name in ["cohort.json", "profile.json", "retrieval.json", "budgets.json"]]
    output = tmp_path / "freeze.json"
    freeze(*files, [("source.py", source)], output)
    files[1].write_text('{"version":2}')
    with pytest.raises(ValueError, match="Frozen output differs"):
        freeze(*files, [("source.py", source)], output)


def test_retrieval_metrics_distinguish_file_recall_and_complete_changed_region_coverage():
    gold = {"changed_files": ["package/a.py", "package/b.py"],
            "original_regions": [{"path": "package/a.py", "start_line": 20, "end_line": 30}]}
    regions = [{"path": "package/a.py", "start_line": 20, "end_line": 22},
               {"path": "package/b.py", "start_line": 1, "end_line": 10},
               {"path": "package/a.py", "start_line": 10, "end_line": 40}]
    value = case_metrics(regions, gold)
    assert value["file_recall_at_1"] == .5
    assert value["file_hit_at_1"] == 1
    assert value["mrr"] == 1
    assert value["file_recall_at_5"] == 1
    assert value["whole_changed_region_hit_at_1"] == 0
    assert value["whole_changed_region_hit_at_5"] == 1


def test_missing_and_environment_cases_are_visible_and_not_invented_zeros(tmp_path):
    gold = {"version": VERSION, "instances": {name: private_labels(PATCH) for name in ["one", "two", "three"]}}
    gold_path = write(tmp_path, "private/gold.json", gold)
    ranking = write(tmp_path, "ranked.json", [{"instance_id": "one", "regions": [
        {"path": "package/source.py", "start_line": 1, "end_line": 40}]},
        {"instance_id": "two", "status": "environment_failure"}])
    result = score(gold_path, ranking)
    assert result["primary"]["cohort_cases"] == 3
    assert result["primary"]["scored_cases"] == 1
    assert result["primary"]["means"]["file_recall_at_1"] == 1
    assert result["primary"]["outcomes"] == {"completed": 1, "environment_failure": 1, "unattempted": 1}


def test_paired_bootstrap_is_reproducible_descriptive_and_case_paired():
    left = {"one": {"mrr": 0}, "two": {"mrr": .5}, "missing": {"mrr": .2}}
    right = {"one": {"mrr": .5}, "two": {"mrr": 1}}
    value = paired_bootstrap(left, right, 200, "frozen")
    assert value == paired_bootstrap(left, right, 200, "frozen")
    assert value["paired_cases"] == 2
    assert value["differences"]["mrr"]["mean_difference"] == .5
    assert value["differences"]["mrr"]["percentile_95_interval"] == [.5, .5]
    assert "do not establish superiority" in value["scope"]


@pytest.mark.parametrize("path", ["../reference.patch", "/etc/passwd", "source\\file.py", None])
def test_invalid_ranked_paths_cannot_reach_scoring(path):
    with pytest.raises(ValueError, match="Invalid source"):
        case_metrics([{"path": path, "start_line": 1, "end_line": 2}], private_labels(PATCH))


def test_official_prediction_export_keeps_missing_and_failed_cases_distinct(tmp_path):
    data = dataset(tmp_path)
    attempts = write(tmp_path, "attempts.json", {"attempts": [
        {"instance_id": "fresh-1", "outcome": "failed_checks", "model_patch": PATCH},
        {"instance_id": "fresh-2", "outcome": "environment_failure"},
        {"instance_id": "fresh-3", "outcome": "unattempted"}]})
    output = tmp_path / "predictions.jsonl"
    result = export_predictions(attempts, output, "frozen-provider/retrieval-v1", data)
    predictions = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(predictions) == 2
    assert all(set(row) == {"instance_id", "model_name_or_path", "model_patch"} for row in predictions)
    assert predictions[1]["model_patch"] == ""
    assert result["dataset_cases"] == 6 and result["prediction_cases"] == 2
    assert result["all_dataset_cases_attempted"] is False
    assert result["official_harness_executed"] is False
    assert [row["outcome"] for row in result["outcomes"]] == ["failed_checks", "environment_failure"] + ["unattempted"] * 4


def test_export_refuses_duplicate_strategy_cases_and_uncaptured_success(tmp_path):
    path = write(tmp_path, "attempts.json", [
        {"instance_id": "case-one", "configuration": strategy, "outcome": "failed_checks", "model_patch": PATCH}
        for strategy in ["baseline", "retrieval"]])
    with pytest.raises(ValueError, match="unique"):
        export_predictions(path, tmp_path / "ambiguous.jsonl", "profile")
    result = export_predictions(path, tmp_path / "selected.jsonl", "profile", strategy="baseline")
    assert result["prediction_cases"] == 1
    path = write(tmp_path, "success.json", [{"instance_id": "case-one", "outcome": "verified_repair"}])
    with pytest.raises(ValueError, match="no captured patch"):
        export_predictions(path, tmp_path / "missing.jsonl", "profile")


def test_cli_missing_dataset_fails_explicitly_without_services(tmp_path, history, capsys):
    status = main(["select", "--dataset", str(tmp_path / "missing.json"), "--history-root", str(history),
                   "--output", str(tmp_path / "public/cohort.json"), "--private-gold", str(tmp_path / "private/gold.json"),
                   "--count", "2", "--seed", "011"])
    result = json.loads(capsys.readouterr().out)
    assert status == 1 and result["passed"] is False
    assert not (tmp_path / "public/cohort.json").exists()
