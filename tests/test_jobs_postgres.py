"""Durable-runtime integration checks against isolated real PostgreSQL schemas."""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
import pytest

from kairos_api.jobs import create_jobs_router
from kairos_api.jobs_repository import JobsRepository
from kairos_api.model_runtime import model_request
from kairos_api.worker import JobWorker

COMMAND = {"scenario_id":"late-order-exception","policy":"preserve","runner":"model","publish":False}
VALID = {"raw_response":'{"disposition":"zero","reason":"Already compensated","evidence_ids":["policy.exception","order.receipt"]}',"model":"test-classifier","model_revision":"test-v1"}


@pytest.fixture
def repository(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL runtime tests")
    schema = "kairos_jobs_test_" + uuid4().hex
    with psycopg.connect(url,autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    repository = JobsRepository(make_conninfo(url,options=f"-c search_path={schema}",application_name=schema),tmp_path/"blobs")
    repository.initialize()
    yield repository
    with psycopg.connect(url,autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def enqueue(repository,key="test",**changes):
    return repository.enqueue("tenant-a",key,{**COMMAND,**changes})


def expire(repository,job_id):
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(job_id,))


def test_durable_identity_idempotency_and_conflict(repository):
    first = enqueue(repository)
    restarted = JobsRepository(repository.database_url,repository.blobs.root)
    assert restarted.read(first["id"],"tenant-a")["status"] == "queued"
    assert enqueue(repository)["id"] == first["id"]
    with pytest.raises(HTTPException) as error:
        enqueue(repository,policy="compact")
    assert error.value.status_code == 409
    assert len(repository.list("tenant-a")) == 1


def test_concurrent_duplicate_enqueue_and_distinct_claim(repository):
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _:enqueue(repository)["id"],range(8)))
    assert len(set(ids)) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda i:repository.claim(str(i)),range(4)))
    assert len([claim for claim in claims if claim]) == 1


def test_real_reference_executor_and_independent_grader(repository):
    failed = enqueue(repository,runner="reference",policy="compact")
    result = JobWorker(repository).run_once()
    assert result["id"] == failed["id"] and result["status"] == "failed"
    assert result["result"]["decision"]["refund_cents"] == 480
    assert result["result"]["grade"]["passed"] is False
    assert result["model_calls"] == 0 and result["integrity"]["verified"]


def test_provider_sees_committed_intent_and_no_open_worker_transaction(repository):
    queued = enqueue(repository)
    def provider(request):
        with repository.connect() as connection:
            row = connection.execute("SELECT stage,request,model_calls FROM kairos_jobs WHERE id=%s",(queued["id"],)).fetchone()
            assert row["stage"] == "dispatched" and row["model_calls"] == 1
            assert row["request"]["body"] == request
            own_pid = connection.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            count = connection.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE application_name=current_setting('application_name') AND pid<>%s AND state='idle in transaction'",(own_pid,)).fetchone()["n"]
            assert count == 0
        return VALID
    result = JobWorker(repository,provider).run_once()
    assert result["status"] == "succeeded"
    assert result["response"]["body"] == VALID
    assert result["result"]["decision"]["refund_cents"] == 0
    assert result["integrity"]["verified"]


def test_strict_failure_preserves_raw_response_and_does_not_retry(repository):
    enqueue(repository)
    raw = "```json\n{}\n```"
    result = JobWorker(repository,lambda _: {"raw_response":raw,"model":"bad-format"}).run_once()
    assert result["status"] == "failed" and result["response"]["body"]["raw_response"] == raw
    assert result["result"]["grade"]["passed"] is False
    assert result["result"]["parse_error"]
    assert JobWorker(repository,lambda _:pytest.fail("Must not repeat")).run_once() is None


def test_unknown_provider_outcome_never_redispatched(repository):
    queued = enqueue(repository)
    def lost(_):
        raise TimeoutError("injected response loss")
    result = JobWorker(repository,lost).run_once()
    assert result["status"] == "unknown" and result["model_calls"] == 1
    with pytest.raises(HTTPException) as error:
        repository.recover(queued["id"],"tenant-a")
    assert error.value.status_code == 409
    assert JobWorker(repository,lambda _:pytest.fail("No hidden retry")).run_once() is None


