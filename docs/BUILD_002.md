# Kairos build002 — local flagship implementation report

Recorded 2026-10-11. The local full-stack product is implemented and verified. The configured small model is **not release-qualified**. Public hosting, external users and customer adoption remain unverified external gates. This report supersedes build001's current-state summary; build001 evidence remains historical and unchanged.

## What a reviewer can use

Start at the public website on `http://127.0.0.1:3100/`. The first interaction reveals an omitted policy exception. The incident inspector connects source facts, context selection, decision, independent grade and event payloads. The model ledger exposes actual captured failures. Reports expose task rows and bounds. The authenticated workbench supports private queued executions, cancellation, fresh forks, supported known-response continuation, calibration, proposal review and sandbox receipts.

The active stack is Next.js16/React19, Python/FastAPI, PostgreSQL18, a separate Python worker and a local model HTTP adapter. Keycloak26.8 supplies a real OIDC provider. Legacy Go ingestion and old harness modules remain outside the product path. Filesystem content-addressed objects are implemented; S3 is not.

## Executed acceptance evidence

| Check | Observed result | Artifact |
|---|---|---|
| Backend correctness | 169 passed, two dependency deprecation warnings; real PostgreSQL and real local provider flows included | [final test log](../evidence/build002/backend-tests-final.txt) |
| Frontend command boundary | Four stream/byte-budget tests passed | [boundary tests](../evidence/build002/frontend-boundary-tests.txt) |
| Frontend quality | ESLint and TypeScript passed | [lint](../evidence/build002/frontend-lint.txt), [types](../evidence/build002/frontend-types.txt) |
| Locked clean builds | API lock installed in clean Python image; `npm ci` and production Next build completed in clean Node24 image | Docker build logs in evidence directory |
| Dependency audit | Zero known findings for full npm dependency tree and pinned API lock at the recorded checkpoint | [npm](../evidence/build002/npm-audit-all-final.json), [Python](../evidence/build002/python-audit.json) |
| Actual images | Non-root API UID10001/web UID1000; private idempotency, conflict, body limit, public web, anonymous denial, production mutation denial, unknown report404 and explicit outage behavior passed | [container smoke](../evidence/build002/docker-smoke.json) |
| Real process crash | Two SIGKILL branches passed; unknown dispatch refuses continuation, captured response continues without a second model dispatch | [final crash drill](../evidence/build002/worker-crash-drill-final.json) |
| Combined recovery | Fresh database and fresh object directory verified seven jobs, seven reference runs,12 object references and10 distinct objects; initializers applied twice | [database/blob restore](../evidence/build002/restore-with-blobs.json) |
| Bounded local HTTP load | 120 requests, concurrency8, zero errors; eight duplicate requests produced one run; p95 93.087ms | [load report](../evidence/build002/load.json) |
| Final manual browser flow | Real provider login, private reference/model queue, raw output, approval, sandbox dispatch, receipt after reload, logout, context toggle,390px/1440px layouts, semantic report filter/expansion and bounded trace interaction | [browser acceptance](../evidence/build002/browser-acceptance.json) |

These are local measurements. Load excludes inference and is not a production capacity or SLO claim. Image smoke uses a separate development-auth schema; production identity has separate protocol/configuration tests. Hosted CI has not run. Browser acceptance is manual, not a reusable full E2E suite. The two warnings concern upstream httpx-to-httpx2 transitions; an untested client migration was not introduced to suppress them.

## Why these decisions

**Commit before acknowledging.** A memory queue only proves receipt by a process. PostgreSQL commits command identity, state and events before success. Scoped idempotency keys bind payload digests, so retries reconcile and changed commands conflict. Disabled database fsync is rejected. This is local database durability, not survival of losing every host and backup.

**Use a small durable worker contract.** A model request cannot hold a database transaction open. Workers claim with `SKIP LOCKED`, leases and fencing tokens. PostgreSQL owns time authority. Each job permits one model dispatch, at most three claims and a180-second deadline. Intent is durable before dispatch; the response is durable before grading. If dispatch may have happened but no response was captured, the outcome is UNKNOWN. Blind retries would hide ambiguity and spend.

