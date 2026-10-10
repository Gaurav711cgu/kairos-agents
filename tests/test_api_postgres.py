"""Real PostgreSQL tests. Each test owns a temporary schema, never product data."""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
import pytest

from kairos_api.app import create_app
from kairos_api.repository import RunRepository
from kairos_api.settings import Settings

TOKEN_A = "test-only-alpha-credential-00000001"
TOKEN_B = "test-only-beta-credential-000000002"
COMMAND = {"scenario_id": "late-order-exception", "policy": "compact", "publish": True}


@pytest.fixture
def repository():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for PostgreSQL integration tests")
    schema = "kairos_test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    repository = RunRepository(make_conninfo(url, options=f"-c search_path={schema}"))
    repository.initialize()
    yield repository
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def client(repository):
    settings = Settings(repository.database_url, {TOKEN_A: "tenant-a", TOKEN_B: "tenant-b"}, ["http://localhost:3100"])
    with TestClient(create_app(settings, repository)) as client:
        yield client


def headers(key="test-command", token=TOKEN_A):
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def test_commit_visible_to_new_connection_before_http_success_and_restart(client, repository):
    response = client.post("/api/runs", json=COMMAND, headers=headers())
    assert response.status_code == 201
    run = response.json()
    with repository.connect() as connection:
        assert connection.execute("SELECT count(*) AS count FROM kairos_runs").fetchone()["count"] == 1
        assert connection.execute("SELECT count(*) AS count FROM kairos_events").fetchone()["count"] == 7
    restarted = RunRepository(repository.database_url)
    assert restarted.read(run["id"], tenant_id="tenant-a")["decision"]["refund_cents"] == 480
    assert run["integrity"]["verified"] is True


def test_idempotent_retry_and_conflicting_payload(client, repository):
    first = client.post("/api/runs", json=COMMAND, headers=headers())
    retry = client.post("/api/runs", json=COMMAND, headers=headers())
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    conflict = client.post("/api/runs", json={**COMMAND, "policy": "preserve"}, headers=headers())
    assert conflict.status_code == 409
    assert len(repository.public_list()) == 1


def test_concurrent_duplicate_command_creates_one_run(repository):
    def create(_):
        return repository.create("tenant-a", "same-concurrent-key", COMMAND)["id"]
    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(create, range(8)))
    assert len(set(ids)) == 1
    assert len(repository.public_list()) == 1


def test_tenant_identity_is_credential_bound_and_private_reads_denied(client):
    private = {**COMMAND, "publish": False}
    response = client.post("/api/runs", json=private, headers=headers())
    run_id = response.json()["id"]
    assert client.get(f"/api/runs/{run_id}", headers=headers(token=TOKEN_B)).status_code == 404
    assert client.get(f"/api/public/incidents/{run_id}").status_code == 404
    assert client.post(f"/api/runs/{run_id}/fork", json={"policy": "preserve"}, headers=headers("fork", TOKEN_B)).status_code == 404
    spoofed = client.get(f"/api/runs/{run_id}", headers={**headers(token=TOKEN_B), "X-Tenant-ID": "tenant-a"})
    assert spoofed.status_code == 404
    assert client.post("/api/runs", json={**COMMAND, "tenant_id": "tenant-a"}, headers=headers("injection")).status_code == 422


def test_auth_and_idempotency_required_for_mutations(client):
    assert client.post("/api/runs", json=COMMAND).status_code == 401
    assert client.post("/api/runs", json=COMMAND, headers=headers(token="invalid")).status_code == 401
    assert client.post("/api/runs", json=COMMAND, headers={"Authorization": f"Bearer {TOKEN_A}"}).status_code == 400


def test_public_response_sanitizes_identity_and_keeps_model_provenance(client):
    response = client.post("/api/runs", json=COMMAND, headers=headers())
    public = client.get(f"/api/public/incidents/{response.json()['id']}")
    assert public.status_code == 200
    text = public.text
    assert "tenant-a" not in text and TOKEN_A not in text
    assert public.json()["configuration"]["model"] is None
    assert public.json()["integrity"]["verified"] is True
    assert client.get("/api/public/evidence").json()["run_count"] == 1


