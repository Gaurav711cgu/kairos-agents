"""Provision isolated reviewer PostgreSQL/OIDC and import genuine published captures."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

import httpx
import psycopg
from psycopg.types.json import Jsonb
from kairos_api.identity import IdentityRepository
from kairos_api.investigations.repository import InvestigationRepository
from scripts.reviewer_evidence import digest, validate_package
from scripts.reviewer_runtime import LABEL, docker_inspect, ensure_runtime, private_json, require_owned_resource, resource_names, require_ports

POSTGRES = "postgres:18@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336"
KEYCLOAK = "quay.io/keycloak/keycloak:26.8.0@sha256:27b3230fbabb8c9ff3c66c864cf09dcd8a41aca82e5100679d109ef0eeb05741"


def private_text(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(text)
    path.chmod(0o600)


def credentials(runtime):
    path = runtime / "identity.local.json"
    if path.exists():
        data = json.loads(path.read_text()); path.chmod(0o600)
        return data
    data = {"admin_password": secrets.token_urlsafe(32), "postgres_password": secrets.token_urlsafe(32),
        "client_secret": secrets.token_urlsafe(40), "accounts": [
            {"username": "reviewer-admin", "password": secrets.token_urlsafe(24), "tenant_id": "member005", "role": "admin"},
            {"username": "reviewer-viewer", "password": secrets.token_urlsafe(24), "tenant_id": "member005", "role": "viewer"},
            {"username": "reviewer-operator", "password": secrets.token_urlsafe(24), "tenant_id": "other005", "role": "operator"},
            {"username": "reviewer-archive", "password": secrets.token_urlsafe(24), "tenant_id": "archive005", "role": "admin"},
            {"username": "reviewer-unassigned", "password": secrets.token_urlsafe(24)}]}
    private_json(path, data)
    return data


def provision_container(runtime, owner, kind, image, port, volume_kind, destination, env_file, arguments):
    names = resource_names(runtime); volume = docker_inspect("volume", names[volume_kind])
    if volume:
        require_owned_resource(volume, owner, "volume")
    else:
        subprocess.run(["docker", "volume", "create", "--label", LABEL + "=" + owner, names[volume_kind]], check=True, capture_output=True)
    container = docker_inspect("container", names[kind]); fingerprint = hashlib.sha256(env_file.read_bytes()).hexdigest()
    if container:
        require_owned_resource(container, owner, "container")
        labels = container["Config"]["Labels"]; binds = container["HostConfig"].get("PortBindings", {})
        key = "5432/tcp" if kind == "postgres" else "8080/tcp"
        mounts = {item.get("Destination"): item.get("Name") for item in container["Mounts"]}
        if (labels.get("io.kairos.reviewer.configuration") != fingerprint or container["Config"]["Image"] != image
                or binds.get(key) != [{"HostIp": "127.0.0.1", "HostPort": str(port)}] or mounts.get(destination) != names[volume_kind]):
            raise RuntimeError("Owned container configuration changed; inspect it before reuse")
        if not container["State"]["Running"]:
            require_ports([port]); subprocess.run(["docker", "start", names[kind]], capture_output=True, check=True)
    else:
        require_ports([port]); inside = "5432" if kind == "postgres" else "8080"
        command = ["docker", "run", "-d", "--name", names[kind], "--label", LABEL + "=" + owner,
            "--label", "io.kairos.reviewer.configuration=" + fingerprint, "--cpus=2", "--memory=" + ("512m" if kind == "postgres" else "1g"),
            "--env-file", str(env_file), "-p", f"127.0.0.1:{port}:{inside}", "-v", names[volume_kind] + ":" + destination, image, *arguments]
        subprocess.run(command, capture_output=True, check=True)
    return names[kind]


def identity(runtime, data, database):
    base = "http://127.0.0.1:8090"
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        for _ in range(120):
            try:
                response = client.post(base + "/realms/master/protocol/openid-connect/token", data={"grant_type": "password",
                    "client_id": "admin-cli", "username": "reviewer-admin", "password": data["admin_password"]})
                response.raise_for_status(); break
            except (httpx.HTTPError, ValueError): time.sleep(1)
        else: raise RuntimeError("Reviewer identity provider startup deadline exceeded")
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]; realm = base + "/admin/realms/kairos"
        response = client.get(realm)
        if response.status_code == 404:
            client.post(base + "/admin/realms", json={"realm": "kairos", "enabled": True, "sslRequired": "none",
                "registrationAllowed": False, "resetPasswordAllowed": False, "loginWithEmailAllowed": False, "bruteForceProtected": True}).raise_for_status()
        else: response.raise_for_status()
        spec = {"clientId": "kairos-web", "enabled": True, "protocol": "openid-connect", "publicClient": False,
            "secret": data["client_secret"], "standardFlowEnabled": True, "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False,
            "redirectUris": ["http://127.0.0.1:8310/api/auth/callback"], "webOrigins": ["http://127.0.0.1:3310"],
            "attributes": {"pkce.code.challenge.method": "S256"}, "protocolMappers": [{"name": "kairos-audience", "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper", "config": {"included.client.audience": "kairos-web", "id.token.claim": "false", "access.token.claim": "true"}}]}
        response = client.get(realm + "/clients", params={"clientId": "kairos-web"}); response.raise_for_status(); found = response.json()
        response = client.put(realm + "/clients/" + found[0]["id"], json=spec) if found else client.post(realm + "/clients", json=spec)
        response.raise_for_status()
        for account in data["accounts"]:
            response = client.get(realm + "/users", params={"username": account["username"], "exact": "true"}); response.raise_for_status(); found = response.json()
            if not found:
                client.post(realm + "/users", json={"username": account["username"], "enabled": True, "emailVerified": True,
                    "email": account["username"] + "@example.invalid", "firstName": "Synthetic", "lastName": "Reviewer",
                    "credentials": [{"type": "password", "value": account["password"], "temporary": False}]}).raise_for_status()
                response = client.get(realm + "/users", params={"username": account["username"], "exact": "true"}); response.raise_for_status(); found = response.json()
            account["subject"] = found[0]["id"]
            client.put(realm + "/users/" + account["subject"], json={"username": account["username"], "enabled": True, "emailVerified": True,
                "email": account["username"] + "@example.invalid", "firstName": "Synthetic", "lastName": "Reviewer", "requiredActions": []}).raise_for_status()
    repository = IdentityRepository(database); repository.initialize()
    with repository.connect() as connection:
        for account in data["accounts"]:
            if "tenant_id" in account:
                connection.execute("""INSERT INTO kairos_memberships(subject,tenant_id,role,active) VALUES (%s,%s,%s,true)
                    ON CONFLICT(subject) DO UPDATE SET tenant_id=excluded.tenant_id,role=excluded.role,active=true,updated_at=now()""",
                    (account["subject"], account["tenant_id"], account["role"]))
    private_json(runtime / "identity.local.json", data)


def import_published(runtime, database, evidence):
    records, blobs = validate_package(evidence); target = runtime / "blobs"; target.mkdir(exist_ok=True)
    for key, raw in blobs.items():
        path = target / key
        if path.is_symlink(): raise ValueError("Reviewer artifact path is a symlink")
        if path.exists() and path.read_bytes() != raw: raise ValueError("Existing reviewer artifact has different bytes")
        if not path.exists():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output: output.write(raw); output.flush(); os.fsync(output.fileno())
    descriptor = os.open(target, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    repository = InvestigationRepository(database, target); repository.initialize()
    fields = ["id", "task_id", "task_snapshot", "task_digest", "configuration", "config_snapshot", "config_digest", "registry_version",
        "status", "outcome", "summary", "published", "created_at", "updated_at", "started_at", "deadline_at", "cancel_requested",
        "claims", "model_calls", "patch_count", "check_count"]
    # The package stores original public rows. Import identities are separate durable commands, never reconstructed agent results.
    with repository.connect() as connection:
        connection.execute("SET LOCAL synchronous_commit=on")
        for identifier, record in records.items():
            existing = connection.execute("SELECT tenant_id FROM kairos_investigations WHERE id=%s", (identifier,)).fetchone()
            if existing:
                if existing["tenant_id"] != "archive005": raise ValueError("Investigation identifier belongs to another tenant")
                current = repository.read(identifier, "archive005")
                if (any(current[field] != record[field] for field in fields if field != "registry_version")
                        or current["steps"] != record["steps"]
                        or sorted(current["artifacts"], key=lambda item: item["sha256"]) != sorted(record["artifacts"], key=lambda item: item["sha256"])):
                    raise ValueError("Previously imported evidence differs from package")
                continue
            values = dict(record); values["registry_version"] = record.get("registry_version", "repository-cases-v1")
            values["task_snapshot"] = Jsonb(values["task_snapshot"]); values["config_snapshot"] = Jsonb(values["config_snapshot"])
            connection.execute("INSERT INTO kairos_investigations (tenant_id,command_key,command_digest," + ",".join(fields) + ") VALUES (%s,%s,%s," + ",".join(["%s"] * len(fields)) + ")",
                ["archive005", "import005:" + identifier, digest({"import_record_sha256": digest(record)})] + [values[field] for field in fields])
            for step in record["steps"]:
                connection.execute("""INSERT INTO kairos_investigation_steps
                    (investigation_id,seq,kind,name,state,request,result,started_at,captured_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [identifier, step["seq"], step["kind"], step["name"], step["state"], Jsonb(step["request"]),
                     Jsonb(step["result"]) if step["result"] is not None else None, step["started_at"], step["captured_at"]])
            for artifact in record["artifacts"]:
                connection.execute("INSERT INTO kairos_investigation_artifacts VALUES (%s,%s,%s)", (identifier, artifact["sha256"], artifact["bytes"]))
        for identifier, record in records.items():
            parent = record.get("parent_id")
            if parent is not None and parent not in records: raise ValueError("Published evidence has a parent outside the package")
            connection.execute("UPDATE kairos_investigations SET parent_id=%s WHERE id=%s AND tenant_id='archive005'", (parent, identifier))
    for identifier in records:
        if not repository.read(identifier, "archive005")["integrity"]["verified"]:
            raise ValueError("Imported investigation failed application integrity checks")
    private_json(runtime / "import-receipt.json", {"records": len(records), "artifact_objects": len(blobs), "tenant": "archive005",
        "ids_and_timestamps_preserved": True, "captured_bytes_preserved": True, "inference_calls": 0, "passed": True})


