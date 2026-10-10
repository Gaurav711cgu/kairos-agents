# Kairos build002 — complete local flagship

User explicitly requested completing remaining work before a final report. Scope: all implementable local product, correctness, identity, harness, evaluation, delivery and presentation gates. Actual public hosting, external model-provider credentials and outside-user adoption cannot be fabricated; prepare deployable artifacts and record those external gates distinctly.

## Shared boundaries

Retain existing reference API and public incident contract. New domains get separate SQL files/modules; app.py integration and dependency lock/env/compose are root-owned to avoid collisions. All new schemas initialized idempotently by their repository. Changes additive; preserve build001 evidence. Do not print secret files. Existing app local credentials are a separate development mode; production OIDC must not silently accept them.

Public website retains editorial design. Private workbench gains real identity, queued runs, captured model requests/results, recovery controls, evidence download and release report. Public reads remain sanitized. No public unlimited compute.

## Work split

1. Runtime specialist owns kairos_api/jobs*.py, kairos_api/model*.py, kairos_api/worker.py, kairos_api/schema_jobs.sql, scripts/serve_local_model.py, tests/test_jobs*.py. Durable PostgreSQL jobs, fenced leases, cancellation/deadline/budgets, actual local model HTTP execution, raw strict outputs, context capture, controlled replay and explicit recovery. Separate router factory accepts dependencies; no app.py edits.
2. Identity specialist owns kairos_api/identity*.py, kairos_api/schema_identity.sql, tests/test_identity*.py, infra/identity/, scripts/setup_identity.py. Keycloak OIDC using Authlib/PyJWT libraries, server-side sessions, state/nonce/PKCE, explicit subject-to-tenant membership, role checks/revocation, tenant isolation. Local provider Docker current official26.8.0 on127.0.0.1:8088. API callbacks8100, frontend3100. No app.py/settings/env/compose modifications; supply integration hook and needed variables.
3. Product/evaluation specialist owns dashboard active source/config/package/lock, kairos_api/evaluation*.py, kairos_api/schema_evaluation.sql, tests/test_evaluation*.py, scripts/run_evaluation.py. Complete private workbench/pages/reports, fix dev audit without disabling security or laundering reports. Implement fixed-sample pass/fail/inconclusive policy with paired task endpoint, hard invariant blocker, predeclared margin/minimum independent tasks, conservative finite-sample bound or justified library method. Honest deterministic calibration separate from model observations. Root integrates app.py.
4. Root owns app.py integration, effect approval/receipt sandbox modules/tests, blob/recovery/load/deployment scripts, compose, locks, CI, docs, memory, actual model/identity/browser integration and final review.

## Contracts to agree before coding

Runtime job router factory: create_jobs_router(tenant_dependency, key_dependency, repository_dependency=None). Tenant dependency returns tenant_id string. Repository defaults DATABASE_URL. POST /api/jobs accepts {scenario_id:"late-order-exception"|"late-order-standard"|"insufficient-evidence",policy:"compact"|"preserve",runner:"reference"|"model",publish:false}; 202 durable identity. Idempotency-Key required. GET /api/jobs lists scoped summaries; GET /api/jobs/{id} detail; POST /api/jobs/{id}/cancel; POST /api/jobs/{id}/recover supports explicit known-result continuation, never hidden redispatch. GET /api/public/jobs exposes published synthetic executed summaries/detail. Successful jobs link persisted existing IncidentDetail if feasible; otherwise expose separate job result with decision/grade/events/context/request/response. Exact route/output contract shared with product specialist directly.

Model endpoint local port8120 /generate POST receives messages/context and max_tokens; returns raw_response, rendered_request, model identifier/revision, input/output tokens and timing. Worker captures request intent before dispatch and full provider response after. No network call under a PostgreSQL transaction. Model allowlist/configured endpoint only. Grader independent of selected context; deterministic arithmetic tool after classification preferred over model numeric arithmetic. Preserve all failures. Development and held-out task suite alignment required before comparative scores.

Identity integration factory install_identity(application,database_url) returns callable identity(request) mapping validated session/bearer to principal {subject,tenant_id,role}; server secret required. Expose GET /api/auth/me (401 anonymous), GET /api/auth/login, GET /api/auth/callback, POST /api/auth/logout. Browser host same127.0.0.1 API/web cookie sharing via ports; HttpOnly session cookie, Secure in deployment, strict expected Origin for cookie mutations. No tokens in browser JSON/localStorage. Managed membership seeded for synthetic local accounts only. Cross-tenant/roles/missing/expired/wrong-issuer/wrong-audience tokens denied. Frontend requests API via server proxy forwarding session cookie, not exposing tokens.

Evaluation factory/router to root. Every report includes task-set/code/grader/config digests, actual per-task paired outcomes, method/margin/sample plan, hard checks, counts and limits. Gate must not equate insignificant regression or degenerate bootstrap to safety. Store complete raw input/output report and expose actual public curated reports + scoped private report actions.

Effect sandbox: versioned approval binds tenant/run/proposal digest/state; target adjustment transaction uses stable effect key and receipt, no money. Response-loss after commit reconciles same receipt. Replay has no external dispatch; forks cannot inherit approval. Explicit UNKNOWN semantics where target contract unsupported. No claim of general exactly-once effects.

## Local completion gates

- Real Keycloak login + private browser workbench, tenant/member/role denial; production dev credential rejection.
- Real local model job ledger; strict output capture, bounded attempts, cancellation, crash/recovery fencing, checkpoint/version validation, no DB transaction during inference.
- Context/blob integrity with scoped reads; network-free recorded playback and verification; explicit fresh-fork vs supported checkpoint continuation distinction.
- Approval/effect race and lost-response reconciliation in real PostgreSQL sandbox; independent effect count.
- Versioned aligned task evaluation; pass/fail/inconclusive and null/planted calibration; no manufactured model success.
- Actual PostgreSQL backup restore into new database, additive migration checks, declared load measurements and browser large-trace interaction limits.
- Full dependency audit resolved if compatible versions exist, otherwise replace unnecessary affected lint dependency chain; no blanket ignore/false clean claim.
- Clean locked Python + frontend setup, tests, production build, Docker deployment/CI definition, accessible populated site, browser checks and screenshots.
- Compact brain, decisions, failure/evidence registry updated. Final report only after implementable gates complete; external gates explicit.