**Make recovery narrower than replay marketing.** Recorded playback reads stored evidence without inference or effect dispatch. Known-response continuation requires matching checkpoint/source fingerprints. A fresh fork starts the entire scenario with new context policy and lineage. Arbitrary historical-step resume is unsupported. Cancel is cooperative and cannot undo work already sent.

**Keep arithmetic and permission outside the model.** The model classifies refund, zero or abstain. Deterministic code calculates cents. Strict unmodified JSON parsing rejects duplicate keys, nonfinite values, extra fields, incomplete output and missing required evidence. A grader reads full source truth, independently of the selected model context. Model text never grants approval.

**Separate identity from authorization.** Authlib/PyJWT validate code flow, PKCE, state, browser binding, nonce, issuer, audience, signature, expiration and authorized party. Opaque HttpOnly sessions are hashed at rest. Membership is checked on every request and supplies tenant and role. Viewer writes and foreign records are denied. Production rejects developer credentials. Production login, callback and website must share one HTTPS public origin because cookies are host-only. A trusted edge preserves Host and overwrites forwarded protocol headers.

**Bind approval to a reviewed proposal.** Admin approval binds version, source decision digest, tenant, target, order and amount, and expires after15minutes. Dispatch rechecks those facts under a lock. The synthetic target adjustment and receipt commit in one PostgreSQL transaction. Stable order identity prevents an equivalent fork from producing a second adjustment. Receipt GET supports reconciliation after client command-key loss. This does not prove general exactly-once external payments; no money moves.

**Use positive evidence for release.** The fixed paired Hoeffding bound uses alpha0.05, margin0.10 and at least1,024 independent seeded procedural task draws. PASS requires the lower bound above−0.10. FAIL requires a hard invariant failure or an upper bound below−0.10. Otherwise the verdict is INCONCLUSIVE. An insignificant regression cannot approve release. Claims apply only to the declared synthetic generator. Provider errors remain planned failed outcomes, rather than disappearing from denominators.

**Make the frontend part of the investigation.** The populated dark site uses real source records, context controls, URL-selected events, keyboard movement, raw payloads and report downloads. Trace rendering stays bounded to80 event buttons. Reduced-motion preferences disable decorative card motion. Initial loading, empty, unavailable and failed-record states are distinct. Active fetchers and mutation proxies never substitute canonical sample data for an outage or manufacture successful actions.

## Model evidence and its setback

The six-cell durable development probe passed **0/6**: four wrong policy outcomes, one missing required evidence reference and one strict-schema failure. Five responses parsed; that does not mean five successful decisions. Exact input and output remain in [model-jobs.json](../evidence/build002/model-jobs.json).

The separate32-task development batch passed three planned tasks. Twelve actual model responses were captured;20 tasks had provider failures: one ReadTimeout and19 HTTPStatusError responses from the busy service. This is not32 valid model-quality observations. The single-slot provider was still busy after a timed-out call; subsequent requests failed rather than silently queuing. The original batch is preserved in [model-development-v2.json](../evidence/build002/model-development-v2.json).

The adapter now records a60-second cooperative generation budget, busy state and finish reason. A private final smoke call returned after29,005.368ms with35 output tokens and EOS. Its zero decision matched the business disposition but omitted the required exception citation, so the strict grade still failed. No permissive parser or invented success was used. The smoke does not replace the initial six-cell result or qualify the model.

Next model-quality work is a separately versioned experiment: select a model that fits the contract, predeclare the development change, inspect structured-output and evidence failures, then run an untouched adequately sized model holdout. Compare quality, provider availability, cost and latency separately. Do not spend1,024 calls on a candidate that fails development invariants. Model research would require a distinct research contribution and study; this is applied AI/evaluation engineering.

Fresh final deterministic holdout calibrations are saved privately: [null PASS](../evidence/build002/null-calibration-final.json), [planted FAIL](../evidence/build002/planted-regression-final.json), [reference repair PASS](../evidence/build002/reference-repair-final.json). Calibration validates the release rule's behavior; it does not establish model quality. Earlier published reports retain their original source snapshots.

