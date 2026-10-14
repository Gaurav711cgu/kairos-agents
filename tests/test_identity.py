"""Identity boundary checks; temporary schemas, generated signing key, real provider optional."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import jwt
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from kairos_api.identity import (COOKIE, IdentityConfig, IdentityRepository, IdentityService,
                                 install_identity, require_identity_role)


@pytest.fixture
def repository():
    database = os.environ.get("TEST_DATABASE_URL")
    if not database:
        pytest.skip("TEST_DATABASE_URL required for PostgreSQL identity tests")
    schema = "identity_test_" + uuid4().hex
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    repository = IdentityRepository(make_conninfo(database, options=f"-c search_path={schema}"))
    repository.initialize()
    with repository.connect() as connection:
        connection.execute("INSERT INTO kairos_memberships(subject,tenant_id,role) VALUES ('subject-a','tenant-a','operator'),('subject-b','tenant-b','viewer')")
    yield repository
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def config():
    return IdentityConfig("https://identity.example/realms/kairos", "kairos-web", "test-client-secret-at-least24characters", "https://api.example/api/auth/callback", "https://web.example", True)


def test_hashed_session_membership_revocation_and_expiry(repository):
    token = repository.create_session("subject-a", 60)
    assert repository.session(token)["tenant_id"] == "tenant-a"
    with repository.connect() as connection:
        stored = connection.execute("SELECT session_hash FROM kairos_sessions").fetchone()["session_hash"]
        assert stored != token and len(stored) == 64
        connection.execute("UPDATE kairos_memberships SET active=false WHERE subject='subject-a'")
    with pytest.raises(HTTPException) as error:
        repository.session(token)
    assert error.value.status_code == 403
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_memberships SET active=true WHERE subject='subject-a'")
        connection.execute("UPDATE kairos_sessions SET expires_at=now()-interval '1 second'")
    with pytest.raises(HTTPException) as error:
        repository.session(token)
    assert error.value.status_code == 401


def test_state_is_bound_expiring_one_use(repository):
    repository.save_state("state", "verifier", "nonce", "binding", "/workbench")
    assert repository.consume_state("state", "binding")["verifier"] == "verifier"
    with pytest.raises(HTTPException):
        repository.consume_state("state", "binding")
    repository.save_state("state2", "verifier", "nonce", "binding", "/workbench")
    with pytest.raises(HTTPException):
        repository.consume_state("state2", "other-binding")
    assert repository.consume_state("state2", "binding")["nonce"] == "nonce"
    repository.save_state("expired", "verifier", "nonce", "binding", "/workbench")
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_login_states SET expires_at=now()-interval '1 second'")
    with pytest.raises(HTTPException):
        repository.consume_state("expired", "binding")


def test_cookie_origin_roles_and_logout(repository, config):
    app = FastAPI()
    principal = install_identity(app, repository.database_url, config)
    @app.post("/mutate")
    def mutate(request: Request):
        return require_identity_role(principal(request))
    session_a = repository.create_session("subject-a", 60)
    with TestClient(app, base_url="https://api.example") as client:
        assert client.get("/api/auth/me").status_code == 401
        client.cookies.set(COOKIE, session_a)
        assert client.get("/api/auth/me").json()["tenant_id"] == "tenant-a"
        assert client.get("/api/auth/me").headers["cache-control"] == "no-store"
        assert client.post("/mutate").status_code == 403
        assert client.post("/mutate", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/mutate", headers={"Origin": config.web_origin}).status_code == 200
        assert client.post("/api/auth/logout", headers={"Origin": config.web_origin}).status_code == 200
        with pytest.raises(HTTPException):
            repository.session(session_a)
    with pytest.raises(HTTPException) as error:
        require_identity_role({"role": "viewer"})
    assert error.value.status_code == 403


@pytest.fixture
def signing_service(repository, config):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public["kid"] = "test-key"
    service = IdentityService(config, repository)
    service._metadata = {"jwks_uri": "https://identity.example/keys"}
    service._jwks = {"keys": [public]}
    now = datetime.now(timezone.utc)
    claims = {"iss": config.issuer, "aud": config.client_id, "azp": config.client_id, "sub": "subject-a",
              "iat": now, "exp": now + timedelta(minutes=5), "nonce": "expected-nonce", "typ": "Bearer"}
    return service, key, claims


def test_verified_jwt_and_principal(signing_service):
    service, key, claims = signing_service
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    assert service.validate_token(token, nonce="expected-nonce")["sub"] == "subject-a"
    assert service.validate_token(token, access=True)["aud"] == "kairos-web"


@pytest.mark.parametrize("change", [
    {"iss": "https://other.example"}, {"aud": "other-client"}, {"exp": 1},
    {"iat": 9999999999}, {"azp": "other-client"}, {"sub": ""}, {"nonce": "wrong"}])
def test_wrong_claims_fail_closed(signing_service, change):
    service, key, claims = signing_service
    token = jwt.encode({**claims, **change}, key, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(HTTPException) as error:
        service.validate_token(token, nonce="expected-nonce")
    assert error.value.status_code == 401


def test_wrong_signature_algorithm_and_missing_membership(signing_service):
    service, key, claims = signing_service
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, other, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(HTTPException):
        service.validate_token(token)
    token = jwt.encode(claims, "long-secret-key-for-unaccepted-hmac", algorithm="HS256", headers={"kid": "test-key"})
    with pytest.raises(HTTPException):
        service.validate_token(token)
    with pytest.raises(HTTPException) as error:
        service.repository.membership("missing-subject")
    assert error.value.status_code == 403


def test_open_redirect_denied_and_secure_production_config(repository, config, monkeypatch):
    app = FastAPI()
    install_identity(app, repository.database_url, config)
    with TestClient(app) as client:
        for destination in ("https://evil.example/workbench", "//evil.example/workbench", "https://web.example/steal"):
            assert client.get("/api/auth/login", params={"return_to": destination}).status_code == 400
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_OIDC_ISSUER", "http://127.0.0.1:8088/realms/kairos")
    monkeypatch.setenv("KAIROS_OIDC_CLIENT_SECRET", "test-secret-longer-than24characters")
    with pytest.raises(ValueError, match="HTTPS"):
        IdentityConfig.from_environment()


def test_lazy_route_install_has_no_startup_database_access(repository, config):
    from kairos_api.identity import initialize_identity
    app = FastAPI()
    install_identity(app)
    count = len(app.routes)
    with TestClient(app) as client:
        assert client.get("/api/auth/me").status_code == 503
        app.state.identity = initialize_identity(repository.database_url, config)
        assert client.get("/api/auth/me").status_code == 401
        # Reinitializing service changes no router registration.
        app.state.identity = initialize_identity(repository.database_url, config)
        assert len(app.routes) == count


@pytest.mark.parametrize("audiences,authorized_party,accepted", [
    (["kairos-web", "other-resource"], None, False),
    (["kairos-web", "other-resource"], "other-client", False),
    (["kairos-web", "other-resource"], "kairos-web", True),
    (["kairos-web"], None, True),
    ("kairos-web", None, True),
])
def test_multiple_audience_authorized_party_binding(signing_service, audiences, authorized_party, accepted):
    service, key, claims = signing_service
    claims = {**claims, "aud": audiences}
    if authorized_party is None:
        claims.pop("azp")
    else:
        claims["azp"] = authorized_party
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    if accepted:
        assert service.validate_token(token, nonce="expected-nonce")["sub"] == "subject-a"
    else:
        with pytest.raises(HTTPException) as error:
            service.validate_token(token, nonce="expected-nonce")
        assert error.value.status_code == 401



def production_identity_environment(monkeypatch):
    monkeypatch.setenv("KAIROS_ENV", "production")
    monkeypatch.setenv("KAIROS_OIDC_ISSUER", "https://identity.example/realms/kairos")
    monkeypatch.setenv("KAIROS_OIDC_CLIENT_SECRET", "test-secret-longer-than24characters")
    monkeypatch.setenv("KAIROS_WEB_ORIGIN", "https://kairos.example")
    monkeypatch.setenv("KAIROS_OIDC_CALLBACK", "https://kairos.example/api/auth/callback")
    monkeypatch.setenv("KAIROS_AUTH_LOGIN_URL", "https://kairos.example/api/auth/login")


@pytest.mark.parametrize("name,value", [
    ("KAIROS_OIDC_CALLBACK", "https://api.kairos.example/api/auth/callback"),
    ("KAIROS_OIDC_CALLBACK", "https://kairos.example:8443/api/auth/callback"),
    ("KAIROS_OIDC_CALLBACK", "https://kairos.example/other-callback"),
    ("KAIROS_AUTH_LOGIN_URL", "https://api.kairos.example/api/auth/login"),
    ("KAIROS_AUTH_LOGIN_URL", "https://kairos.example/other-login"),
    ("KAIROS_WEB_ORIGIN", "https://kairos.example/path"),
])
def test_production_rejects_split_origin_and_wrong_identity_routes(monkeypatch, name, value):
    production_identity_environment(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        IdentityConfig.from_environment()


def test_production_accepts_shared_public_origin_and_default_https_port(monkeypatch):
    production_identity_environment(monkeypatch)
    monkeypatch.setenv("KAIROS_OIDC_CALLBACK", "https://kairos.example:443/api/auth/callback")
    assert IdentityConfig.from_environment().secure
    monkeypatch.delenv("KAIROS_AUTH_LOGIN_URL")
    assert IdentityConfig.from_environment().secure
