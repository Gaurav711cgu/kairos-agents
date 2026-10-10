from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel


class BootstrapResult(BaseModel):
    mean_baseline: float
    mean_candidate: float
    delta_mean: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    p_value: float
    is_regression: bool
    is_improvement: bool
    sample_size: int
    n_resamples: int


class MultiTestCorrectionResult(BaseModel):
    task_ids: List[str]
    raw_p_values: List[float]
    adjusted_p_values: List[float]
    rejected_null: List[bool]
    alpha: float


class StatisticalRegressionGate:
    """
    Statistical Regression Gate for Agent Evaluations.
    Evaluates whether performance changes across non-deterministic runs
    represent genuine regressions or sampling noise using paired bootstrap CIs.
    """

    @staticmethod
    def paired_bootstrap(
        baseline_scores: List[float],
        candidate_scores: List[float],
        confidence_level: float = 0.95,
        n_resamples: int = 10000,
        random_seed: int = 42,
    ) -> BootstrapResult:
        if len(baseline_scores) != len(candidate_scores):
            raise ValueError(
                f"Paired evaluation requires equal sample lengths: baseline ({len(baseline_scores)}) != candidate ({len(candidate_scores)})"
            )

        n = len(baseline_scores)
        if n < 3:
            raise ValueError(f"Sample size {n} too small for statistical bootstrap testing (minimum n=3)")

        b_arr = np.array(baseline_scores, dtype=np.float64)
        c_arr = np.array(candidate_scores, dtype=np.float64)

        mean_b = float(np.mean(b_arr))
        mean_c = float(np.mean(c_arr))
        observed_delta = mean_c - mean_b

        rng = np.random.default_rng(random_seed)
        # Resample paired differences
        diffs = c_arr - b_arr
        indices = rng.integers(0, n, size=(n_resamples, n))
        bootstrap_means = np.mean(diffs[indices], axis=1)

        alpha = 1.0 - confidence_level
        lower_pct = (alpha / 2.0) * 100.0
        upper_pct = (1.0 - alpha / 2.0) * 100.0

        ci_lower = float(np.percentile(bootstrap_means, lower_pct))
        ci_upper = float(np.percentile(bootstrap_means, upper_pct))

        # Empirical p-value (proportion of bootstrap samples with opposite sign or zero)
        if observed_delta <= 0:
            p_val = float(np.mean(bootstrap_means >= 0))
        else:
            p_val = float(np.mean(bootstrap_means <= 0))

        # Two-sided p-value approximation
        p_val_two_sided = min(1.0, 2.0 * p_val)

        is_regression = ci_upper < 0.0 and p_val_two_sided < (1.0 - confidence_level)
        is_improvement = ci_lower > 0.0 and p_val_two_sided < (1.0 - confidence_level)

        return BootstrapResult(
            mean_baseline=round(mean_b, 4),
            mean_candidate=round(mean_c, 4),
            delta_mean=round(observed_delta, 4),
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
            confidence_level=confidence_level,
            p_value=round(p_val_two_sided, 4),
            is_regression=is_regression,
            is_improvement=is_improvement,
            sample_size=n,
            n_resamples=n_resamples,
        )

    @staticmethod
    def holm_bonferroni_correction(
        task_ids: List[str],
        p_values: List[float],
        alpha: float = 0.05,
    ) -> MultiTestCorrectionResult:
        m = len(p_values)
        if m == 0:
            return MultiTestCorrectionResult(
                task_ids=[], raw_p_values=[], adjusted_p_values=[], rejected_null=[], alpha=alpha
            )

        # Sort p-values with original indices
        sorted_indices = sorted(range(m), key=lambda i: p_values[i])
        sorted_p = [p_values[i] for i in sorted_indices]

        adjusted = [0.0] * m
        rejected = [False] * m

        # Holm-Bonferroni adjusted p-values: cumulative maximum of raw_p * (m - k + 1)
        curr_max = 0.0
        for rank, idx in enumerate(sorted_indices):
            k = rank + 1
            raw_p = sorted_p[rank]
            adj_p = min(1.0, max(curr_max, raw_p * (m - k + 1)))
            curr_max = adj_p
            adjusted[idx] = round(adj_p, 4)

        # Step-down rejection: reject H_(k) if raw_p <= alpha / (m - k + 1) until first failure
        for rank, idx in enumerate(sorted_indices):
            k = rank + 1
            threshold = alpha / (m - k + 1)
            raw_p = sorted_p[rank]
            if raw_p <= threshold:
                rejected[idx] = True
            else:
                break

        return MultiTestCorrectionResult(
            task_ids=task_ids,
            raw_p_values=[round(p, 4) for p in p_values],
            adjusted_p_values=adjusted,
            rejected_null=rejected,
            alpha=alpha,
        )
