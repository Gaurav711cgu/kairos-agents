# Decision record

All choices below are working design defaults, awaiting implementation evidence. Reopen a decision when its trigger occurs; do not add infrastructure merely to enlarge the stack.

## D01 — Lead with a complete developer product

**Choice:** incident investigation and controlled release decisions are the central workflow. SDE/full-stack is the primary portfolio story.

**Why:** one coherent user problem produces meaningful UI, API, storage, concurrency, and testing work. A recruiter can understand the product before reading infrastructure details.

**Alternatives:** a pure statistics library has narrower frontend scope; a broad agent platform risks becoming unfinished; generic observability overlaps mature products.

**Proof:** an outside user can inspect an incident, explain the relevant evidence, compare a fork, and find the release rationale. **Revisit:** interviews reveal a different recurring problem with stronger demand.

## D02 — Use one bounded workflow

**Choice:** support/order decisions over versioned synthetic records, progressing from read-only drafts to approved sandbox adjustments.

**Why:** natural-language ambiguity makes AI useful; real transactional effects create genuine SDE failure cases; business rules allow independent scoring.

**Alternatives:** text-to-SQL is a useful early probe but read-only tasks alone cannot prove effect recovery; live commerce adds access and data dependencies before core value is demonstrated.

**Proof:** reference answers, deterministic policy checks, ambiguous cases requiring abstention, and a local API returning real receipts. **Revisit:** a real pilot provides a better workflow and authorized data.

## D03 — Two languages and simple deployment boundaries

**Choice:** TypeScript/React/Next.js for site/workbench; Python/FastAPI for product API, execution worker, and evaluation. PostgreSQL and object storage provide persistence. Start with one region and independently restartable API/worker processes.

**Why:** frontend engineering remains substantial; Python simplifies model/data tooling; one backend domain model reduces integration overhead. Language count does not establish systems depth.

**Alternatives:** Java or TypeScript backend is valid if target jobs or existing maintainable code justify it. Go ingress is deferred until measured capacity or isolation requirements support another service.

**Proof:** typed API contracts, clean setup, separation of domain/transport/persistence, and measured deployment behavior. **Revisit:** concrete job constraints, team expertise, or sustained workload shows a specific mismatch.

## D04 — Own a narrow execution contract; reuse infrastructure

**Choice:** implement a thin reference runner for this workflow with explicit step boundaries and a pure state transition model. Compare its needs with LangGraph before coding; document the mismatch if custom transitions remain necessary. Use established provider SDKs, validation, migrations, retries, and test tooling.

**Why:** context provenance, command identity, approvals, and the authoritative ledger are core product behavior. A general agent framework is unnecessary. LangGraph checkpoints occur at defined runtime boundaries; they do not automatically meet every Kairos effect or playback contract.

**Alternative:** adopt LangGraph as runner if the spike proves its step/checkpoint interface fits. Do not maintain both runners in the first release.

