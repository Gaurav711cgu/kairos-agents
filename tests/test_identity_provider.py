"""Actual local Keycloak authorization-code flow, not provider mocks.

Opt in KAIROS_TEST_IDENTITY_PROVIDER=1 after scripts/setup_identity.py.
Uses generated synthetic credentials from ignored .runtime only.
"""
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from kairos_api.identity import COOKIE, IdentityConfig, IdentityRepository, install_identity


class PrivateCredentials(dict):
    def __repr__(self):
        return "<private synthetic identity credentials>"


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values["action"]


def provider_authorize(url, account):
    """Interact with real provider username/password page, preserving its cookies."""
    with httpx.Client(timeout=20, follow_redirects=True) as browser:
        page = browser.get(url)
        page.raise_for_status()
        parser = LoginForm()
        parser.feed(page.text)
        assert parser.action, "Provider login form unavailable"
        # Keycloak marks loopback cookies Secure. Real browsers accept them on
        # trustworthy loopback; httpx's cookie jar does not. Send only provider
        # loopback cookies explicitly in this protocol-level development check.
        provider_cookies = "; ".join(f"{item.name}={item.value}" for item in browser.cookies.jar
                                     if item.domain == "127.0.0.1" and item.path.startswith("/realms/kairos"))
        response = browser.post(parser.action, headers={"Cookie": provider_cookies}, data={"username": account["username"], "password": account["password"], "credentialId": ""}, follow_redirects=False)
        assert response.status_code == 302, "Provider did not issue authorization code"
        location = response.headers["location"]
        assert urlparse(location).path == "/api/auth/callback"
        return location


@pytest.fixture
def provider_client():
    if os.environ.get("KAIROS_TEST_IDENTITY_PROVIDER") != "1":
        pytest.skip("Enable real local provider integration with KAIROS_TEST_IDENTITY_PROVIDER=1")
    database = os.environ.get("TEST_DATABASE_URL")
    assert database
    local = PrivateCredentials(json.loads((Path(__file__).parents[1] / ".runtime/identity.local.json").read_text()))
    local["accounts"] = [PrivateCredentials(account) for account in local["accounts"]]
    schema = "identity_provider_" + uuid4().hex
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    repository = IdentityRepository(make_conninfo(database, options=f"-c search_path={schema}"))
    repository.initialize()
    with repository.connect() as connection:
        for account in local["accounts"]:
            if "tenant_id" in account:
                connection.execute("INSERT INTO kairos_memberships(subject,tenant_id,role) VALUES (%s,%s,%s)",
                                   (account["subject"], account["tenant_id"], account["role"]))
    config = IdentityConfig("http://127.0.0.1:8088/realms/kairos", "kairos-web", local["client_secret"],
                            "http://127.0.0.1:8100/api/auth/callback", "http://127.0.0.1:3100")
    app = FastAPI()
    install_identity(app, repository.database_url, config)
    with TestClient(app, base_url="http://127.0.0.1:8100", follow_redirects=False) as client:
        yield client, app, repository, local
    with psycopg.connect(database, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.mark.parametrize("account_index", [0, 1, 2])
def test_real_provider_pkce_nonce_login_membership_and_logout(provider_client, account_index):
    client, app, repository, local = provider_client
    account = local["accounts"][account_index]
    start = client.get("/api/auth/login", params={"return_to": "/workbench"})
    assert start.status_code == 302
    authorization = start.headers["location"]
    query = parse_qs(urlparse(authorization).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["nonce"] and query["state"]
    callback = provider_authorize(authorization, account)
    complete = client.get(callback)
    assert complete.status_code == 302, complete.text
    assert complete.headers["location"] == "http://127.0.0.1:3100/workbench"
    assert "HttpOnly" in complete.headers["set-cookie"]
    principal = client.get("/api/auth/me")
    assert principal.json() == {"subject": account["subject"], "tenant_id": account["tenant_id"], "role": account["role"]}
    assert "token" not in principal.text and "secret" not in principal.text
    assert client.get(callback).status_code == 400
    token = client.cookies.get(COOKIE)
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_memberships SET active=false WHERE subject=%s", (account["subject"],))
    assert client.get("/api/auth/me").status_code == 403
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_memberships SET active=true WHERE subject=%s", (account["subject"],))
    assert client.post("/api/auth/logout", headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"Origin": "http://127.0.0.1:3100"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_real_provider_valid_identity_without_membership_denied(provider_client):
    client, app, repository, local = provider_client
    start = client.get("/api/auth/login")
    callback = provider_authorize(start.headers["location"], local["accounts"][3])
    assert client.get(callback).status_code == 403
    assert client.get("/api/auth/me").status_code == 401
