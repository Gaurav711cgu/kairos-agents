"""PostgreSQL command boundary: write receipts, events and run commit together."""
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from kairos_api.integrity import INTEGRITY_SCOPE, request_digest, verify_events
from kairos_api.runner import execute_scenario


class MissingRun(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


class CorruptRun(Exception):
    pass


PUBLIC_DETAIL_KEYS = {"task", "scenario", "context_blocks", "events", "decision", "grade",
                      "duration_ms", "configuration", "lineage", "integrity"}

SUMMARY_KEYS = ("id", "slug", "title", "summary", "scenario_id", "policy", "status", "created_at",
                "event_count", "provenance", "parent_run_id", "grade_passed")


class RunRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def connect(self):
        # A bounded timeout prevents hanging indefinitely on a missing database.
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5)

    @staticmethod
    def _enforce_durability(connection) -> None:
        connection.execute("SET LOCAL synchronous_commit = on")
        if connection.execute("SHOW fsync").fetchone()["fsync"] != "on":
            raise psycopg.OperationalError("PostgreSQL fsync must be enabled.")

    def initialize(self) -> None:
        """Verify the applied schema; setup owns all schema and data changes."""
        from kairos_api.migrations import verify
        with self.connect() as connection:
            verify(connection)

    def health(self) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 AS alive").fetchone()["alive"] == 1

    def create(self, tenant_id: str, key: str, command: dict, parent_run_id: str | None = None) -> dict:
        digest = request_digest({"command": command, "parent_run_id": parent_run_id})
        with self.connect() as connection:
            self._enforce_durability(connection)
            # Conflicting concurrent INSERTs wait for the winning transaction.
            connection.execute(
                "INSERT INTO kairos_commands (tenant_id, idempotency_key, request_digest) VALUES (%s, %s, %s) "
                "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING", (tenant_id, key, digest))
            receipt = connection.execute(
                "SELECT request_digest, run_id FROM kairos_commands WHERE tenant_id=%s AND idempotency_key=%s FOR UPDATE",
                (tenant_id, key)).fetchone()
            if receipt["request_digest"] != digest:
                raise IdempotencyConflict("Idempotency key already belongs to a different command.")
            if receipt["run_id"]:
                result = self._read(connection, str(receipt["run_id"]), tenant_id=tenant_id)
                if not result["integrity"]["verified"]:
                    raise CorruptRun("Stored command result failed local consistency checks.")
            else:
                published = command.get("publish", False)
                scenario_id = command.get("scenario_id")
                if parent_run_id:
                    parent = self._read(connection, parent_run_id, tenant_id=tenant_id)
                    if not parent["integrity"]["verified"]:
                        raise CorruptRun("Parent run failed local consistency checks.")
                    scenario_id = parent["scenario_id"]
                    published = connection.execute("SELECT published FROM kairos_runs WHERE id=%s", (parent_run_id,)).fetchone()["published"]
                document = execute_scenario(scenario_id, command["policy"], parent_run_id)
                self._insert(connection, tenant_id, published, document)
                connection.execute("UPDATE kairos_commands SET run_id=%s WHERE tenant_id=%s AND idempotency_key=%s",
                                   (document["id"], tenant_id, key))
                result = self._read(connection, document["id"], tenant_id=tenant_id)
        # psycopg context manager has successfully committed before result escapes.
        return result

    def _insert(self, connection, tenant_id: str, published: bool, document: dict) -> None:
        stored = deepcopy(document)
        events = stored.pop("events")
        connection.execute(
            "INSERT INTO kairos_runs (id, tenant_id, published, document, document_hash, event_count, event_head) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (stored["id"], tenant_id, published, Jsonb(stored), request_digest(stored), len(events), events[-1]["event_hash"]))
        with connection.cursor() as cursor:
            cursor.executemany("INSERT INTO kairos_events (run_id, seq, event) VALUES (%s, %s, %s)",
                               [(stored["id"], event["seq"], Jsonb(event)) for event in events])

    def _read(self, connection, run_id: str, tenant_id: str | None = None, public: bool = False) -> dict:
        try:
            UUID(run_id)
        except ValueError:
            raise MissingRun("Run not found.") from None
        condition = "published=true" if public else "tenant_id=%s"
        params = (run_id,) if public else (run_id, tenant_id)
        row = connection.execute(f"SELECT * FROM kairos_runs WHERE id=%s AND {condition}", params).fetchone()
        if not row:
            raise MissingRun("Run not found.")
        event_rows = connection.execute("SELECT seq, event FROM kairos_events WHERE run_id=%s ORDER BY seq", (run_id,)).fetchall()
        events = [row["event"] for row in event_rows]
        sequence_matches = all(row["seq"] == row["event"].get("seq") for row in event_rows)
        document = row["document"]
        verified = (document.get("id") == str(row["id"]) and sequence_matches and
                    request_digest(document) == row["document_hash"] and
                    document.get("event_count") == row["event_count"] and
                    verify_events(events, row["event_count"], row["event_head"], str(row["id"])))
        result = {**document, "events": events, "integrity": {"verified": verified, "scope": INTEGRITY_SCOPE}}
        if public:
            allowed = PUBLIC_DETAIL_KEYS | set(SUMMARY_KEYS)
            return {key: value for key, value in result.items() if key in allowed}
        return result

    def read(self, run_id: str, tenant_id: str | None = None, public: bool = False) -> dict:
        with self.connect() as connection:
            return self._read(connection, run_id, tenant_id=tenant_id, public=public)

    def public_list(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT document FROM kairos_runs WHERE published=true ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{key: row["document"][key] for key in SUMMARY_KEYS} for row in rows]

    def evidence(self) -> dict:
        with self.connect() as connection:
            # Repeatable snapshot: totals and integrity inspect the same published dataset.
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            ids = [str(row["id"]) for row in connection.execute("SELECT id FROM kairos_runs WHERE published=true ORDER BY created_at").fetchall()]
            documents = [self._read(connection, run_id, public=True) for run_id in ids]
        return {
            "provenance": "Measured from committed, published synthetic runs in the connected PostgreSQL database.",
            "runner": "deterministic-reference-policy", "model": None,
            "run_count": len(documents), "event_count": sum(len(d["events"]) for d in documents),
            "passing_runs": sum(d["grade"]["passed"] for d in documents),
            "failing_runs": sum(not d["grade"]["passed"] for d in documents),
            "abstained_runs": sum(d["decision"]["refund_cents"] is None for d in documents),
            "integrity_verified_runs": sum(d["integrity"]["verified"] for d in documents),
            "fork_count": sum(d["parent_run_id"] is not None for d in documents),
            "checks": [
                {"name": "local_hash_consistency", "passed": bool(documents) and all(d["integrity"]["verified"] for d in documents),
                 "detail": INTEGRITY_SCOPE},
                {"name": "model_qualification", "passed": None, "detail": "Not evaluated: no language model is used by this reference runner."},
            ],
            "limitations": ["Synthetic tasks do not establish real customer adoption or model quality.",
                            "Forks rerun the complete controlled scenario; arbitrary checkpoint resume is not implemented.",
                            "No external writes, payments, throughput benchmarks, bootstrap confidence intervals or hosted CI claims."],
        }
