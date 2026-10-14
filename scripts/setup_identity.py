"""Provision isolated local Keycloak and synthetic memberships; prints no secrets.

Run after starting official Keycloak26.8.0 with .runtime/keycloak-bootstrap.env.
Development credentials remain in mode0600 .runtime/identity.local.json.
"""
from pathlib import Path
import json
import os
import secrets
import time

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"


def local_env(path):
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))


def main():
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    path = RUNTIME / "identity.local.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = {"admin_password": secrets.token_urlsafe(32), "client_secret": secrets.token_urlsafe(40),
                "accounts": [{"username": "kairos-builder", "password": secrets.token_urlsafe(24), "tenant_id": "local-studio", "role": "admin"},
                             {"username": "kairos-other", "password": secrets.token_urlsafe(24), "tenant_id": "other-studio", "role": "operator"},
                             {"username": "kairos-viewer", "password": secrets.token_urlsafe(24), "tenant_id": "local-studio", "role": "viewer"},
                             {"username": "kairos-unassigned", "password": secrets.token_urlsafe(24)}]}
        path.write_text(json.dumps(data, indent=2) + "\n")
        path.chmod(0o600)
    bootstrap = RUNTIME / "keycloak-bootstrap.env"
    bootstrap.write_text("KC_BOOTSTRAP_ADMIN_USERNAME=kairos-admin\nKC_BOOTSTRAP_ADMIN_PASSWORD=" + data["admin_password"] + "\n")
    bootstrap.chmod(0o600)
    if os.environ.get("KAIROS_IDENTITY_PREPARE_ONLY") == "1":
        print("Prepared ignored provider bootstrap configuration.")
        return
    base = "http://127.0.0.1:8088"
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for attempt in range(60):
            try:
                response = client.post(base + "/realms/master/protocol/openid-connect/token", data={
                    "grant_type": "password", "client_id": "admin-cli", "username": "kairos-admin", "password": data["admin_password"]})
                response.raise_for_status()
                break
            except (httpx.HTTPError, ValueError):
                if attempt == 59:
                    raise RuntimeError("Local identity provider not ready; inspect container status.") from None
                time.sleep(1)
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        realm = base + "/admin/realms/kairos"
        exists = client.get(realm)
        if exists.status_code == 404:
            response = client.post(base + "/admin/realms", json={"realm": "kairos", "enabled": True,
                "sslRequired": "none", "registrationAllowed": False, "resetPasswordAllowed": False,
                "loginWithEmailAllowed": False, "bruteForceProtected": True})
            response.raise_for_status()
        else:
            exists.raise_for_status()
        spec = {"clientId": "kairos-web", "enabled": True, "protocol": "openid-connect", "publicClient": False,
                "secret": data["client_secret"], "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False, "redirectUris": ["http://127.0.0.1:8100/api/auth/callback"],
                "webOrigins": ["http://127.0.0.1:3100"], "attributes": {"pkce.code.challenge.method": "S256"},
                "protocolMappers": [{"name": "kairos-audience", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
                    "config": {"included.client.audience": "kairos-web", "id.token.claim": "false", "access.token.claim": "true"}}]}
        response = client.get(realm + "/clients", params={"clientId": "kairos-web"})
        response.raise_for_status()
        existing = response.json()
        response = client.put(realm + "/clients/" + existing[0]["id"], json=spec) if existing else client.post(realm + "/clients", json=spec)
        response.raise_for_status()
        for account in data["accounts"]:
            response = client.get(realm + "/users", params={"username": account["username"], "exact": "true"})
            response.raise_for_status()
            found = response.json()
            if not found:
                response = client.post(realm + "/users", json={"username": account["username"], "enabled": True,
                    "emailVerified": True, "email": account["username"] + "@example.invalid", "firstName": "Synthetic", "lastName": "Builder",
                    "credentials": [{"type": "password", "value": account["password"], "temporary": False}]})
                response.raise_for_status()
                response = client.get(realm + "/users", params={"username": account["username"], "exact": "true"})
                response.raise_for_status()
                found = response.json()
            account["subject"] = found[0]["id"]
            response = client.put(realm + "/users/" + account["subject"], json={"username": account["username"],
                "enabled": True, "emailVerified": True, "email": account["username"] + "@example.invalid",
                "firstName": "Synthetic", "lastName": "Builder", "requiredActions": []})
            response.raise_for_status()
    env = local_env(ROOT / ".env.kairos.local")
    database_url = os.environ.get("DATABASE_URL", env["DATABASE_URL"])
    from kairos_api.identity import IdentityRepository
    from kairos_api.migrations import apply
    apply(database_url)
    IdentityRepository(database_url).initialize()
    with psycopg.connect(database_url) as connection:
        for account in data["accounts"]:
            if "tenant_id" in account:
                connection.execute("INSERT INTO kairos_memberships(subject,tenant_id,role,active) VALUES (%s,%s,%s,true) ON CONFLICT(subject) DO UPDATE SET tenant_id=excluded.tenant_id,role=excluded.role,active=true,updated_at=now()",
                                   (account["subject"], account["tenant_id"], account["role"]))
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o600)
    identity_env = RUNTIME / "identity.env"
    identity_env.write_text("KAIROS_OIDC_ISSUER=http://127.0.0.1:8088/realms/kairos\nKAIROS_OIDC_CLIENT_ID=kairos-web\nKAIROS_OIDC_CLIENT_SECRET=" + data["client_secret"] + "\nKAIROS_OIDC_CALLBACK=http://127.0.0.1:8100/api/auth/callback\nKAIROS_WEB_ORIGIN=http://127.0.0.1:3100\nKAIROS_IDENTITY_MODE=oidc\n")
    identity_env.chmod(0o600)
    print("Provisioned real local OIDC provider, confidential PKCE client, and three synthetic memberships. Secrets saved privately.")


if __name__ == "__main__":
    main()
