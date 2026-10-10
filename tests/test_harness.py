import sqlite3
import pytest
from harness import AgentHarness, AgentConfig, EventType, DeterministicVerifier
from harness.tools import SqlExecutionTool
from harness.workload import init_benchmark_database, BENCHMARK_TASKS


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_benchmark_database(conn)
    return conn


def test_agent_harness_text_to_sql_execution(test_db):
    sql_tool = SqlExecutionTool()
    sql_tool._conn = test_db

    task = BENCHMARK_TASKS[0]  # Platinum customers query

    # Model mock that translates task prompt into canonical query and returns final answer
    def mock_model(messages, step):
        if step == 0:
            return {
                "type": "tool_call",
                "tool_name": "execute_sql",
                "tool_args": {"query": task.canonical_sql},
            }
        return {
            "type": "final_answer",
            "content": "Retrieved platinum tier customers successfully.",
        }

    config = AgentConfig(max_steps=3, token_budget=2048)
    harness = AgentHarness(config=config, tools=[sql_tool], model_fn=mock_model)

    # Compute expected result
    expected_rows = [dict(r) for r in test_db.execute(task.canonical_sql).fetchall()]

    result = harness.run(task_prompt=task.prompt, expected_output=expected_rows)

    assert result.status == "completed"
    assert result.total_steps == 2
    assert result.verdict is not None
    assert result.verdict.passed is True
    assert result.event_log.verify_integrity() is True


def test_context_compaction_audit():
    from harness.context import ContextManager

    cm = ContextManager(token_budget=100)  # Very low token budget to force compaction
    cm.set_system_prompt("You are a helpful assistant.")
    cm.set_task("Do task")

    # Add several large tool observations
    for i in range(10):
        cm.add_message("tool", f"Result {i}: " + "x" * 150)

    messages, audit, context_hash = cm.assemble()

    assert audit.performed is True
    assert audit.dropped_count > 0
    assert audit.compacted_tokens < audit.original_tokens
    assert len(context_hash) == 64


def test_kill_and_resume_checkpointing(test_db):
    sql_tool = SqlExecutionTool()
    sql_tool._conn = test_db
    task = BENCHMARK_TASKS[1]

    execution_count = 0

    def mock_model(messages, step):
        nonlocal execution_count
        execution_count += 1
        if step == 0:
            return {
                "type": "tool_call",
                "tool_name": "execute_sql",
                "tool_args": {"query": task.canonical_sql},
            }
        return {"type": "final_answer", "content": "Done"}

    config = AgentConfig(max_steps=1)  # Simulate kill / timeout after step 0
    harness = AgentHarness(config=config, tools=[sql_tool], model_fn=mock_model)

    result_p1 = harness.run(task_prompt=task.prompt)
    assert result_p1.status == "max_steps_exceeded"

    # Find the checkpoint event
    checkpoint_event = next(
        e for e in result_p1.event_log.events if e.event_type == EventType.CHECKPOINT_SAVED
    )
    checkpoint_data = {
        "run_id": result_p1.run_id,
        "next_step": checkpoint_event.payload["next_step"],
        "executed_tool_keys": checkpoint_event.payload["executed_tool_keys"],
        "past_events": [e.model_dump() for e in result_p1.event_log.events],
    }

    # Resume with max_steps=3
    config_resume = AgentConfig(max_steps=3)
    harness_resume = AgentHarness(config=config_resume, tools=[sql_tool], model_fn=mock_model)

    result_p2 = harness_resume.run(
        task_prompt=task.prompt, resume_from_checkpoint=checkpoint_data
    )

    assert result_p2.status == "completed"
    assert result_p2.run_id == result_p1.run_id
    assert result_p2.event_log.verify_integrity() is True
