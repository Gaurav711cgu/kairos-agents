"""PostgreSQL job authority. No provider call occurs under a DB transaction."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import HTTPException

from kairos_api.model_runtime import BlobStore, digest
from kairos_api.scenarios import assemble_context, get_scenario

GENESIS = "0" * 64
SUMMARY = ("id", "scenario_id", "policy", "runner", "status", "created_at", "updated_at",
           "attempt", "max_attempts", "model_calls", "cancel_requested", "publish", "parent_job_id")


def input_snapshot(scenario_id, policy, blocks):
    sources = {}
    for filename in ("scenarios.py", "grading.py", "runner.py", "model_runtime.py"):
        sources[filename] = hashlib.sha256(Path(__file__).with_name(filename).read_bytes()).hexdigest()
    return {"scenario_id": scenario_id, "policy": policy, "blocks": blocks,
                   "truth": get_scenario(scenario_id), "source_digests": sources,
                   "checkpoint_version": 1, "task_set_version": "synthetic-orders-v1"}


def input_digest(scenario_id, policy, blocks):
    return digest(input_snapshot(scenario_id,policy,blocks))


def public_value(value):
    if isinstance(value, dict):
        return {key: public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_value(item) for item in value]
    if isinstance(value, (datetime, UUID)):
        return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else str(value)
    return value


class JobsRepository:
    def __init__(self, database_url=None, blob_root=None):
        self.database_url = database_url or os.environ["DATABASE_URL"]
        self.blobs = BlobStore(blob_root)

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5)

    def initialize(self) -> None:
        """Verify the applied schema; setup owns all schema and data changes."""
        from kairos_api.migrations import verify
        with self.connect() as connection:
            verify(connection)

    def _event(self, connection, job_id, event_type, payload):
        # Caller holds the parent row lock, serializing sequence and hash writes.
        previous = connection.execute("SELECT seq,event_hash FROM kairos_job_events WHERE job_id=%s ORDER BY seq DESC LIMIT 1", (job_id,)).fetchone()
        event = {"job_id": str(job_id), "seq": previous["seq"] + 1 if previous else 1,
                 "event_type": event_type, "payload": payload,
                 "created_at": public_value(connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]),
                 "prev_hash": previous["event_hash"] if previous else GENESIS}
        event["event_hash"] = digest(event)
        connection.execute("INSERT INTO kairos_job_events VALUES (%s,%s,%s,%s,%s,%s,%s)",
                           (job_id,event["seq"],event_type,Jsonb(payload),event["created_at"],event["prev_hash"],event["event_hash"]))

    def _locked(self, connection, job_id, tenant_id=None):
        try:
            UUID(str(job_id))
        except ValueError:
            raise HTTPException(404, "Job not found") from None
        query = "SELECT * FROM kairos_jobs WHERE id=%s"
        params = [job_id]
        if tenant_id is not None:
            query += " AND tenant_id=%s"
            params.append(tenant_id)
        row = connection.execute(query + " FOR UPDATE", params).fetchone()
        if not row:
            raise HTTPException(404, "Job not found")
        return row

    def enqueue(self, tenant_id, key, command, parent_job_id=None):
        command = {"scenario_id": command.get("scenario_id", "late-order-exception"),
                   "policy": command.get("policy", "preserve"), "runner": command.get("runner", "reference"),
                   "publish": command.get("publish", False)}
        request_hash = digest({"command": command, "parent_job_id": parent_job_id})
        blocks = assemble_context(get_scenario(command["scenario_id"]), command["policy"])
        job_id = str(uuid4())
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            # Bound active jobs per tenant without racing separate enqueue transactions.
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("jobs:" + tenant_id,))
            existing = connection.execute("SELECT id,command_digest FROM kairos_jobs WHERE tenant_id=%s AND command_key=%s", (tenant_id,key)).fetchone()
            if existing:
                if existing["command_digest"] != request_hash:
                    raise HTTPException(409, "Idempotency key already binds a different job command")
                job_id = str(existing["id"])
            else:
                if parent_job_id:
                    parent = self._locked(connection, parent_job_id, tenant_id)
                    if parent["scenario_id"] != command["scenario_id"]:
                        raise HTTPException(409, "Fork must retain the parent scenario")
                count = connection.execute("SELECT count(*) AS n FROM kairos_jobs WHERE tenant_id=%s AND status IN ('queued','running')", (tenant_id,)).fetchone()["n"]
                if count >= 20:
                    raise HTTPException(429, "Active job quota reached; wait or cancel before adding work")
                connection.execute("""INSERT INTO kairos_jobs
                    (id,tenant_id,command_key,command_digest,scenario_id,policy,runner,publish,parent_job_id,
                     deadline_at,context_blocks,input_digest,input_snapshot)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+interval '180 seconds',%s,%s,%s)""",
                    (job_id,tenant_id,key,request_hash,command["scenario_id"],command["policy"],command["runner"],
                     command["publish"],parent_job_id,Jsonb(blocks),input_digest(command["scenario_id"],command["policy"],blocks),Jsonb(input_snapshot(command["scenario_id"],command["policy"],blocks))))
                self._event(connection, job_id, "job.queued", {"scenario_id": command["scenario_id"], "policy": command["policy"],
                            "runner": command["runner"], "parent_job_id": parent_job_id, "checkpoint_version": 1,
                            "mode": "fresh-isolated-scenario-rerun" if parent_job_id else "initial-controlled-run"})
                self._event(connection, job_id, "context.selected", {"blocks": blocks, "omitted_ids": [b["id"] for b in blocks if not b["included"]]})
        # Connection has committed before an HTTP 202 can be returned.
        return self.read(job_id, tenant_id=tenant_id)

    def read(self, job_id, tenant_id=None, public=False):
        try:
            UUID(str(job_id))
        except ValueError:
            raise HTTPException(404, "Job not found") from None
        with self.connect() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            query = "SELECT * FROM kairos_jobs WHERE id=%s"
            params = [job_id]
            if public:
                query += " AND publish=true"
            else:
                query += " AND tenant_id=%s"
                params.append(tenant_id)
            row = connection.execute(query, params).fetchone()
            if not row:
                raise HTTPException(404, "Job not found")
            events = connection.execute("SELECT * FROM kairos_job_events WHERE job_id=%s ORDER BY seq", (job_id,)).fetchall()
        result = public_value(row)
        for field in ("tenant_id", "command_key", "command_digest", "lease_owner", "lease_token"):
            result.pop(field, None)
        normalized = []
        previous = GENESIS
        valid = True
        for index, event in enumerate(events, 1):
            event = public_value(event)
            recorded = event.pop("event_hash")
            valid = valid and event["job_id"] == str(job_id) and event["seq"] == index and event["prev_hash"] == previous and digest(event) == recorded
            event["event_hash"] = recorded
            normalized.append(event)
            previous = recorded
        for field in ("request", "response"):
            captured = result[field]
            if captured and "blob" in captured:
                try:
                    valid = valid and digest(self.blobs.get(captured["blob"]["sha256"])) == captured["blob"]["sha256"]
                    valid = valid and digest(captured["body"]) == captured["blob"]["sha256"]
                    capture_type = "model.dispatch_intent" if field == "request" else "model.response_captured"
                    capture_field = "request_digest" if field == "request" else "response_digest"
                    matching = [e for e in normalized if e["event_type"] == capture_type]
                    valid = valid and bool(matching) and matching[-1]["payload"].get(capture_field) == captured["blob"]["sha256"]
                except (ValueError, OSError):
                    valid = False
        if result["result"] is not None:
            completed = [e for e in normalized if e["event_type"] == "job.completed"]
            valid = valid and bool(completed) and completed[-1]["payload"]["result_digest"] == digest(result["result"])
        snapshot = result.get("input_snapshot")
        valid = valid and bool(snapshot) and result["input_digest"] == digest(snapshot)
        valid = valid and bool(snapshot) and snapshot["blocks"] == result["context_blocks"] and snapshot["scenario_id"] == result["scenario_id"] and snapshot["policy"] == result["policy"]
        selected = [e for e in normalized if e["event_type"] == "context.selected"]
        queued = [e for e in normalized if e["event_type"] == "job.queued"]
        valid = valid and bool(selected) and selected[0]["payload"]["blocks"] == result["context_blocks"]
        valid = valid and bool(queued) and all(queued[0]["payload"][key] == result[key] for key in ("scenario_id","policy","runner"))
        result["events"] = normalized
        result["integrity"] = {"verified": bool(valid), "scope": "Local captured objects, event continuity and versioned inputs; not immutable history."}
        result["provenance"] = "Synthetic scenario; actual local model inference." if result["runner"] == "model" else "Synthetic scenario; deterministic reference execution; no model call."
        return result

    def list(self, tenant_id=None, public=False):
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM kairos_jobs WHERE " + ("publish=true" if public else "tenant_id=%s") + " ORDER BY created_at DESC LIMIT 100", () if public else (tenant_id,)).fetchall()
        return [{key: public_value(row[key]) for key in SUMMARY} for row in rows]

    def cancel(self, job_id, tenant_id):
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            row = self._locked(connection, job_id, tenant_id)
            if row["status"] in {"queued", "running"}:
                status = "cancelled" if row["status"] == "queued" else "running"
                connection.execute("UPDATE kairos_jobs SET cancel_requested=true,status=%s,updated_at=clock_timestamp() WHERE id=%s", (status,job_id))
                self._event(connection,job_id,"job.cancel_requested",{"provider_may_still_finish": row["stage"] == "dispatched"})
        return self.read(job_id,tenant_id)

    def recover(self, job_id, tenant_id):
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            row = self._locked(connection,job_id,tenant_id)
            if row["status"] != "unknown" or not row["response"] or row["stage"] != "response_captured":
                raise HTTPException(409, "Only unknown jobs with a durable known response can continue. Unknown dispatches are never silently repeated.")
            if row["checkpoint_version"] != 1 or row["input_digest"] != input_digest(row["scenario_id"],row["policy"],row["context_blocks"]):
                raise HTTPException(409, "Checkpoint code/context version mismatch")
            try:
                captured = row["response"]
                if digest(self.blobs.get(captured["blob"]["sha256"])) != digest(captured["body"]):
                    raise ValueError("Capture mismatch")
            except (ValueError,OSError,KeyError):
                raise HTTPException(409,"Known response object is missing or corrupted") from None
            if row["attempt"] >= row["max_attempts"] or row["cancel_requested"]:
                raise HTTPException(409, "Attempt budget exhausted or cancellation requested; fork a fresh job explicitly")
            connection.execute("UPDATE kairos_jobs SET status='queued',error=NULL,lease_owner=NULL,lease_expires_at=NULL,lease_token=lease_token+1,deadline_at=clock_timestamp()+interval '180 seconds',updated_at=clock_timestamp() WHERE id=%s",(job_id,))
            self._event(connection,job_id,"job.known_result_continuation_requested",{"redispatch": False,"checkpoint_version":1})
        return self.read(job_id,tenant_id)

    def reclaim_expired(self):
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            rows = connection.execute("SELECT * FROM kairos_jobs WHERE status='running' AND lease_expires_at<=clock_timestamp() FOR UPDATE SKIP LOCKED").fetchall()
            for row in rows:
                if row["stage"] == "response_captured" or row["stage"] == "dispatched":
                    status = "unknown"
                    reason = "lease_expired_known_result" if row["response"] else "lease_expired_dispatch_outcome_unknown"
                elif row["cancel_requested"]:
                    status,reason = "cancelled","cancel_before_dispatch"
                elif row["attempt"] >= row["max_attempts"] or self._deadline_expired(connection,row):
                    status,reason = "failed","deadline_or_attempt_budget_exhausted"
                else:
                    status,reason = "queued","lease_expired_before_dispatch"
                connection.execute("UPDATE kairos_jobs SET status=%s,lease_token=lease_token+1,lease_owner=NULL,lease_expires_at=NULL,error=%s,updated_at=clock_timestamp() WHERE id=%s",(status,Jsonb({"code":reason}),row["id"]))
                self._event(connection,row["id"],"job.lease_expired",{"status":status,"reason":reason,"redispatch":False})
            return len(rows)

    def claim(self, owner, lease_seconds=120):
        self.reclaim_expired()
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            # Dispose of expired queued jobs before claiming; fixed deadline stops starvation loops.
            expired = connection.execute("SELECT * FROM kairos_jobs WHERE status='queued' AND deadline_at<=clock_timestamp() FOR UPDATE SKIP LOCKED").fetchall()
            for row in expired:
                connection.execute("UPDATE kairos_jobs SET status='failed',error=%s,updated_at=clock_timestamp() WHERE id=%s",(Jsonb({"code":"deadline_exhausted"}),row["id"]))
                self._event(connection,row["id"],"job.stopped",{"reason":"deadline_exhausted"})
            row = connection.execute("SELECT * FROM kairos_jobs WHERE status='queued' AND deadline_at>clock_timestamp() AND attempt<max_attempts ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not row:
                return None
            row = connection.execute("UPDATE kairos_jobs SET status='running',attempt=attempt+1,lease_token=lease_token+1,lease_owner=%s,lease_expires_at=clock_timestamp()+(%s * interval '1 second'),updated_at=clock_timestamp() WHERE id=%s RETURNING *",(owner,lease_seconds,row["id"])).fetchone()
            self._event(connection,row["id"],"job.claimed",{"attempt":row["attempt"],"lease_token":row["lease_token"],"checkpoint_version":row["checkpoint_version"]})
        return row

    @staticmethod
    def _deadline_expired(connection, row):
        # Database time is authoritative across workers with different host clocks.
        return connection.execute("SELECT %s::timestamptz <= clock_timestamp() AS expired", (row["deadline_at"],)).fetchone()["expired"]

    def _fenced(self, connection, job):
        row = self._locked(connection,job["id"])
        # Check the database clock after acquiring the lock, not before a possible wait.
        expired = connection.execute("SELECT %s::timestamptz <= clock_timestamp() AS expired", (row["lease_expires_at"],)).fetchone()["expired"]
        if row["status"] != "running" or row["lease_token"] != job["lease_token"] or row["lease_owner"] != job["lease_owner"] or expired:
            raise RuntimeError("Stale worker lease rejected")
        return row

    def dispatch_intent(self, job, request):
        blob = self.blobs.put(request)
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            row = self._fenced(connection,job)
            if row["cancel_requested"] or self._deadline_expired(connection,row):
                return False
            if row["model_calls"] >= 1 or row["stage"] != "prepared":
                raise RuntimeError("Model call budget/checkpoint prevents redispatch")
            capture = {"body":request,"blob":blob}
            connection.execute("UPDATE kairos_jobs SET stage='dispatched',request=%s,model_calls=model_calls+1,updated_at=clock_timestamp() WHERE id=%s",(Jsonb(capture),job["id"]))
            self._event(connection,job["id"],"model.dispatch_intent",{"request_digest":blob["sha256"],"max_calls":1,"outcome":"not_yet_known"})
        return True

    def capture_response(self, job, response):
        blob = self.blobs.put(response)
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            row = self._fenced(connection,job)
            if row["stage"] != "dispatched":
                raise RuntimeError("Response requires a committed dispatch intent")
            connection.execute("UPDATE kairos_jobs SET stage='response_captured',response=%s,updated_at=clock_timestamp() WHERE id=%s",(Jsonb({"body":response,"blob":blob}),job["id"]))
            self._event(connection,job["id"],"model.response_captured",{"response_digest":blob["sha256"],"raw_response_preserved":True})

    def finish(self, job, result=None, error=None, unknown=False):
        with self.connect() as connection:
            connection.execute("SET LOCAL synchronous_commit=on")
            row = self._fenced(connection,job)
            if row["cancel_requested"]:
                status = "cancelled"
            elif unknown:
                status = "unknown"
            elif self._deadline_expired(connection,row):
                status,error = "failed",{"code":"deadline_exhausted"}
            else:
                status = "succeeded" if result and result["grade"]["passed"] else "failed"
            connection.execute("UPDATE kairos_jobs SET status=%s,result=%s,error=%s,stage=%s,lease_owner=NULL,lease_expires_at=NULL,updated_at=clock_timestamp() WHERE id=%s",(status,Jsonb(result) if result is not None else None,Jsonb(error) if error else None,"completed" if result else row["stage"],job["id"]))
            self._event(connection,job["id"],"job.completed" if result else "job.stopped",{"status":status,"result_digest":digest(result) if result else None,"error":error,"external_effects":0})
        return self.read(str(job["id"]),tenant_id=job["tenant_id"])

    def replay(self, job_id, tenant_id):
        job = self.read(job_id,tenant_id)
        if not job["integrity"]["verified"]:
            raise HTTPException(409,"Capture integrity/version mismatch; replay refused")
        return {"job_id":job_id,"mode":"recorded-playback","network_calls":0,"external_effects":0,
                "events":job["events"],"context_blocks":job["context_blocks"],"request":job["request"],
                "response":job["response"],"result":job["result"],"integrity":job["integrity"]}

    def blob(self, job_id, tenant_id, key):
        job = self.read(job_id,tenant_id)
        if not any(job[field] and job[field].get("blob",{}).get("sha256") == key for field in ("request","response")):
            raise HTTPException(404,"Object is not referenced by this scoped job")
        try:
            return self.blobs.get(key)
        except (ValueError,OSError):
            raise HTTPException(409,"Captured object integrity unavailable") from None
