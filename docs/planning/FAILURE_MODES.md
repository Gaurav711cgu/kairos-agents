# Failure register and recovery contract

This register covers the declared product and failure model. It is not a promise to anticipate every possible defect. Every new incident adds a regression case and a documented recovery decision.

Threat/fault assumptions: processes can crash at any instruction; networks time out, duplicate, delay, or lose responses; two workers/users may race; providers drift or fail; task text and candidate code can be untrusted. Initial deployment assumes one region. Host/volume destruction requires backup recovery and may exceed the local-commit guarantee.

P0 means an integrity, tenant, effect, or evidence-truth violation. P1 means material availability, quality, or usability failure. P2 means a product/portfolio weakness. Priority is for sequencing, not an estimate of occurrence probability.

## F01 — Acknowledged event disappears (P0)

Cause: ACK before durable commit. Prevention: commit critical event and state together, then ACK. Injection: crash before commit, after commit/before response, after response. Expected: retry finds identical committed identity or creates the first valid one; never fabricated success. Evidence: acknowledged-ID reconciliation and crash-point matrix. Decisions: D05, D06.

## F02 — Duplicate identity carries different payload (P0)

Cause: retries or clients reuse keys incorrectly. Prevention: identity includes tenant scope; store request hash. Injection: same key/same body, then same key/changed body. Expected: first is replayed response, second is explicit conflict. Evidence: API/SQL assertions. Decisions: D05, D10.

## F03 — Queue or database stays unavailable (P1)

Cause: outage, saturation, full disk. Prevention: bounded concurrency and queue admission; reserve connection capacity for control/read operations; pause audit-critical work. Injection: disconnection, slow commits, exhausted limits. Expected: visible degraded state, bounded memory, retriable rejection; no lost-data success. Evidence: backlog age and recovery measurements. Decisions: D06, D07.

## F04 — Two workers execute the same logical job (P0)

Cause: lease expiry while original worker is alive. Prevention: lease token, conditional state updates, target effect idempotency. Injection: suspend worker past lease, allow another claim, resume original. Expected: stale database updates rejected; target sees at most one committed effect under its tested contract. Unsupported targets escalate. Evidence: independent receipt count. Decision: D07.

## F05 — Effect succeeds but response/receipt is lost (P0)

Cause: timeout or crash after external commit. Prevention: stable effect key and receipt lookup. Injection: service commits then drops response. Expected: UNKNOWN state, reconcile same key, no blind new-effect retry. If target cannot reconcile, require human resolution. Evidence: service row, receipt, intent lineage. Decisions: D07, D09.

## F06 — Approval/cancel/retry decisions race (P0)

Cause: two tabs/users or in-flight requests. Prevention: serialized state transition, version preconditions, approval binding and dispatch recheck. Injection: stale approval, changed arguments, revoke-before-dispatch, cancellation alongside dispatch. Expected: clear winning transition and conflict for stale action; already-dispatched effects reconciled. Cancellation is not a rollback promise. Decisions: D05, D09.

## F07 — Object upload and SQL disagree (P0)

Cause: separate transaction systems. Prevention: verify object first, then commit reference; grace-period orphan GC. Injection: upload/commit failure and concurrent GC. Expected: no new committed missing reference; orphan recoverable or safely removed. Existing missing blobs mark evidence incomplete. Decisions: D11.

## F08 — Evidence is corrupt, truncated, reordered, or rewritten (P0)

Cause: bug, unauthorized write, privileged manipulation. Prevention: versioned canonical encoding, digests, chained sequence, externally trusted manifest. Injection: mutate one block, truncate tail, reorder events, replace chain/head. Expected: digest/head comparison catches supported tampering; total compromise of all trust anchors remains outside guarantee. Decision: D12.

## F09 — Replay calls real tools (P0)

Cause: wrong adapter, default network routing. Prevention: mode-specific tool registry plus enforced egress deny. Injection: malicious URL and DNS, absent fixture, startup failure. Expected: playback refuses external call and fails visibly; no fallback to production. Evidence: external canary and blocked-connection logs. Decision: D08.

## F10 — Fork alters parent or targets primary state (P0)

