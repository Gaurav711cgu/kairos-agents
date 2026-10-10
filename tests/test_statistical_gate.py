import pytest
from engine.stats import StatisticalRegressionGate
from engine.ablation import HarnessAblationStudy


def test_paired_bootstrap_detects_genuine_regression():
    # Baseline consistently scores 1.0 (100%)
    baseline = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    # Candidate experiences severe 40% regression
    candidate = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]

    result = StatisticalRegressionGate.paired_bootstrap(
        baseline_scores=baseline,
        candidate_scores=candidate,
        confidence_level=0.95,
        n_resamples=5000,
    )

    assert result.delta_mean == -0.4
    assert result.ci_upper < 0.0
    assert result.is_regression is True
    assert result.is_improvement is False
    assert result.p_value < 0.05


def test_paired_bootstrap_detects_no_significant_difference():
    # Identical performance with minor sampling noise
    baseline = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    candidate = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]

    result = StatisticalRegressionGate.paired_bootstrap(
        baseline_scores=baseline,
        candidate_scores=candidate,
        confidence_level=0.95,
        n_resamples=5000,
    )

    assert result.delta_mean == 0.0
    assert result.ci_lower <= 0.0 <= result.ci_upper
    assert result.is_regression is False
    assert result.is_improvement is False


def test_holm_bonferroni_correction():
    tasks = ["task_01", "task_02", "task_03", "task_04"]
    # Task 1: highly significant, Task 2: marginal, Task 3 & 4: noise
    raw_p = [0.001, 0.04, 0.35, 0.75]

    correction = StatisticalRegressionGate.holm_bonferroni_correction(
        task_ids=tasks,
        p_values=raw_p,
        alpha=0.05,
    )

    # Task 1 (p=0.001): adjusted = 0.001 * 4 = 0.004 <= 0.05 -> rejected
    assert correction.rejected_null[0] is True
    # Task 2 (p=0.04): adjusted = 0.04 * 3 = 0.12 > 0.05 -> fails correction! (Naive rule would have false-alarmed)
    assert correction.rejected_null[1] is False
    assert correction.rejected_null[2] is False
    assert correction.rejected_null[3] is False


def test_harness_ablation_study():
    report = HarnessAblationStudy.run_ablation()

    assert report.baseline_success_rate == 1.0
    assert report.no_verifier_success_rate < report.baseline_success_rate
    assert report.verifier_bootstrap.is_regression is True