def prepare(runtime, evidence):
    owner = ensure_runtime(runtime)["owner"]; data = credentials(runtime)
    private_text(runtime / "postgres.env", "POSTGRES_DB=reviewer005\nPOSTGRES_USER=reviewer\nPOSTGRES_PASSWORD=" + data["postgres_password"] + "\n")
    private_text(runtime / "keycloak.env", "KC_BOOTSTRAP_ADMIN_USERNAME=reviewer-admin\nKC_BOOTSTRAP_ADMIN_PASSWORD=" + data["admin_password"] + "\nJAVA_OPTS_KC_HEAP=-Xms128m -Xmx512m\n")
    provision_container(runtime, owner, "postgres", POSTGRES, 55434, "pgdata", "/var/lib/postgresql", runtime / "postgres.env", [])
    database = "postgresql://reviewer:" + data["postgres_password"] + "@127.0.0.1:55434/reviewer005"
    for _ in range(90):
        try:
            with psycopg.connect(database, connect_timeout=2) as connection:
                if connection.execute("SHOW fsync").fetchone()[0] != "on": raise RuntimeError("Reviewer database must keep fsync enabled")
            break
        except psycopg.Error: time.sleep(1)
    else: raise RuntimeError("Reviewer PostgreSQL startup deadline exceeded")
    from kairos_api.migrations import apply, backfill
    apply(database); backfill(database)
    if "runtime_database_password" not in data:
        data["runtime_database_password"] = secrets.token_urlsafe(32)
        private_json(runtime / "identity.local.json", data)
    from psycopg import sql
    with psycopg.connect(database, autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='reviewer_runtime'").fetchone():
            connection.execute(sql.SQL("CREATE ROLE reviewer_runtime LOGIN PASSWORD {}").format(sql.Literal(data["runtime_database_password"])))
        connection.execute("ALTER ROLE reviewer_runtime SET lock_timeout='2s'")
        connection.execute("ALTER ROLE reviewer_runtime SET statement_timeout='15s'")
        connection.execute("ALTER ROLE reviewer_runtime SET idle_in_transaction_session_timeout='30s'")
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.execute("GRANT USAGE ON SCHEMA public TO reviewer_runtime")
        connection.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO reviewer_runtime")
        connection.execute("REVOKE ALL ON kairos_schema_migrations,kairos_data_backfills FROM reviewer_runtime")
        connection.execute("GRANT SELECT ON kairos_schema_migrations,kairos_data_backfills TO reviewer_runtime")
    runtime_database = "postgresql://reviewer_runtime:" + data["runtime_database_password"] + "@127.0.0.1:55434/reviewer005"
    provision_container(runtime, owner, "keycloak", KEYCLOAK, 8090, "kcdata", "/opt/keycloak/data", runtime / "keycloak.env",
        ["start-dev", "--http-port=8080", "--hostname=http://127.0.0.1:8090"])
    identity(runtime, data, database); import_published(runtime, database, evidence)
    private_text(runtime / "migration.env", "KAIROS_MIGRATION_DATABASE_URL=" + database + "\nTEST_DATABASE_URL=" + database + "\n")
    environment = {"DATABASE_URL": runtime_database, "KAIROS_ENV": "development", "KAIROS_IDENTITY_MODE": "oidc",
        "KAIROS_OIDC_ISSUER": "http://127.0.0.1:8090/realms/kairos", "KAIROS_OIDC_CLIENT_ID": "kairos-web", "KAIROS_OIDC_CLIENT_SECRET": data["client_secret"],
        "KAIROS_OIDC_CALLBACK": "http://127.0.0.1:8310/api/auth/callback", "KAIROS_WEB_ORIGIN": "http://127.0.0.1:3310", "KAIROS_CORS_ORIGINS": "http://127.0.0.1:3310",
        "KAIROS_API_URL": "http://127.0.0.1:8310", "KAIROS_AUTH_LOGIN_URL": "http://127.0.0.1:8310/api/auth/login", "KAIROS_BLOB_DIR": str(runtime / "blobs"),
        "KAIROS_INVESTIGATION_ROOT": str(runtime / "investigations"), "KAIROS_EVIDENCE_MODE": "live", "KAIROS_REVIEWER_RUNTIME": str(runtime)}
    (runtime / "investigations").mkdir(exist_ok=True)
    private_text(runtime / "application.env", "".join(key + "=" + value + "\n" for key, value in environment.items()))
    print("Provisioned isolated PostgreSQL and OIDC. Published captures retain original IDs and bytes.", flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["prepare"])
    parser.add_argument("--runtime", required=True); parser.add_argument("--evidence", required=True); args = parser.parse_args()
    prepare(Path(args.runtime).resolve(), Path(args.evidence).resolve())


if __name__ == "__main__": main()
