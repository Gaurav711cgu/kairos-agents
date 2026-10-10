# Build002 durable runtime contract

Implemented in `jobs.py`, `jobs_repository.py`, `worker.py`, `model_runtime.py` and `schema_jobs.sql`. Root app supplies authenticated tenant and idempotency-key dependencies. Router creation: `create_jobs_router(tenant_dependency, key_dependency, repository_dependency)`. Create a JobsRepository with the same database and initialize it during startup. Schema migration is additive and idempotent.

## Running

Load ignored `.env.kairos.local` into the process environment without logging its contents. API worker: `.venv/bin/python -m kairos_api.worker` (or `--once`). Separate offline model service: `python3 scripts/serve_local_model.py --model /absolute/cached/model/directory --port 8120`; this Python environment needs torch and transformers. The model loader has local_files_only and trust_remote_code false. No paid provider calls occur. `KAIROS_MODEL_ENDPOINT` is a server-controlled URL, default http://127.0.0.1:8120/generate. Client commands cannot supply arbitrary URLs. `KAIROS_BLOB_DIR` defaults `.runtime/blobs`; back up it together with PostgreSQL. It is a local content-addressed object store, not S3 or immutable storage.

`python -m kairos_api.jobs_probe` saves six actual aligned development observations, explicitly not a quality/release gate. Its stable idempotency keys make rerunning it read existing observations; choose an explicit new --key-prefix for another paid-in-compute experiment. `python scripts/drill_worker_crash.py` runs two actual SIGKILL worker subprocess drills in an isolated PostgreSQL schema and deletes only that schema afterwards. The drill provider is a controlled fixture; it is recovery evidence, not model-quality evidence.

## HTTP routes

- POST /api/jobs (202, Idempotency-Key required): scenario_id in late-order-exception/late-order-standard/insufficient-evidence; policy compact/preserve; runner reference/model; publish boolean default false.
- GET /api/jobs and GET /api/jobs/{id}: scoped list/detail. Public reads exist under /api/public/jobs only for explicit published synthetic jobs.
- POST /api/jobs/{id}/cancel: queued cancellation prevents dispatch; running cancellation is cooperative and preserves an eventual response. It cannot undo a provider invocation already dispatched.
- POST /api/jobs/{id}/recover with {mode:continue_known_result}: only unknown jobs with an existing durable response checkpoint can continue, and only with matching code/context version and budget. It never redispatches a model call. Ambiguous dispatches require an explicit fresh fork.
- POST /api/jobs/{id}/fork with policy/runner and Idempotency-Key: fresh complete scenario execution with parent lineage. It inherits publication but no approvals or provider result. It is not arbitrary checkpoint replay.
- GET /api/jobs/{id}/replay: network-free recorded playback. GET /verify: deterministic independent regrading, no inference and no effects.
- GET /api/jobs/{id}/blobs/{sha256}: scoped to objects referenced by that authenticated job. Digest possession alone does not grant access.

Summary: id, scenario_id, policy, runner, status, created_at, updated_at, attempt, max_attempts, model_calls, cancel_requested, publish, parent_job_id. Detail adds context_blocks, events, request, response, result, error, stage, deadline_at, lease_expires_at, checkpoint_version, input_snapshot, input_digest, integrity and provenance. Secrets, tenant IDs, lease owner/token and command keys are omitted. Events contain job_id, seq, event_type, payload, created_at, prev_hash, event_hash.

## State and guarantees

Queue insertion commits with synchronous_commit on before response; PostgreSQL fsync must be on. Active-tenant quota is20. Jobs have a180-second deadline, at most3 claims and at most1 model dispatch. Claim uses SKIP LOCKED, a120-second lease and monotonic fencing tokens. Provider timeout is100seconds. No HTTP provider call runs while a database transaction is open. Durable dispatch intent precedes the invocation; exact rendered request and raw response are captured afterwards with input/output tokens, model-file digests and runtime metadata. Request/response blobs use temp-write, file fsync, atomic replace and directory fsync. Orphan blobs after DB rollback are harmless but require future retention cleanup.

Worker death before dispatch can requeue within budgets. Death after dispatch becomes UNKNOWN, because success or billable inference cannot be inferred from a missing response. Death after a durable response also becomes UNKNOWN, but supports explicit known-result continuation. Old workers are fenced after expiry; they cannot commit a late result. Cancellation/deadline stops further work but cannot interrupt the separate provider process reliably. Local model HTTP429/transport errors after intent remain ambiguous and are not automatically retried.

Model output is exact JSON classification: disposition refund/zero/abstain, reason1..2000characters, unique included evidence_ids. Duplicate keys, nonfinite constants, fences, extra keys and hallucinated citations fail. Abstention cites policy.evidence; exception-zero cites policy.exception when present. Refund arithmetic uses the verified synthetic order amount in a deterministic tool. The independent grader sees complete source truth; it can reject semantically wrong decisions even when parsing succeeds. Execution status succeeded requires grade pass; failed preserves provider output and grader details.

Captured input snapshots retain fixture truth, selected blocks and source digests so historical recorded playback survives a later code change. Resuming execution requires the current checkpoint version and matching source/context digest. Verify/regrading deliberately uses current verifier code and records that distinction. Hash continuity, blob digest checks and document bindings detect local inconsistency; administrators can rewrite all records, so this is not immutable history or general exactly-once side effects.

## Evidence

Runtime tests use temporary PostgreSQL schemas and test blob directories. They cover committed idempotency, concurrent claim, tenant isolation, independent grading, transaction-free inference, strict failures, unknown outcome, queued/running cancellation, lease fencing, checkpoint/version/deadline/attempt budgets, explicit known-result continuation, network-free playback, scope-limited objects and corruption/substitution detection. Fixture provider tests are distinct from real offline-model observations saved under evidence/build002/model-jobs.json.