## Failures found and closed

- Legacy SQL read-only validation could be bypassed with comments; legacy replay missed changed model responses. Those paths were excluded, not promoted. [Reuse review](LEGACY_REUSE_REVIEW.md) records reproductions and useful patterns.
- Active UI changes had introduced fake fallback records, demo authentication and simulated guarantees. Those active paths were replaced with actual API records and explicit failures; the current visual design was preserved.
- Worker host-clock skew and non-UTC sessions could undermine lease authority or hash serialization. Database time and normalized UTC encoding now have regressions.
- Expired or stale approvals, equivalent forks, lost responses and command-key loss could invite duplicate effects. Versioned locking, source rechecks and durable receipt lookup now cover the supported sandbox contract.
- Streaming requests could exceed the limit before rejection. Next.js cancels observed bodies above32KiB; ASGI enforces the same bound before JSON parsing and authentication dependencies. Tests include absent/false lengths and multibyte UTF8.
- Separate production callback/web hosts would create a login loop. Configuration now rejects split origins and incorrect callback/login paths.
- Five development-tool audit entries were resolved by replacing the unnecessary vulnerable lint dependency chain while retaining React/hooks/accessibility lint checks. Final full audit reports zero findings.
- A PostgreSQL-only backup omitted model objects. The combined drill holds a consistent database snapshot, copies exactly referenced objects, restores into new targets and verifies every reference. Private backup files are0600, directory0700; archive traversal, symlinks, duplicates, corruption and unexpected objects are rejected.
- Local services stopped during the session pause. The failed environment run was sanitized and preserved; services restarted against persistent data, and the complete suite passed afterwards. A passing later run does not erase the outage.

## What each role can reasonably infer

| Role/depth | Evidence earned | Boundary still open |
|---|---|---|
| SDE/backend | Transaction design, versioned state transitions, concurrency, idempotency, tenant checks and regression cases | Large production traffic and operational ownership |
| Full-stack/frontend | Authenticated command flows, server proxy boundaries, interactive context/timeline, responsive layout, raw evidence and failure states | Independent usability/accessibility study and broad browser matrix |
| Applied AI | Real inference, captured context, strict outputs, deterministic tools, independent grades and honest failure taxonomy | A qualified useful model and untouched model holdout |
| Harness/loop | Durable bounded single-call loop, fencing, deadlines, cancellation, exact captures and narrow continuation | General multi-tool orchestration and arbitrary checkpoint resume |
| Statistics | Explicit sample plan, conservative paired bound, hard gates and calibration | Real-world generalization, multiple-metric policy and production drift study |
| FDE | Synthetic discovery brief, scoped workflow, deployable artifacts, permissions and debugging narrative | Customer discovery, actual customer data integration and measured adoption |

No single project proves every job description. This one gives reviewers concrete implementation and tradeoffs to examine. Do not claim research, adoption, Kubernetes operations, S3 deployment, immutable history or commercial payments from this evidence.

## Delivery and next external gates

Dockerfiles and production Compose package API, worker, database and web. Deployment requires a real HTTPS origin/TLS edge, protected secrets, production OIDC persistence and memberships, configured model adapter, offsite backup/retention and monitoring. The CI definition covers integration, provider flows, calibration, stream boundaries, audits, lint, types and build. No cloud account or public endpoint was configured.

For recruiter review, use the public incident first, then the failure ledger and a release report. Link a real repository only after review and publishing. The next outside-user pilot should ask an unfamiliar developer to find the missing exception, explain the verdict, create a controlled comparison and locate its receipt without coaching. Record task completion and blockers; do not invent adoption metrics. [Discovery brief](DISCOVERY_BRIEF.md) contains the study hypothesis.

Use [BRAIN.md](../BRAIN.md) for the next session, [ARCHITECTURE.md](../ARCHITECTURE.md) for contracts, and [planning decisions](planning/DECISIONS.md) for why. The evidence manifest fingerprints the working tree and local receipts; it is not a signed or immutable attestation.