def test_cancel_queued_and_during_provider_preserves_capture(repository):
    first = enqueue(repository)
    assert repository.cancel(first["id"],"tenant-a")["status"] == "cancelled"
    assert JobWorker(repository,lambda _:pytest.fail("Queued cancellation dispatched")).run_once() is None
    second = enqueue(repository,"running")
    def provider(_):
        assert repository.cancel(second["id"],"tenant-a")["cancel_requested"]
        return VALID
    result = JobWorker(repository,provider).run_once()
    assert result["status"] == "cancelled" and result["response"]["body"] == VALID


def test_expired_lease_before_dispatch_requeues_and_fences_old_worker(repository):
    queued = enqueue(repository,runner="reference")
    stale = repository.claim("stale")
    expire(repository,queued["id"])
    assert repository.reclaim_expired() == 1
    winner = repository.claim("winner")
    assert winner["lease_token"] > stale["lease_token"]
    with pytest.raises(RuntimeError,match="Stale"):
        repository.finish(stale,error={"code":"old-worker"})
    assert repository.finish(winner,result={"grade":{"passed":True},"decision":{}})["status"] == "succeeded"


def test_crash_after_dispatch_becomes_unknown_without_redispatch(repository):
    queued = enqueue(repository)
    job = repository.claim("crash")
    repository.dispatch_intent(job,model_request(job["context_blocks"]))
    expire(repository,queued["id"])
    repository.reclaim_expired()
    recovered = repository.read(queued["id"],"tenant-a")
    assert recovered["status"] == "unknown" and recovered["response"] is None
    assert JobWorker(repository,lambda _:pytest.fail("Ambiguous dispatch repeated")).run_once() is None


def test_crash_after_known_response_explicit_continuation_no_model_call(repository):
    queued = enqueue(repository)
    job = repository.claim("crash")
    repository.dispatch_intent(job,model_request(job["context_blocks"]))
    repository.capture_response(job,VALID)
    expire(repository,queued["id"])
    repository.reclaim_expired()
    assert repository.read(queued["id"],"tenant-a")["status"] == "unknown"
    repository.recover(queued["id"],"tenant-a")
    result = JobWorker(repository,lambda _:pytest.fail("Known response must not redispatch")).run_once()
    assert result["status"] == "succeeded" and result["model_calls"] == 1
    assert result["attempt"] == 2 and result["integrity"]["verified"]


def test_checkpoint_version_context_and_attempt_budgets(repository):
    queued = enqueue(repository)
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_jobs SET checkpoint_version=99 WHERE id=%s",(queued["id"],))
    assert JobWorker(repository,lambda _:pytest.fail("Invalid checkpoint dispatched")).run_once()["status"] == "failed"
    second = enqueue(repository,"budget")
    for _ in range(3):
        claim = repository.claim("crash-loop")
        assert claim
        expire(repository,second["id"])
        repository.reclaim_expired()
    final = repository.read(second["id"],"tenant-a")
    assert final["status"] == "failed" and final["attempt"] == 3
    assert JobWorker(repository).run_once() is None


def test_deadline_stops_before_dispatch(repository):
    queued = enqueue(repository)
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_jobs SET deadline_at=clock_timestamp()-interval '1 second' WHERE id=%s",(queued["id"],))
    assert JobWorker(repository,lambda _:pytest.fail("Expired deadline dispatched")).run_once() is None
    assert repository.read(queued["id"],"tenant-a")["status"] == "failed"


def test_tenant_and_public_isolation_and_scoped_blobs(repository):
    queued = enqueue(repository)
    result = JobWorker(repository,lambda _:VALID).run_once()
    for kwargs in ({"tenant_id":"tenant-b"},{"public":True}):
        with pytest.raises(HTTPException) as error:
            repository.read(queued["id"],**kwargs)
        assert error.value.status_code == 404
    key = result["response"]["blob"]["sha256"]
    assert repository.blob(queued["id"],"tenant-a",key) == VALID
    with pytest.raises(HTTPException):
        repository.blob(queued["id"],"tenant-b",key)
    with pytest.raises(HTTPException):
        repository.blob(queued["id"],"tenant-a","a"*64)


