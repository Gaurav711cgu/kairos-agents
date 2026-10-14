import signal
import shutil
import socket
import sqlite3
import subprocess
import time
from pathlib import Path
import httpx
import pytest

from harness import AgentHarness, AgentConfig
from harness.tools import SqlExecutionTool
from harness.workload import init_benchmark_database, BENCHMARK_TASKS


@pytest.fixture(scope="module")
def go_ingest_service(tmp_path_factory):
    go = shutil.which("go")
    if go is None:
        raise RuntimeError("Go toolchain from ingest/go.mod is required for ingest acceptance")
    source = Path(__file__).resolve().parents[1] / "ingest"
    runtime = tmp_path_factory.mktemp("go-ingest-contract")
    bin_path = runtime / "kairos-ingest"
    build = subprocess.run(
        [go, "build", "-o", str(bin_path), "."], cwd=source,
        capture_output=True, text=True, timeout=300,
    )
    if build.returncode:
        raise RuntimeError("Go ingest build failed: " + build.stderr[-4000:])
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    # Wait for service readiness
    log_path = runtime / "service.log"
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            [str(bin_path), "-port", str(port), "-db", str(runtime / "events.db"), "-buffer", "1024"],
            cwd=runtime, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("Go ingest exited during startup: " + log_path.read_text()[-4000:])
                try:
                    if httpx.get(base_url + "/healthz", timeout=1).status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Go ingest startup deadline exceeded: " + log_path.read_text()[-4000:])
            yield base_url
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)


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
