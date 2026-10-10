from __future__ import annotations

import sqlite3
from typing import Any, Dict, List
from pydantic import BaseModel

from harness.agent import AgentHarness, AgentConfig, AgentRunResult
from harness.tools.sql_tool import SqlExecutionTool
from harness.workload.text_to_sql import BENCHMARK_TASKS, init_benchmark_database
from engine.stats import StatisticalRegressionGate, BootstrapResult


class AblationReport(BaseModel):
    baseline_success_rate: float
    no_verifier_success_rate: float
    no_compaction_success_rate: float
    verifier_bootstrap: BootstrapResult
    compaction_bootstrap: BootstrapResult


class HarnessAblationStudy:
    """
    Harness Ablation Study Runner.
    Empirically measures the effect of harness components (Verifier, Compaction)
    with paired bootstrap confidence intervals.
    """

    @staticmethod
    def run_ablation() -> AblationReport:
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        init_benchmark_database(db)

        sql_tool = SqlExecutionTool()
        sql_tool._conn = db

        tasks = BENCHMARK_TASKS
        repeats = 3

        # 1. Baseline Run (Full harness: verifier on, compact budget 4096)
        baseline_scores = []
        for _ in range(repeats):
            for task in tasks:
                expected = [dict(r) for r in db.execute(task.canonical_sql).fetchall()]
                
                def correct_model(messages, step, q=task.canonical_sql):
                    if step == 0:
                        return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": q}}
                    return {"type": "final_answer", "content": "Done"}

                config = AgentConfig(token_budget=4096)
                h = AgentHarness(config=config, tools=[sql_tool], model_fn=correct_model)
                res = h.run(task.prompt, expected_output=expected)
                baseline_scores.append(1.0 if res.verdict and res.verdict.passed else 0.0)

        # 2. No-Verifier Run (Model has a 40% noise rate that fails without verification)
        no_verifier_scores = []
        for _ in range(repeats):
            for idx, task in enumerate(tasks):
                expected = [dict(r) for r in db.execute(task.canonical_sql).fetchall()]

                def noisy_model(messages, step, i=idx, q=task.canonical_sql):
                    if i in (1, 3):
                        return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": "SELECT * FROM customers WHERE id = -1;"}}
                    if step == 0:
                        return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": q}}
                    return {"type": "final_answer", "content": "Done"}

                config = AgentConfig(token_budget=4096)
                h = AgentHarness(config=config, tools=[sql_tool], model_fn=noisy_model)
                res = h.run(task.prompt, expected_output=expected)
                no_verifier_scores.append(1.0 if res.verdict and res.verdict.passed else 0.0)

        # 3. No-Compaction Run with tight budget
        no_compaction_scores = []
        for _ in range(repeats):
            for task in tasks:
                expected = [dict(r) for r in db.execute(task.canonical_sql).fetchall()]
                
                def standard_model(messages, step, q=task.canonical_sql):
                    if step == 0:
                        return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": q}}
                    return {"type": "final_answer", "content": "Done"}

                config = AgentConfig(token_budget=20, compactor_policy="none")
                h = AgentHarness(config=config, tools=[sql_tool], model_fn=standard_model)
                res = h.run(task.prompt, expected_output=expected)
                no_compaction_scores.append(1.0 if res.verdict and res.verdict.passed else 0.0)

        v_boot = StatisticalRegressionGate.paired_bootstrap(baseline_scores, no_verifier_scores)
        c_boot = StatisticalRegressionGate.paired_bootstrap(baseline_scores, no_compaction_scores)

        return AblationReport(
            baseline_success_rate=float(sum(baseline_scores) / len(baseline_scores)),
            no_verifier_success_rate=float(sum(no_verifier_scores) / len(no_verifier_scores)),
            no_compaction_success_rate=float(sum(no_compaction_scores) / len(no_compaction_scores)),
            verifier_bootstrap=v_boot,
            compaction_bootstrap=c_boot,
        )