def test_fork_reexecutes_in_isolation_preserves_publication_and_is_idempotent(client):
    parent = client.post("/api/runs", json=COMMAND, headers=headers()).json()
    path = f"/api/runs/{parent['id']}/fork"
    fork = client.post(path, json={"policy": "preserve"}, headers=headers("fork")).json()
    retry = client.post(path, json={"policy": "preserve"}, headers=headers("fork")).json()
    assert fork["id"] == retry["id"] and fork["id"] != parent["id"]
    assert fork["grade"]["passed"] is True and fork["decision"]["refund_cents"] == 0
    assert fork["lineage"]["mode"] == "fresh-isolated-scenario-rerun"
    assert client.get(f"/api/public/incidents/{fork['id']}").status_code == 200
    assert client.get(f"/api/public/incidents/{parent['id']}").json()["grade"]["passed"] is False


def test_corruption_detected_and_fork_rejected(client, repository):
    run = client.post("/api/runs", json=COMMAND, headers=headers()).json()
    event = run["events"][3]
    event["payload"]["omitted_ids"] = []
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_events SET event=%s WHERE run_id=%s AND seq=4", (Jsonb(event), run["id"]))
    observed = client.get(f"/api/public/incidents/{run['id']}").json()
    assert observed["integrity"]["verified"] is False
    assert client.post(f"/api/runs/{run['id']}/fork", json={"policy": "preserve"}, headers=headers("fork")).status_code == 409
    assert client.get("/api/public/evidence").json()["integrity_verified_runs"] == 0


def test_partial_write_failure_rolls_back_receipt_run_and_events(repository, monkeypatch):
    original = repository._insert
    def fail_after_insert(connection, tenant_id, published, document):
        original(connection, tenant_id, published, document)
        raise RuntimeError("injected failure before transaction commit")
    monkeypatch.setattr(repository, "_insert", fail_after_insert)
    with pytest.raises(RuntimeError, match="injected failure"):
        repository.create("tenant-a", "rollback-key", COMMAND)
    with repository.connect() as connection:
        for table in ("kairos_runs", "kairos_events", "kairos_commands"):
            assert connection.execute(sql.SQL("SELECT count(*) AS count FROM {}").format(sql.Identifier(table))).fetchone()["count"] == 0
    monkeypatch.setattr(repository, "_insert", original)
    assert repository.create("tenant-a", "rollback-key", COMMAND)["integrity"]["verified"]


def test_document_corruption_detected_and_unknown_public_fields_omitted(client, repository):
    run = client.post("/api/runs", json=COMMAND, headers=headers()).json()
    with repository.connect() as connection:
        row = connection.execute("SELECT document FROM kairos_runs WHERE id=%s", (run["id"],)).fetchone()
        document = row["document"]
        document["private_note"] = "must not become public"
        connection.execute("UPDATE kairos_runs SET document=%s WHERE id=%s", (Jsonb(document), run["id"]))
    public = client.get(f"/api/public/incidents/{run['id']}").json()
    assert "private_note" not in public
    assert public["integrity"]["verified"] is False


def test_transaction_enforces_synchronous_commit_even_if_database_default_is_off(repository):
    original_connect = repository.connect
    def connect_with_async_default():
        connection = original_connect()
        connection.execute("SET synchronous_commit = off")
        connection.commit()
        return connection
    repository.connect = connect_with_async_default
    original_insert = repository._insert
    def inspect_setting(connection, tenant_id, published, document):
        assert connection.execute("SHOW synchronous_commit").fetchone()["synchronous_commit"] == "on"
        original_insert(connection, tenant_id, published, document)
    repository._insert = inspect_setting
    assert repository.create("tenant-a", "durability-check", COMMAND)["integrity"]["verified"]


def test_storage_sequence_corruption_is_detected(client, repository):
    run = client.post("/api/runs", json=COMMAND, headers=headers()).json()
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_events SET seq=8 WHERE run_id=%s AND seq=7", (run["id"],))
    assert not client.get(f"/api/public/incidents/{run['id']}").json()["integrity"]["verified"]


def test_whole_valid_chain_cannot_be_attached_to_another_run(client, repository):
    first = client.post("/api/runs", json=COMMAND, headers=headers()).json()
    second = client.post("/api/runs", json={**COMMAND, "policy": "preserve"}, headers=headers("second")).json()
    with repository.connect() as connection:
        for event in second["events"]:
            connection.execute("UPDATE kairos_events SET event=%s WHERE run_id=%s AND seq=%s",
                               (Jsonb(event), first["id"], event["seq"]))
        connection.execute("UPDATE kairos_runs SET event_head=%s WHERE id=%s",
                           (second["events"][-1]["event_hash"], first["id"]))
    observed = client.get(f"/api/public/incidents/{first['id']}").json()
    assert observed["integrity"]["verified"] is False
