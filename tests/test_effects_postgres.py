"""Sandbox approval invariants verified against isolated real PostgreSQL schemas."""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
import pytest
from kairos_api.effects import EffectRepository, EffectConflict, LostSandboxResponse
from kairos_api.repository import MissingRun, CorruptRun, IdempotencyConflict

@pytest.fixture
def effects():
    url=os.environ.get("TEST_DATABASE_URL")
    if not url:pytest.skip("TEST_DATABASE_URL required")
    schema="effects_test_"+uuid4().hex
    with psycopg.connect(url,autocommit=True) as c:c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    repo=EffectRepository(make_conninfo(url,options=f"-c search_path={schema}"));repo.initialize()
    yield repo
    with psycopg.connect(url,autocommit=True) as c:c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

def proposal(repo, key="run"):
    run=repo.create("a",key,{"scenario_id":"late-order-standard","policy":"preserve","publish":False})
    return repo.propose("a",run["id"],"proposal-"+key)

def approved(repo):
    p=proposal(repo)
    return repo.approve("a",p["id"],1,"subject-1","approval")

def count(repo):
    with repo.connect() as c:return c.execute("SELECT count(*) AS n FROM kairos_sandbox_adjustments").fetchone()["n"]

def test_dispatch_requires_approval_and_binds_version(effects):
    p=proposal(effects)
    with pytest.raises(EffectConflict):effects.dispatch("a",p["id"],1,"dispatch")
    a=effects.approve("a",p["id"],1,"subject-1","approval")
    assert a["version"]==2 and a["approved_by"]=="subject-1"
    with pytest.raises(EffectConflict):effects.dispatch("a",p["id"],1,"dispatch-stale")
    assert count(effects)==0
    assert effects.dispatch("a",p["id"],2,"dispatch")["real_money"] is False
    assert count(effects)==1

def test_concurrent_retry_and_lost_response_reconcile_one_receipt(effects):
    a=approved(effects)
    with pytest.raises(LostSandboxResponse):effects.dispatch("a",a["id"],2,"dispatch",lose_response=True)
    def retry(_):return effects.dispatch("a",a["id"],2,"dispatch")["receipt_id"]
    with ThreadPoolExecutor(max_workers=4) as pool:receipts=list(pool.map(retry,range(8)))
    assert len(set(receipts))==1 and count(effects)==1
    with pytest.raises(IdempotencyConflict):effects.dispatch("a",a["id"],3,"dispatch")

def test_fork_does_not_inherit_approval_or_duplicate_target(effects):
    a=approved(effects);receipt=effects.dispatch("a",a["id"],2,"dispatch")
    fork=effects.create("a","fork",{"policy":"preserve"},parent_run_id=a["run_id"])
    p=effects.propose("a",fork["id"],"fork-proposal")
    assert p["state"]=="proposed"
    with pytest.raises(EffectConflict):effects.dispatch("a",p["id"],1,"fork-dispatch")
    effects.approve("a",p["id"],1,"subject-1","fork-approval")
    second=effects.dispatch("a",p["id"],2,"fork-dispatch")
    assert second["receipt_id"]==receipt["receipt_id"] and count(effects)==1

def test_bad_and_abstained_drafts_cannot_create_proposal(effects):
    for i,scenario in enumerate(("late-order-exception","insufficient-evidence")):
        run=effects.create("a",str(i),{"scenario_id":scenario,"policy":"compact","publish":False})
        with pytest.raises(EffectConflict):effects.propose("a",run["id"],"proposal"+str(i))
    assert count(effects)==0

def test_cross_tenant_and_revocation(effects):
    a=approved(effects)
    with pytest.raises(MissingRun):effects.dispatch("b",a["id"],2,"dispatch")
    effects.revoke("a",a["id"],2,"revoke")
    with pytest.raises(EffectConflict):effects.dispatch("a",a["id"],2,"dispatch")
    assert effects.list("b")==[] and count(effects)==0

def test_expired_approval_requires_renewal(effects):
    a=approved(effects)
    with effects.connect() as c:c.execute("UPDATE kairos_effect_proposals SET approval_expires_at=now()-interval '1 second' WHERE id=%s",(a["id"],))
    with pytest.raises(EffectConflict):effects.dispatch("a",a["id"],2,"dispatch")
    renewed=effects.approve("a",a["id"],2,"subject-2","renew")
    assert renewed["version"]==3
    effects.dispatch("a",a["id"],3,"dispatch")
    assert count(effects)==1

def test_proposal_tamper_blocks_dispatch(effects):
    a=approved(effects)
    with effects.connect() as c:
        altered={**a["proposal"],"amount_cents":900}
        c.execute("UPDATE kairos_effect_proposals SET proposal=%s WHERE id=%s",(Jsonb(altered),a["id"]))
    with pytest.raises(CorruptRun):effects.dispatch("a",a["id"],2,"dispatch")
    assert count(effects)==0