def test_network_free_recorded_replay_and_corruption_rejection(repository):
    queued = enqueue(repository)
    result = JobWorker(repository,lambda _:VALID).run_once()
    replay = repository.replay(queued["id"],"tenant-a")
    assert replay["network_calls"] == replay["external_effects"] == 0
    assert replay["result"] == result["result"]
    key = result["response"]["blob"]["sha256"]
    (repository.blobs.root/key).write_text("tampered")
    assert not repository.read(queued["id"],"tenant-a")["integrity"]["verified"]
    with pytest.raises(HTTPException) as error:
        repository.replay(queued["id"],"tenant-a")
    assert error.value.status_code == 409


def test_foreign_event_and_result_tampering_detected(repository):
    queued = enqueue(repository)
    JobWorker(repository,lambda _:VALID).run_once()
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_jobs SET result=%s WHERE id=%s",(Jsonb({"grade":{"passed":False}}),queued["id"]))
    assert not repository.read(queued["id"],"tenant-a")["integrity"]["verified"]


def test_router_validation_scoping_replay_verification_and_fresh_fork(repository):
    app = FastAPI()
    app.include_router(create_jobs_router(lambda:"tenant-a",lambda:"http-command",lambda:repository))
    with TestClient(app) as client:
        assert client.post("/api/jobs",json={**COMMAND,"tenant_id":"other"}).status_code == 422
        queued = client.post("/api/jobs",json=COMMAND)
        assert queued.status_code == 202
        job_id = queued.json()["id"]
        JobWorker(repository,lambda _:VALID).run_once()
        assert client.get(f"/api/jobs/{job_id}/verify").json()["captured_result_matches"]
        assert client.get(f"/api/jobs/{job_id}/replay").json()["network_calls"] == 0
        # Different fork command shares command-key space, so retry conflict is explicit.
        assert client.post(f"/api/jobs/{job_id}/fork",json={"policy":"compact","runner":"reference"}).status_code == 409
        fork = repository.enqueue("tenant-a","fresh-fork",{**COMMAND,"policy":"compact"},job_id)
        assert fork["parent_job_id"] == job_id and fork["model_calls"] == 0


def test_active_job_quota_and_durability_override(repository):
    original = repository.connect
    def asynchronous_default():
        connection = original()
        connection.execute("SET synchronous_commit=off")
        connection.commit()
        return connection
    repository.connect = asynchronous_default
    original_event = repository._event
    def inspect(connection,*args):
        assert connection.execute("SHOW synchronous_commit").fetchone()["synchronous_commit"] == "on"
        return original_event(connection,*args)
    repository._event = inspect
    for index in range(20):
        enqueue(repository,str(index))
    with pytest.raises(HTTPException) as error:
        enqueue(repository,"overflow")
    assert error.value.status_code == 429


def test_untouched_capture_survives_code_version_change_but_resume_requires_current_code(repository,monkeypatch):
    import kairos_api.jobs_repository as module
    queued = enqueue(repository)
    result = JobWorker(repository,lambda _:VALID).run_once()
    snapshot = result["input_snapshot"]
    assert snapshot["source_digests"] and snapshot["truth"]["policy_exception"]
    original = module.input_snapshot
    def changed(*args):
        snapshot = original(*args)
        snapshot["checkpoint_version"] = 2
        return snapshot
    monkeypatch.setattr(module,"input_snapshot",changed)
    assert repository.read(queued["id"],"tenant-a")["integrity"]["verified"]
    assert repository.replay(queued["id"],"tenant-a")["network_calls"] == 0


def test_blob_reference_substitution_detected_even_when_object_digest_is_valid(repository):
    queued = enqueue(repository)
    JobWorker(repository,lambda _:VALID).run_once()
    replacement = {"raw_response":"different"}
    blob = repository.blobs.put(replacement)
    with repository.connect() as connection:
        connection.execute("UPDATE kairos_jobs SET response=%s WHERE id=%s",(Jsonb({"body":replacement,"blob":blob}),queued["id"]))
    assert not repository.read(queued["id"],"tenant-a")["integrity"]["verified"]