Cause: reused mutable IDs, credentials, environment. Prevention: new fork namespace, immutable lineage references, separate sandbox credentials/state. Injection: startup/restore failure and mixed run identifiers. Expected: parent/primary canaries unchanged; fork stops. Decisions: D08–D10.

## F11 — Cached result reused for changed arguments (P0)

Cause: weak fingerprint or sequence-only matching. Prevention: tool/schema/arguments/scenario/config fingerprint. Injection: same event position, different amount/order/query. Expected: unsupported replay or explicitly resolved sandbox call; never pretend baseline output belongs to new input. Decision: D08.

## F12 — Tenant data leaks through secondary path (P0)

Cause: scoped list endpoint but unscoped blobs, streams, reports, workers, search, or exports. Prevention: tenant checks at each boundary, non-owner database roles, short-lived scoped downloads. Injection: foreign identifiers and signed-link reuse across users. Expected: denial without revealing payload/existence unnecessarily. Revocation semantics for already-issued URLs must be documented. Decision: D10.

## F13 — Prompt text or candidate code gains authority (P0)

Cause: treating model text as permission, unsafe rendering, privileged CI. Prevention: deterministic tool authorization; trusted launcher; no production secrets in candidate sandbox; escaped/sanitized rendering; scoped provider gateway. Injection: tool-return injection, secret-exfiltration request, malicious HTML, candidate flag modification. Expected: no unauthorized effect or secret access. Decisions: D09, D10, D16.

## F14 — Loop never ends or overruns spend (P1)

Cause: repeated retries/actions, model stalls, parallel admission races. Prevention: finite step/time/retry budgets, reservations, call token caps, provider timeout, cancellation. Injection: endless tool requests and delayed provider results. Expected: explicit stop, finite active requests, recorded unknown billing where needed. Estimated budgets do not guarantee provider invoices without provider-side controls. Decisions: D04, D06.

## F15 — Resume uses incompatible code/checkpoint schema (P0)

Cause: deployment changes reducer, model adapter, or state format. Prevention: versioned snapshot/reducer metadata, explicit compatibility/migration checks. Injection: old checkpoint/new worker and missing dependency. Expected: supported migration or paused incompatible run; no silent reinterpretation. Decisions: D04, D05, D16.

## F16 — Compaction drops decisive evidence (P1)

Cause: token-only truncation or poor summary. Prevention: provenance links, required policy/evidence blocks, explicit token accounting, abstention on missing context. Injection: policy exception omitted, stale retrieval, oversized tool response. Expected: recorded context difference and independent wrong-answer detection. Keeping a block helps only if experiments support it. Decisions: D02, D13.

## F17 — Valid JSON receives a wrong-success grade (P0)

Cause: grader checks shape instead of business outcome; verifier grades itself. Prevention: fixed external assertions over result and service state. Injection: schema-valid wrong amount, invented evidence, double adjustment. Expected: fail even if internal verifier approves. Decision: D13.

## F18 — Evaluation leaks answers or cross-trial state (P0)

Cause: shared files/history/cache; answer hints in prompts; candidate edits grader. Prevention: immutable task/grade manifests, isolated initial state, held-out families, trusted scoring job. Injection: planted answer file, leftover receipt, modified expected result. Expected: isolation/leakage test fails; contaminated runs excluded with reason, not silently deleted. Decision: D13.

## F19 — Statistical gate is overconfident (P0)

Cause: pseudoreplication, tiny samples, degenerate bootstrap, optional stopping. Prevention: declared estimand/unit, nested trial handling, fixed sample plan, honest inconclusive state. Injection: few distinct tasks with many repeats, all-equal outcomes, repeated interim checking. Expected: unsuitable analysis rejected or qualified; no automatic pass. Decision: D14.

## F20 — Aggregate improvement hides important failures (P0)

Cause: task mix shifts or averages hide policy exceptions. Prevention: fixed weights, absolute qualification rules, family-level breakdowns, hard invariant gate. Injection: candidate improves common cases while failing all critical exceptions. Expected: release blocked or inconclusive under declared policy. Decisions: D13, D14.

## F21 — Provider/environment drift confounds experiment (P1)

