import sqlite3
import pytest
from harness import AgentHarness, AgentConfig
from harness.tools import SqlExecutionTool
from harness.workload import init_benchmark_database, BENCHMARK_TASKS
from engine.replay import ReplayEngine
from engine.fork import ForkEngine


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_benchmark_database(conn)
    return conn


def test_strict_replay_exact_match(test_db):
    sql_tool = SqlExecutionTool()
    sql_tool._conn = test_db
    task = BENCHMARK_TASKS[0]

    def model_fn(messages, step):
        if step == 0:
            return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": task.canonical_sql}}
        return {"type": "final_answer", "content": "Done"}

    config = AgentConfig()
    harness = AgentHarness(config=config, tools=[sql_tool], model_fn=model_fn)

    res1 = harness.run(task.prompt)
    res2 = harness.run(task.prompt)

    divergence = ReplayEngine.detect_divergence(res1.event_log, res2.event_log)
    assert divergence.diverged is False
    assert divergence.divergence_step is None


def test_divergence_detection_when_model_changes(test_db):
    sql_tool = SqlExecutionTool()
    sql_tool._conn = test_db
    task = BENCHMARK_TASKS[0]

    # Baseline model
    def baseline_model(messages, step):
        if step == 0:
            return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": task.canonical_sql}}
        return {"type": "final_answer", "content": "Done"}

    # Divergent model (runs wrong SQL query at step 0)
    def candidate_model(messages, step):
        if step == 0:
            return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": "SELECT * FROM orders"}}
        return {"type": "final_answer", "content": "Done"}

    config = AgentConfig()
    h1 = AgentHarness(config=config, tools=[sql_tool], model_fn=baseline_model)
    h2 = AgentHarness(config=config, tools=[sql_tool], model_fn=candidate_model)

    res_base = h1.run(task.prompt)
    res_cand = h2.run(task.prompt)

    divergence = ReplayEngine.detect_divergence(res_base.event_log, res_cand.event_log)
    assert divergence.diverged is True
    assert divergence.divergence_step == 0
    assert "Tool call diverged at step 0" in divergence.diff_summary


def test_fork_at_step(test_db):
    sql_tool = SqlExecutionTool()
    sql_tool._conn = test_db
    task = BENCHMARK_TASKS[0]

    def baseline_model(messages, step):
        if step == 0:
            return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": task.canonical_sql}}
        return {"type": "final_answer", "content": "Original final answer"}

    config = AgentConfig(max_steps=3)
    harness = AgentHarness(config=config, tools=[sql_tool], model_fn=baseline_model)

    res_base = harness.run(task.prompt)

    # Patch model at step 1 to output modified final answer
    def patched_model(messages, step):
        return {"type": "final_answer", "content": "Forked patched answer"}

    res_forked = ForkEngine.fork_at_step(
        harness=harness,
        task_prompt=task.prompt,
        baseline_log=res_base.event_log,
        fork_step=1,
        patched_model_fn=patched_model,
    )

    assert res_forked.status == "completed"
    assert res_forked.final_answer == "Forked patched answer"
    assert res_forked.run_id.startswith("fork_")
