import os
import signal
import sqlite3
import subprocess
import time
import httpx
import pytest

from harness import AgentHarness, AgentConfig
from harness.tools import SqlExecutionTool
from harness.workload import init_benchmark_database, BENCHMARK_TASKS


@pytest.fixture(scope="module")
def go_ingest_service():
    bin_path = "/Users/gauravkumarnayak/Desktop/new-karos/ingest/kairos-ingest"
    db_path = "/tmp/kairos_test_ingest_contract.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    proc = subprocess.Popen(
        [bin_path, "-port", "8899", "-db", db_path, "-buffer", "1024"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for service readiness
    ready = False
    for _ in range(30):
        try:
            r = httpx.get("http://localhost:8899/healthz", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.1)

    if not ready:
        proc.kill()
        raise RuntimeError("Go Ingest service failed to start on port 8899")

    yield "http://localhost:8899"

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()

    if os.path.exists(db_path):
        os.remove(db_path)


def test_end_to_end_ingest_contract(go_ingest_service):
    base_url = go_ingest_service

    # 1. Run agent task in Python
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    init_benchmark_database(db)

    sql_tool = SqlExecutionTool()
    sql_tool._conn = db
    task = BENCHMARK_TASKS[0]

    def mock_model(messages, step):
        if step == 0:
            return {"type": "tool_call", "tool_name": "execute_sql", "tool_args": {"query": task.canonical_sql}}
        return {"type": "final_answer", "content": "Done"}

    harness = AgentHarness(config=AgentConfig(), tools=[sql_tool], model_fn=mock_model)
    result = harness.run(task.prompt)

    events_payload = [e.model_dump() for e in result.event_log.events]
    assert len(events_payload) > 0

    # 2. POST batch to Go Ingest Service
    resp = httpx.post(f"{base_url}/api/v1/events/batch", json={"events": events_payload})
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == len(events_payload)
    assert data["duplicates"] == 0

    # 3. Re-post identical batch: Idempotent Deduplication Check
    resp_dup = httpx.post(f"{base_url}/api/v1/events/batch", json={"events": events_payload})
    assert resp_dup.status_code == 200
    data_dup = resp_dup.json()
    assert data_dup["accepted"] == 0
    assert data_dup["duplicates"] == len(events_payload)

    # 4. Query ingested run log
    resp_get = httpx.get(f"{base_url}/api/v1/runs/{result.run_id}")
    assert resp_get.status_code == 200
    run_data = resp_get.json()
    assert run_data["count"] == len(events_payload)

    # 5. Check health & outbox metrics
    resp_health = httpx.get(f"{base_url}/healthz")
    assert resp_health.status_code == 200
    h_data = resp_health.json()
    assert h_data["outbox_pending"] >= len(events_payload)
