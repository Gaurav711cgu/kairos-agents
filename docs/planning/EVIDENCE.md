# Evidence contract and capability depth

Status: build001 has scoped local implementation results. Capability acceptance criteria remain proposed gates until explicitly covered; no row marks a whole discipline complete.

## Evidence manifest

For each result preserve: evidence ID, date/time/timezone, source commit or working-tree digest, dependency/image versions, hardware/runtime, task/scenario/grader versions, configuration, command, raw artifacts, offered/admitted/completed counts where relevant, failures/exclusions, analysis script, and limits.

Public artifacts are sanitized copies with explicit provenance. Keep private raw payloads out of public static builds. Evidence regeneration must invalidate stale website claims when versions or results change. Hashes verify correspondence only relative to a trusted manifest; they do not establish that a fabricated experiment was executed.

Recommended future artifact layout:

```text
evidence/<evidence-id>/manifest.json
evidence/<evidence-id>/method.md
evidence/<evidence-id>/raw/
evidence/<evidence-id>/analysis/
evidence/<evidence-id>/limitations.md
```

These paths are proposed, not currently populated results.

## E01 — SDE fundamentals and explainable implementation

**Build:** explicit state model, versioned transitions, typed contracts, meaningful domain boundaries, scoped indexes, command/effect identity, and bounded resource use.

**Why this is depth:** reviewers can trace correctness across components and inspect algorithm/data-structure choices. A long feature list does not show understanding.

**Proof:** stateful property tests, an actual minimized race/crash counterexample and repair, query plans on declared data, CPU/memory profiling, and ADRs comparing alternatives. Explain sorting/index/diff/queue complexity where it governs measured behavior; do not add vector clocks to a sequential runner for interview decoration.

**Limits:** a small local benchmark is not hyperscale production experience.

## E02 — Backend, concurrency, and database correctness

**Build:** commit-before-ACK, concurrent claims, scoped authorization, outbox intent, effect receipts, migrations, recovery.

**Proof:** real PostgreSQL integration; two-worker lease test; exact crash-window table; independent target effect count; old/new schema compatibility; restore with external receipt reconciliation.

**Key metrics:** accepted/committed identity reconciliation, duplicate committed effects under supported target contract, conflict/rejection counts, queue age, transaction latency, and recovery duration. Safety checks are exact assertions for tested scenarios, not probabilistic averages.

## E03 — Frontend engineering

**Build:** timeline/context/fork/report journeys; bounded rendering and data loading; URL state; reconnect; meaningful errors; mobile/keyboard interaction.

**Proof:** Playwright journeys and failure traces, browser performance profiles on the declared large-trace fixture, API contract checks, contrast/focus review, and documented usability findings.

**Key metrics:** measured interaction latency, memory growth, loaded row count, layout stability, task completion, and rendering bottleneck before/after a justified optimization. Distinguish lab measurements from field percentiles.

**Limits:** visual polish without these interactions supports design claims, not full frontend depth.

## E04 — Applied AI and context engineering

**Build:** useful task-model fit, exact context capture, retrieval/compaction lineage, abstention, independent business graders, controlled harness ablations.

**Proof:** held-out task-family results with raw model outputs, per-family confusion/error categories, failures, abstention/coverage tradeoffs, cost, and latency. Compare a simple baseline with the loop. Show why context changes improve or fail to improve outcomes.

**Limits:** model API integration and prompt experiments are applied AI. Claim model research only with a separately defined research question, method, relevant baselines, robust evaluation, and reproducible contribution. Do not add fine-tuning without observed need.

## E05 — Harness engineering

**Build:** tool registry and schemas, permission boundary, context assembler, evidence references, verifier interface, durable transition checkpoints, and observable stop reasons.

**Proof:** tool-argument mismatch rejection, missing-context behavior, permission enforcement despite prompt injection, exact request reconstruction, and replay conformance.

**Limits:** “harness engineering” is a useful description of these responsibilities; do not present it as a universal standardized job taxonomy.

## E06 — Loop engineering

**Build:** step/deadline/retry/spend controls, pause/resume/cancel, repeated-action detection, checkpoint compatibility, effect reconciliation.

**Proof:** generated command sequences and deterministic crash points; runaway loop termination; cancellation race handling; bounded retries; explicit unknown-result states; resumed execution lineage.

**Limits:** changing a loop can improve one workflow and harm another. Report task scope and ablation results rather than declaring a universally optimal loop.

## E07 — Statistical release decisions

**Build:** predeclared primary endpoint/margin/sample plan, task-level pairing, nested-trial treatment, fixed external grader, hard invariant gate.

**Proof:** known null/planted effect experiments, calibrated false-alert/power results, degenerate-sample behavior, holdout results, and pass/fail/inconclusive explanations. Compare with a simple threshold gate under the same task distribution and cost budget.

