"""Explicit approval and receipt reconciliation against a transactional sandbox target.

This target shares PostgreSQL with the authority, so its receipt can commit atomically.
That guarantee does not extend to an arbitrary external payment API.
"""
from pathlib import Path
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from kairos_api.integrity import request_digest
from kairos_api.repository import RunRepository, MissingRun, IdempotencyConflict, CorruptRun


class EffectConflict(Exception):
    pass


class LostSandboxResponse(Exception):
    """Test fault: target committed but caller did not observe its response."""


class EffectVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class EffectRepository(RunRepository):
    def initialize(self) -> None:
        """Verify the applied schema; setup owns all schema and data changes."""
        from kairos_api.migrations import verify
        with self.connect() as connection:
            verify(connection)

    @staticmethod
    def _id(value):
        try:
            return str(UUID(value))
        except (ValueError, TypeError):
            raise MissingRun("Proposal not found.") from None

    @staticmethod
    def _view(row):
        return {**row, "id": str(row["id"]), "run_id": str(row["run_id"]),
                "created_at": row["created_at"].isoformat(),
                "approval_expires_at": row["approval_expires_at"].isoformat() if row["approval_expires_at"] else None}

    def _proposal(self, connection, tenant, proposal_id):
        row = connection.execute("SELECT * FROM kairos_effect_proposals WHERE tenant_id=%s AND id=%s FOR UPDATE",
                                 (tenant, self._id(proposal_id))).fetchone()
        if not row:
            raise MissingRun("Proposal not found.")
        if request_digest(row["proposal"]) != row["digest"]:
            raise CorruptRun("Proposal content failed local consistency checks.")
        row["db_now"] = connection.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
        return row

    def _command(self, connection, tenant, key, payload, action):
        digest = request_digest(payload)
        connection.execute("INSERT INTO kairos_effect_commands(tenant_id,command_key,digest) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (tenant,key,digest))
        row = connection.execute("SELECT * FROM kairos_effect_commands WHERE tenant_id=%s AND command_key=%s FOR UPDATE", (tenant,key)).fetchone()
        if row["digest"] != digest:
            raise IdempotencyConflict("Effect command key belongs to another payload.")
        if row["result"] is not None:
            return row["result"]
        result = action()
        connection.execute("UPDATE kairos_effect_commands SET result=%s WHERE tenant_id=%s AND command_key=%s", (Jsonb(result),tenant,key))
        return result

    def propose(self, tenant, run_id, key):
        with self.connect() as connection:
            self._enforce_durability(connection)
            def action():
                run = self._read(connection,run_id,tenant_id=tenant)
                if not run["integrity"]["verified"]:
                    raise CorruptRun("Run consistency check failed.")
                amount = run["decision"]["refund_cents"]
                if not run["grade"]["passed"] or amount is None or amount <= 0:
                    raise EffectConflict("Only independently passing positive drafts can become sandbox proposals.")
                proposal = {"run_id":run_id,"decision_digest":request_digest(run["decision"]),
                            "order_id":run["scenario"]["order_id"],"amount_cents":amount,
                            "currency":"INR","target":"postgres-synthetic-adjustment-v1"}
                connection.execute("INSERT INTO kairos_effect_proposals(id,tenant_id,run_id,proposal,digest) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,run_id) DO NOTHING", (uuid4(),tenant,run_id,Jsonb(proposal),request_digest(proposal)))
                row=connection.execute("SELECT * FROM kairos_effect_proposals WHERE tenant_id=%s AND run_id=%s",(tenant,run_id)).fetchone()
                if row["digest"] != request_digest(proposal):
                    raise EffectConflict("Existing proposal differs from the current verified draft.")
                return self._view(row)
            return self._command(connection,tenant,key,{"action":"propose","run_id":run_id},action)

    def list(self, tenant):
        with self.connect() as connection:
            return [self._view(row) for row in connection.execute("SELECT * FROM kairos_effect_proposals WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 100",(tenant,)).fetchall()]

    def approve(self, tenant, proposal_id, version, actor, key):
        with self.connect() as connection:
            self._enforce_durability(connection)
            def action():
                row=self._proposal(connection,tenant,proposal_id)
                if row["version"] != version or not (row["state"] == "proposed" or (row["state"] == "approved" and row["approval_expires_at"] <= row["db_now"])):
                    raise EffectConflict("Proposal version or state changed; reload before approving.")
                updated=connection.execute("UPDATE kairos_effect_proposals SET state='approved',version=version+1,approved_by=%s,approval_expires_at=now()+interval '15 minutes' WHERE id=%s RETURNING *",(actor,proposal_id)).fetchone()
                return self._view(updated)
            return self._command(connection,tenant,key,{"action":"approve","id":proposal_id,"version":version,"actor":actor},action)

    def revoke(self, tenant, proposal_id, version, key):
        with self.connect() as connection:
            self._enforce_durability(connection)
            def action():
                row=self._proposal(connection,tenant,proposal_id)
                if row["version"] != version or row["state"] not in ("proposed","approved"):
                    raise EffectConflict("Proposal version or state changed; applied receipts cannot be revoked.")
                updated=connection.execute("UPDATE kairos_effect_proposals SET state='revoked',version=version+1,approval_expires_at=NULL WHERE id=%s RETURNING *",(proposal_id,)).fetchone()
                return self._view(updated)
            return self._command(connection,tenant,key,{"action":"revoke","id":proposal_id,"version":version},action)

    def dispatch(self, tenant, proposal_id, version, key, *, lose_response=False):
        with self.connect() as connection:
            self._enforce_durability(connection)
            def action():
                row=self._proposal(connection,tenant,proposal_id)
                if row["state"] != "approved" or row["version"] != version:
                    raise EffectConflict("Dispatch requires the current approved proposal version.")
                if row["approval_expires_at"] <= row["db_now"]:
                    raise EffectConflict("Approval expired; review and approve the current version again.")
                proposal=row["proposal"]
                run=self._read(connection,str(row["run_id"]),tenant_id=tenant)
                if not run["integrity"]["verified"] or request_digest(run["decision"]) != proposal["decision_digest"]:
                    raise CorruptRun("Approved run no longer matches the captured decision.")
                target={"order_id":proposal["order_id"],"amount_cents":proposal["amount_cents"],"currency":proposal["currency"]}
                digest=request_digest(target)
                connection.execute("INSERT INTO kairos_sandbox_adjustments(id,tenant_id,order_id,target_digest,amount_cents,proposal_id) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,order_id) DO NOTHING",(uuid4(),tenant,proposal["order_id"],digest,proposal["amount_cents"],proposal_id))
                receipt=connection.execute("SELECT * FROM kairos_sandbox_adjustments WHERE tenant_id=%s AND order_id=%s FOR UPDATE",(tenant,proposal["order_id"])).fetchone()
                if receipt["target_digest"] != digest:
                    raise EffectConflict("Target already has a different adjustment for this order; manual reconciliation required.")
                connection.execute("UPDATE kairos_effect_proposals SET state='applied',version=version+1 WHERE id=%s",(proposal_id,))
                return {"proposal_id":proposal_id,"receipt_id":str(receipt["id"]),"order_id":receipt["order_id"],"amount_cents":receipt["amount_cents"],"state":"applied","target":"postgres-synthetic-adjustment-v1","real_money":False,"created_at":receipt["created_at"].isoformat()}
            result=self._command(connection,tenant,key,{"action":"dispatch","id":proposal_id,"version":version},action)
        if lose_response:
            raise LostSandboxResponse("Sandbox commit succeeded; response lost by test fault.")
        return result

    def receipt(self, tenant, proposal_id):
        with self.connect() as connection:
            row=self._proposal(connection,tenant,proposal_id)
            receipt=connection.execute("SELECT * FROM kairos_sandbox_adjustments WHERE tenant_id=%s AND order_id=%s",(tenant,row["proposal"]["order_id"])).fetchone()
            if row["state"] != "applied" or not receipt:
                raise MissingRun("Applied receipt not found.")
            target={key:row["proposal"][key] for key in ("order_id","amount_cents","currency")}
            if request_digest(target) != receipt["target_digest"]:
                raise CorruptRun("Target receipt differs from the approved proposal.")
            return {"proposal_id":proposal_id,"receipt_id":str(receipt["id"]),"order_id":receipt["order_id"],"amount_cents":receipt["amount_cents"],"state":"applied","target":"postgres-synthetic-adjustment-v1","real_money":False,"created_at":receipt["created_at"].isoformat()}


def create_effects_router(tenant_dependency, key_dependency, database_url=None, *, approval_dependency=None, repository_dependency=None):
    router=APIRouter()
    if repository_dependency is None:
        instance=EffectRepository(database_url)
        repository_dependency=lambda: instance
    approval_dependency=approval_dependency or tenant_dependency

    @router.get("/api/effects")
    def proposals(tenant: str=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return {"proposals":repository.list(tenant),"target":"synthetic PostgreSQL sandbox; no payments"}

    @router.post("/api/runs/{run_id}/proposal",status_code=201)
    def propose(run_id:str,tenant:str=Depends(tenant_dependency),key:str=Depends(key_dependency),repository=Depends(repository_dependency)):
        return repository.propose(tenant,run_id,key)

    @router.get("/api/effects/{proposal_id}/receipt")
    def receipt(proposal_id:str,tenant:str=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return repository.receipt(tenant,proposal_id)

    @router.post("/api/effects/{proposal_id}/approve")
    def approve(proposal_id:str,command:EffectVersion,request:Request,tenant:str=Depends(approval_dependency),key:str=Depends(key_dependency),repository=Depends(repository_dependency)):
        actor=getattr(request.state,"identity_subject","authenticated-operator")
        return repository.approve(tenant,proposal_id,command.version,actor,key)

    @router.post("/api/effects/{proposal_id}/revoke")
    def revoke(proposal_id:str,command:EffectVersion,tenant:str=Depends(approval_dependency),key:str=Depends(key_dependency),repository=Depends(repository_dependency)):
        return repository.revoke(tenant,proposal_id,command.version,key)

    @router.post("/api/effects/{proposal_id}/dispatch")
    def dispatch(proposal_id:str,command:EffectVersion,tenant:str=Depends(tenant_dependency),key:str=Depends(key_dependency),repository=Depends(repository_dependency)):
        return repository.dispatch(tenant,proposal_id,command.version,key)
    return router