Cause: model alias changes, time-of-day throttling, hardware contention. Prevention: record available provider IDs, interleave A/B, freeze scenario snapshots, separate infrastructure failures. Injection: throttle one window and change adapter. Expected: report identifies compromised comparison; pinning limits are disclosed. Decision: D13.

## F22 — API and UI disagree about outcome (P0)

Cause: schema drift, stale mutation response, fallback success state. Prevention: generated contracts, explicit state enum/error model, server authority and request IDs. Injection: malformed payload, partial response, 401/403/409/429/503, stale tab. Expected: visible correct state and safe retry; no sample-data substitution. Decisions: D03, D15.

## F23 — Stream reconnect loses/duplicates/reorders events (P1)

Cause: network drop, multiple subscriptions, retention. Prevention: persisted cursor, sequence dedupe, catch-up query, reset-to-snapshot protocol. Injection: disconnect mid-stream, reconnect repeatedly, old cursor. Expected: same ordered authoritative timeline without phantom completion. Decisions: D05, D15.

## F24 — Large trace freezes browser or is inaccessible (P1)

Cause: unbounded rows/diffs, main-thread processing, pointer-only design. Prevention: cursor pagination, bounded cache, virtualization, lazy payloads, cancellable diff work, semantic text alternative. Injection: representative large trace, long JSON, keyboard/reduced-motion/mobile use. Expected: measured interaction budget and complete core task. Decision: D15.

## F25 — Browser double submission creates duplicate fork/effect (P0)

Cause: double click, reload, timeout retry. Prevention: client command identity plus server idempotency; no optimistic final success. Injection: repeated click and response loss. Expected: one logical command, recoverable status. Decisions: D05, D09.

## F26 — Migration/restore breaks live service or repeats effects (P0)

Cause: incompatible schema rollback, incomplete backup, old intent state after restore. Prevention: expand/contract migrations, backup manifest, off-host restore test, receipt reconciliation before writes resume. Injection: deploy old app against expanded schema; restore pre-receipt backup with target effect already committed. Expected: compatibility or deliberate stop; no duplicated effect. Decision: D16.

## F27 — Benchmark hides overload (P1)

Cause: closed-loop load slows with service; errors/dropped attempts omitted; warm cache only. Prevention: declared arrival-rate test, offered/admitted/completed counts, cold/warm cases, queue-age and recovery reporting. Injection: sustained overload and dependency delay. Expected: visible bounded rejection and measured recovery, not misleading throughput. Decisions: D06, D16.

## F28 — Product solves no observed user problem (P2)

Cause: technology-driven scope. Prevention: discovery brief, baseline workflow, observed user tasks. Injection/check: ask a user to diagnose a realistic incident without author narration. Expected: identify friction and revise scope. One user is formative feedback, not market validation. Decision: D01.

## F29 — Website looks impressive but misrepresents implementation (P0)

Cause: fake live labels, decorative charts, fabricated stats/commits, inaccessible demo. Prevention: evidence-linked content, labeled recordings, honest unavailable states, proof navigation. Check: every visible quantitative or implementation claim resolves to an artifact. Missing evidence removes or qualifies claim. Decision: D15.

## F30 — Scope and framework overlap undermine completion (P2)

Cause: adding connectors, queues, models, or infrastructure before core journey works. Prevention: one active gate, library comparison, defer list, explicit revisit conditions. Check: feature must improve current user journey or acceptance gate. Expected: narrow completed slice; framework comparisons show actual additional value. Decisions: D01, D03, D04.

## Techniques and artifacts

- Use stateful property tests to generate command sequences and check invariants after each transition. Persist failing seeds/minimized traces. [Hypothesis](https://hypothesis.readthedocs.io/en/latest/stateful.html).
- Use deterministic barriers/crash hooks around commits and effects before random chaos. Add network delay/reset experiments with [Toxiproxy](https://github.com/Shopify/toxiproxy).
- Use real disposable PostgreSQL/object storage in integration tests. [Testcontainers](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/).
- Use metamorphic checks: duplicate command preserves identity; shuffled arrival preserves declared ordering; playback reproduces captured digest; unrelated added evidence does not bypass permissions.
- Collect browser traces on failed journeys so DOM state, requests, and timing are inspectable. [Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer).

These techniques increase evidence coverage; they do not constitute proof against every failure or replace review of the actual implementation.
