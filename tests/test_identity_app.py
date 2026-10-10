"""Actual product app identity, role and tenant integration, isolated PostgreSQL."""
import os
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from kairos_api.app import create_app
from kairos_api.identity import COOKIE
from kairos_api.settings import Settings


class PrivateTokens(dict):
    def __repr__(self):
        return "<private test session receipts>"


@pytest.fixture
def product(monkeypatch):
    database = os.environ.get("TEST_DATABASE_URL")
    if not database:
        pytest.skip("TEST_DATABASE_URL required for actual product identity checks")
    schema = "identity_app_" + uuid4().hex
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    url = make_conninfo(database, options=f"-c search_path={schema}")
    monkeypatch.setenv("KAIROS_ENV", "development")
    monkeypatch.setenv("KAIROS_OIDC_ISSUER", "https://identity.example/realms/kairos")
    monkeypatch.setenv("KAIROS_OIDC_CLIENT_SECRET", "isolated-test-confidential-secret-000001")
    monkeypatch.setenv("KAIROS_WEB_ORIGIN", "http://127.0.0.1:3100")
    app = create_app(Settings(url, {}, ["http://127.0.0.1:3100"], identity_mode="oidc"))
    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        repository = app.state.identity.repository
        with repository.connect() as connection:
            connection.execute("INSERT INTO kairos_memberships(subject,tenant_id,role) VALUES ('admin-a','tenant-a','admin'),('operator-a','tenant-a','operator'),('viewer-a','tenant-a','viewer'),('operator-b','tenant-b','operator')")
        tokens = PrivateTokens({subject: repository.create_session(subject, 3600) for subject in ("admin-a", "operator-a", "viewer-a", "operator-b")})
        yield client, tokens, repository
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def headers(tokens, subject="operator-a", origin="http://127.0.0.1:3100", key="identity-app-command"):
    return {"Cookie": f"{COOKIE}={tokens[subject]}", "Origin": origin, "Idempotency-Key": key}


def test_viewer_reads_but_cannot_enqueue(product):
    client, tokens, repository = product
    assert client.get("/api/jobs", headers=headers(tokens, "viewer-a")).status_code == 200
    assert client.get("/api/effects", headers=headers(tokens, "viewer-a")).status_code == 200
    response = client.post("/api/jobs", json={"runner": "reference"}, headers=headers(tokens, "viewer-a"))
    assert response.status_code == 403
    assert client.get("/api/jobs", headers=headers(tokens, "viewer-a")).json()["jobs"] == []


def test_operator_can_enqueue_but_cross_tenant_reads_denied(product):
    client, tokens, repository = product
    queued = client.post("/api/jobs", json={"runner": "reference"}, headers=headers(tokens))
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["id"]
    assert client.get(f"/api/jobs/{job_id}", headers=headers(tokens)).status_code == 200
    assert client.get(f"/api/jobs/{job_id}", headers=headers(tokens, "operator-b")).status_code == 404


def test_operator_cannot_approve_admin_can_and_identity_recorded(product):
    client, tokens, repository = product
    run = client.post("/api/runs", json={"scenario_id": "late-order-standard", "policy": "preserve", "publish": False}, headers=headers(tokens, key="run"))
    assert run.status_code == 201, run.text
    proposal = client.post(f'/api/runs/{run.json()["id"]}/proposal', headers=headers(tokens, key="proposal"))
    assert proposal.status_code == 201, proposal.text
    value = proposal.json()
    path = f'/api/effects/{value["id"]}/approve'
    assert client.post(path, json={"version": value["version"]}, headers=headers(tokens, key="deny-approve")).status_code == 403
    approved = client.post(path, json={"version": value["version"]}, headers=headers(tokens, "admin-a", key="approve"))
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved_by"] == "admin-a"
    assert approved.json()["state"] == "approved"


def test_cookie_mutation_wrong_origin_and_dev_bearer_fail_closed(product):
    client, tokens, repository = product
    assert client.post("/api/jobs", json={"runner": "reference"}, headers=headers(tokens, origin="https://evil.example")).status_code == 403
    assert client.post("/api/jobs", json={"runner": "reference"}, headers={"Cookie": f"{COOKIE}={tokens['operator-a']}", "Idempotency-Key": "missing-origin"}).status_code == 403
    assert client.get("/api/jobs", headers={"Authorization": "Bearer development-token-must-never-work"}).status_code == 401
    assert client.get("/api/jobs").status_code == 401


def test_membership_role_change_revokes_mutation_immediately(product):
    client, tokens, repository = product
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_memberships SET role='viewer' WHERE subject='operator-a'")
    assert client.post("/api/jobs", json={"runner": "reference"}, headers=headers(tokens)).status_code == 403
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_memberships SET active=false WHERE subject='operator-a'")
    assert client.get("/api/jobs", headers=headers(tokens)).status_code == 403


def test_production_settings_fail_without_oidc_and_drop_dev_tokens(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused/test")
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_IDENTITY_MODE", "development")
    monkeypatch.setenv("KAIROS_DEV_TOKEN", "valid-length-development-token-0000001")
    with pytest.raises(ValueError, match="OIDC"):
        Settings.from_environment()
    monkeypatch.setenv("KAIROS_IDENTITY_MODE", "oidc")
    assert Settings.from_environment().credentials == {}