**Proof:** conformance cases cover pause, resume, crash, duplicate commands, and replay. **Revisit:** integration demand outweighs reference-runner limitations. [Checkpoint documentation](https://docs.langchain.com/oss/python/langgraph/checkpointers).

## D05 — PostgreSQL is execution authority

**Choice:** commit accepted commands, state transitions, ordered audit events, and outbox intent atomically when they belong to the same transition. Derived UI views and optional tracing are rebuildable projections.

**Why:** prevents a successful state change without the corresponding accepted intent/evidence. Serialize transitions per run using a locked run row or version compare-and-swap. Avoid dual authority between a queue, checkpoint file, and database.

**Alternatives:** memory queues are useful notifications but insufficient authority; full event-sourcing infrastructure is unnecessary. Snapshot state and event records are written together; do not claim arbitrary historic reconstruction unless the reducer is versioned and tested.

**Proof:** crash injections around commit, duplicate request tests, and projection rebuild equivalence. **Revisit:** a measured write bottleneck warrants splitting read or ingest paths.

## D06 — Commit before acknowledgement

**Choice:** initially acknowledge critical events only after PostgreSQL commits. Model-provider responses may be lost before capture; record that interval as incomplete/unknown and reconcile or retry within policy.

**Why:** an in-memory ACK cannot establish durable capture. Finite storage implies a choice between pausing, rejecting, or losing data during long outages. Audit-critical execution pauses when recording is unavailable.

**Alternatives:** a durable local spool may later reduce network dependence but adds recovery, corruption, disk-full, and host-loss contracts.

**Proof:** kill worker/API at each acknowledgement window and compare acknowledged identities with recovered rows. **Revisit:** measured commit overhead or intermittent connectivity requires a spool.

Commit durability assumes the documented PostgreSQL/storage configuration. A local durable commit does not promise survival of destruction of the entire host or storage volume.

## D07 — Jobs are notifications; effects are explicit domain records

**Choice:** persist job intent in the authoritative database, dispatch at least once, claim with bounded leases, and fence stale state updates. Evaluate a maintained PostgreSQL-backed task library before writing a job scheduler. Queue completion never substitutes for effect completion.

**Why:** a worker can die after performing an effect and before acknowledging the task. A logical effect has a stable key across retries and a separately tracked receipt.

**Alternatives:** Kafka and Redis queues add consistency boundaries without proving a first-release need. A queue library must support the required transaction integration or be fed through an outbox relay.

**Proof:** two-worker contention, lease expiry, stale worker completion, and receipt reconciliation tests. **Revisit:** scheduling throughput or workload diversity justifies a dedicated broker.

Fencing only prevents external stale effects if the target enforces it. Otherwise target idempotency/reconciliation is mandatory, or automatic retry is disabled.

## D08 — Three execution modes with separate permissions

**Choice:** recorded playback reads captured results with egress denied; verification replay reruns declared deterministic logic; live fork preserves parent history and runs changed behavior in a new sandbox.

**Why:** these modes answer different questions. Recorded evidence cannot establish the success rate of a new model configuration.

**Alternatives:** a single ambiguous Replay button conceals external calls and changes in task state.

**Proof:** egress canary, tool-argument fingerprint mismatch, parent immutability, and clean-fork state assertions. **Revisit:** a new adapter requires a documented extension to the contract.

## D09 — Bind approval to the exact proposed effect

**Choice:** bind tenant, project, actor, tool, normalized arguments, relevant policy/configuration, and expiry. Require separate proposer/approver identities for the demonstrated protected write. Recheck authority at dispatch.

**Why:** approval for an old amount or tool must not authorize a modified proposal. Revocation and cancellation create races that need serialized decisions.

**Alternatives:** generic “approve run” flags are too broad. Client-side disabled buttons are presentation, not authorization.

**Proof:** changed arguments, expired approval, revoked membership, duplicate approval, and cancellation race cases. **Revisit:** pilot requires different separation-of-duties rules.

## D10 — Managed identity, server authorization, tenant defense in depth

**Choice:** use a maintained identity provider/library. Verify token signature, issuer, audience, and expiry; resolve tenant membership server-side. Apply tenant-scoped queries and PostgreSQL row policies with non-owner application roles. Worker access is equally scoped.

**Why:** project must demonstrate real authorization, while custom password/reset infrastructure adds little value. PostgreSQL owners and privileged roles can bypass row security, so role design is part of correctness.

**Proof:** API, worker, blob, stream, report, and direct-database cross-tenant tests. **Revisit:** enterprise identity or residency constraints arise. [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

## D11 — Upload blobs before committing references

**Choice:** use tenant-scoped content-addressed objects with verified digests. Upload first; commit references after confirmation. Garbage collect unreferenced objects only after a grace period and concurrency recheck.

**Why:** PostgreSQL and S3 do not share one transaction. This protocol favors recoverable orphan objects over committed references to missing content.

**Alternatives:** inline small metadata in PostgreSQL; introduce blob chunking only when real context size warrants it. Global deduplication can disclose cross-tenant equality and complicate deletion.

**Proof:** failed upload, failed SQL commit, corrupt download, concurrent GC, and retention tests. **Revisit:** measured storage overhead justifies different chunking or inline thresholds.

## D12 — Distinguish tamper evidence, retention, and privacy

**Choice:** canonicalize versioned event data, chain digests, and export signed manifests/checkpoints to a separate trust boundary for the stronger integrity demonstration. Restrict application writes. Use retention locks only on approved sanitized evidence where deletion obligations are compatible.

**Why:** a rehashable chain is insufficient against an administrator who controls its head. A lock on an object version also does not prove clients retrieved the intended version without a trusted reference.

**Alternatives:** do not promise absolute immutability or write private payloads into irreversible retention by default.

**Proof:** tamper/truncation/reordering and whole-chain-rewrite cases; explicitly state which attacker each check detects. **Revisit:** actual pilot retention requirements. [Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html).

## D13 — Evaluate outcomes with a fixed external grader

**Choice:** version task definitions, environment, scoring, code, context policy, and available model metadata. Hold out task families; pair configurations on the same tasks; treat repeats as nested trials.

**Why:** JSON validity and internal verifier approval can coexist with a wrong business result. The grader stays independent when the agent verifier is an ablation factor.

**Proof:** known-correct/known-wrong grader cases, abstention scenarios, leakage checks, and per-family errors. **Revisit:** new domain changes what successful completion means. [Agent eval guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

## D14 — Fixed-sample, three-state release policy first

**Choice:** predeclare primary endpoint, tolerated degradation, sampling plan, and confidence procedure. Pass requires sufficient evidence against unacceptable degradation plus hard invariant checks. Fail and inconclusive remain distinct.

**Why:** an insignificant difference can reflect insufficient power. Repeatedly running until significance appears invalidates the nominal decision rule.

**Alternatives:** anytime-valid sequential procedures may be considered later after statistical review. Bootstrap resampling is not automatically a p-value; Holm requires valid tests and a declared family.

**Proof:** null calibration, planted degradations, degenerate samples, cost/latency tradeoffs, and comparison with a simple baseline gate. **Revisit:** fixed-sample cost is demonstrably excessive and a valid sequential design is justified.

## D15 — Recruiter site and authenticated workbench serve different visits

**Choice:** public editorial incident experience, engineering case studies, evidence pages, and documentation; authenticated workbench for mutation and private data. Public playback uses curated, sanitized recordings from real controlled executions.

**Why:** first-time visitors need a fast understandable story. Working engineers need precision and dense controls. Both share real components and consistent data contracts.

**Alternatives:** KPI-wall homepage and empty signup gate lose the product story. Unrestricted anonymous live runs expose operating cost and abuse.

**Proof:** WEBSITE_SPEC.md acceptance checklist, keyboard/mobile browser tests, and small usability sessions. **Revisit:** user research shows entry points or workflows differ.

## D16 — Ship incrementally with reversible schema changes

**Choice:** local Compose, hosted preview, one-region pilot, managed database/backups where suitable. Use expand/migrate/contract changes, restore drills, and source-bound release artifacts. Application rollback must remain compatible with the deployed schema.

**Why:** tests alone cannot establish recoverability; a deployment is useful only when operators can diagnose and reverse failures.

**Alternatives:** Kubernetes and active-active operation are deferred. Dump/restore demonstrates backup recovery; PITR requires a valid base backup and continuous WAL history.

**Proof:** clean-checkout deployment, migration compatibility test, off-host restore with measured recovery, and receipt reconciliation before resuming writes. **Revisit:** actual availability/recovery requirements exceed single-region design. [PostgreSQL PITR](https://www.postgresql.org/docs/current/continuous-archiving.html).

## D17 — Deliver a bounded reference slice before a remote-model runtime

**Status:** accepted for build001,2026-10-11.

**Choice:** reuse the existing repository; add one Python/FastAPI/PostgreSQL execution path and a new incident-led Next.js site. Execute a small deterministic reference policy, independently grade full scenario facts, and persist run/events/receipt in one transaction before response. Keep legacy Go/harness/engine outside this path.

**Why:** a real, reviewable database/UI contract can be verified cheaply before model orchestration or ingestion throughput is justified. Reference failure comes from a deliberately omitted context exception and is labeled accordingly.

**Proof:**27 passing backend tests, including13 real PostgreSQL tests, plus browser-driven fork, tenant rejection, rollback and identity-bound integrity tests. See build001 evidence.

**Limit/revisit:** current synchronous transaction must not surround future remote model calls. Introduce durable jobs/intents/results and unknown-outcome handling first. This is a fresh full-scenario rerun, not checkpoint resume or an arbitrary-code sandbox.

## D18 — Preserve failed model-fit evidence and keep suites separate

**Choice:** run an available cached0.5B model offline on four explicit development cases with strict JSON/business/evidence scoring. Keep original responses.

**Result:**0/4 passed: arithmetic error; exception failure; inappropriate abstention; JSON fences rejected. The missing-delay response expresses sensible abstention but still violates the strict transport contract.

**Why:** a tiny local model is useful for discovering failure modes; hiding failures or equating schema repair with correct reasoning would destroy the evidence. The probe uses non-refundable exception and >30minute rules, while the product fixture uses prior-compensation and >=30minutes. No direct comparative score is valid.

**Next:** align versioned tasks, route arithmetic through a deterministic tool, test structured-output support, preserve exceptions, and evaluate fresh held-out families. Four single trials establish neither general model quality nor a release decision. No fine-tuning or multi-agent council is justified yet.

## D19 — Local interactive demo, production read-only viewer

**Choice:** server-held developer credentials; local same-origin preserve-only fork proxy gated by development mode, explicit flag and credential. Production always rejects mutations and disables the button. Managed identity remains a separate milestone.

**Why:** recruiters can inspect real evidence without exposing public computation or a shared write credential. Browser retries persist their command identity before dispatch; successful navigation clears it and new parents receive new identities.

**Proof:** actual browser forks and chained forks, local foreign/missing-origin rejection, unsupported-policy rejection, production403 despite enabled flag, and disabled production UI.

**Limit/revisit:** do not expose developer mode on a public deployment. Replace with managed identity, role/tenant membership, quotas and session controls before a private remote workbench is offered.