**Limits:** no detected regression does not establish safety; bootstrap repetition is not additional data; distribution shift remains possible after qualification.

## E08 — FDE capability and initial adoption

**Build:** discovery brief, stakeholder workflow map, acceptance criteria, integration/onboarding guide, pilot scope, operating feedback loop.

**Proof:** authorized interview notes, observed debugging sessions, a requirement changed because of feedback, successful onboarding by someone else, and continued use if it actually occurs.

**Key measures:** diagnosis correctness/time, onboarding time, recurring use, and user-reported blockers. Counterbalance comparable tasks if studying debugging help; report participant count, task familiarity, and learning effects.

**Limits:** deployment proves deployment. Website visits prove visits. A small user session proves formative feedback. Sustained adoption needs separate evidence. Do not describe synthetic business records as a real customer deployment.

## E09 — Operations and delivery

**Build:** clean setup, hosted CI, preview/pilot deploy, traces/logs/metrics, bounded quotas, rollback and backup recovery.

**Proof:** source-bound green CI, complete browser path, fault/load reports, actual restore timestamps, and documented incident response. Trace data must not become an unredacted payload leak.

**SLO method:** define user-visible successful operation, eligible denominator, exclusions, window, and alert response. Measure API availability separately from model-quality success. Set initial targets after baseline measurement; do not publish unsupported “99.99% uptime.”

**Load method:** use a declared arrival-rate model, report dropped scheduling attempts and overload rejections, and include fault recovery. [k6 arrival-rate documentation](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/arrival-rate-vu-allocation/).

## E10 — Recruiter presentation and truthful claims

**Build:** public incident story, engineering decisions, evidence browser, documentation, actual screenshots, concise narrated demo, repository.

**Proof:** every claim resolves to manifest/method/artifact; every route/action is meaningful; an unfamiliar visitor explains the problem and finds technical proof without author assistance.

Future resume bullet template: “Built [implemented system] supporting [measured workload]; implemented [specific reliability contract]; measured [result with conditions] using [reproducible method].” Fill it only after evidence exists.

## Result registry

| ID | Capability | State | Artifact |
|---|---|---|---|
| E01 | SDE fundamentals | Partial: command/state boundaries and meaningful regression tests | build001 manifest/source map |
| E02 | Backend/database | Partial:13 PostgreSQL integration checks; durability/idempotency/tenant/rollback/tampering | build001/backend-tests.txt; clean-python-tests-final.txt |
| E03 | Frontend | Partial: manual interaction/mobile/outage + lint/types/build; no full accessibility/performance study | build001/browser-acceptance.json; website-*.txt; screenshots/ |
| E04 | Applied AI/context | Development probe failed0/4; product reference grader works; aligned/held-out model evaluation open | task-fit-local-qwen/report.json; provenance.json |
| E05 | Harness | Partial: bounded reference/context/event capture; no real model request ledger | build001/run-*.json |
| E06 | Loop | Planned beyond one bounded reference pass | No durable multi-step resume evidence |
| E07 | Statistics | Planned; no statistical release confidence claim | Legacy bootstrap is outside current execution path |
| E08 | FDE/user feedback | Planned | No outside-user study or adoption evidence |
| E09 | Delivery/operations | Partial: locked clean Python environment, local build and production gate; hosted CI/restore open | build001/clean-python-environment.txt; production-boundary.json |
| E10 | Recruiter presentation | Partial: populated site and technical docs; unfamiliar-visitor test open | Website and build001 screenshots |

Update a row only with explicit scope and artifact. A passing subset must not turn an entire capability green. Failed experiments remain in the registry with their explanation.

## Executed evidence — build001

Actual project artifacts: `/Users/gauravkumarnayak/Desktop/new-karos/evidence/build001/`. Portable copies live inside that repository; paths in the registry refer to its evidence directory. Current implementation report: `docs/BUILD_001.md`. Source fingerprints: `manifest.json`, generated after final source edits. This is a working-tree evidence bundle, not a signed attestation.

Recorded7 published runs/49events:4 idempotently seeded executions and3 browser-created forks. Product runner makes0LLM calls and0external effects. These are descriptive fixtures, not7 independent model trials. Test data lives in isolated random PostgreSQL schemas and does not add to product counts.

The separate Qwen report preserves0/4 strict development passes. Its policy differs from the product task suite; no before/after model improvement may be claimed. Post-run model/script fingerprints are labeled as such.

Npm runtime audit:0 findings. Full audit:5 related high entries in the development lint dependency chain ending at braces; no compatible upstream fix was applied. One Starlette/httpx TestClient deprecation remains. Hosted workflow is defined but unexecuted; browser checks are manual, not a reusable E2E suite.
