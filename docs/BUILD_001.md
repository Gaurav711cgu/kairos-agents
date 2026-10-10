# Build 001 — executed scope and evidence

Date:2026-10-11 Asia/Kolkata. Status: local implementation checked; larger flagship still in progress.

## What works

The public site opens a real controlled failure, shows the omitted prior-compensation exception, and links to a seven-event persisted execution. The inspector supports filtering, keyboard selection, URL event state, source context, independent checks and lineage. Its local-only action executes a fresh preserve-context scenario; production disables that action.

The new API stores command identity, run document and ordered events in PostgreSQL. Successful writes return after transaction commit, with synchronous commit enforced and fsync required. Same tenant/key/request retries return the same run; conflicting payloads return409. Tenant identity comes from configured developer credentials, not a caller-supplied tenant header. Public reads expose only explicitly published controlled data.

This is a deterministic reference runner. It deliberately drops an exception under compact context, proposes480cents instead of0, and is rejected by an independent grader using complete scenario facts. Preserve retains the exception and passes. Missing evidence yields explicit abstention. No LLM or payment tools run in this product path.

## Executed checks

| Check | Result | Saved artifact |
|---|---|---|
| New backend unit + actual PostgreSQL integration |27passed:14unit,13integration |[backend-tests.txt](../evidence/build001/backend-tests.txt) |
| Fresh Python3.12 environment, exact API lock |27passed |[clean-python-tests-final.txt](../evidence/build001/clean-python-tests-final.txt) |
| ESLint |exit0 |[website-lint.txt](../evidence/build001/website-lint.txt) |
| TypeScript |exit0 |[website-types.txt](../evidence/build001/website-types.txt) |
| Production build |exit0 on Node24.15.0; initial25.9.0 also passed |[website-build-node24.txt](../evidence/build001/website-build-node24.txt) |
| Manual browser journeys |context toggle, URL refresh, keyboard/filter, three forks, mobile/outage/restart, production-disabled control |[browser-acceptance.json](../evidence/build001/browser-acceptance.json) |
| Local proxy boundary requests |foreign/missing origin403; unsupported policy400 |[proxy-boundaries.json](../evidence/build001/proxy-boundaries.json) |
| Production proxy with enabled local flag + same origin |403 |[production-boundary.json](../evidence/build001/production-boundary.json) |
| Runtime npm audit |0findings |[npm-audit-runtime.json](../evidence/build001/npm-audit-runtime.json) |
| Full npm audit |5related high development-tool entries remain |[npm-audit-all.json](../evidence/build001/npm-audit-all.json) |

The PostgreSQL tests use isolated random schemas. They cover committed visibility on another connection, repository restart, idempotent/conflicting/concurrent commands, credential-bound tenant denial, public/private publication, injected partial-write rollback, tampered events, and valid foreign-chain substitution. Tests do not add records to the public dataset. A remaining Starlette/httpx TestClient deprecation is recorded in raw output.

The saved database snapshot contains7published runs/49events:4seed records plus3browser-created forks;6checks pass,1intentional scenario fails,1run abstains,4runs have parents. These are descriptive reference runs, not independent model trials or a performance estimate. See [database-evidence.json](../evidence/build001/database-evidence.json) and individual `run-*.json` artifacts.

Browser checks are manual observations through the app browser, not a checked-in reusable Playwright suite. Homepage and incident were checked at390×844 without document overflow; desktop was checked at1280pixels. Screenshots are in [evidence/build001/screenshots](../evidence/build001/screenshots). No complete accessibility or performance qualification is claimed.

## Model experiment — preserve the failures

[Raw Qwen probe](../evidence/task-fit-local-qwen/report.json):0/4strict development passes, one greedy trial per case using locally cached Qwen2.5-0.5B-Instruct weights. Standard late-order math returned6000 instead of2000. Exception and within-window outputs violated policy; three responses used Markdown fences and failed strict JSON parsing. The unknown-delay response expresses appropriate abstention but fails the transport contract. Treat semantic and formatting failures separately.

This probe uses a non-refundable exception and a >30minute threshold. The product scenario uses prior compensation and >=30minutes. Its results must not be compared directly to the reference runner's scores. Align and version these tasks before a model/harness evaluation. No qualification, confidence interval or release recommendation follows from four development cases. [Provenance](../evidence/task-fit-local-qwen/provenance.json) contains explicitly post-run script/model fingerprints.

## Failures caught while building

- API/client schema mismatch for boolean exceptions and nullable evidence: repaired before browser acceptance.
- Next normalized local URL hostname differently from browser origin: proxy now compares validated loopback Origin with the actual Host header, retaining development/flag/credential restrictions.
- Client command identity could carry across incident navigation: scoped to parent and cleared after confirmation; chained browser forks now succeed with distinct identities.
- Storage failures could leave the action busy: dispatch is inside the guarded path and does not proceed if persistent command identity cannot be saved.
- A valid foreign event chain could pass consistency checks: events and stored sequence now bind to the actual run row; regression test added.
- Durable capture depended on PostgreSQL defaults: writes explicitly enforce synchronous commit and reject fsync disabled.
- Outage retry linked to a different route: now refreshes the current view.

The full npm audit reports one underlying braces stack-exhaustion advisory through the dev-only ESLint/fast-glob/micromatch chain, represented by five related entries. The suggested automatic fix downgrades Next lint config across major versions. No compatible fix was applied; raw findings remain open. Runtime audit is clear. Do not pass untrusted glob patterns to this development toolchain.

## Reproduce and resume

Use [README](../README.md) for commands. `python3 scripts/configure_local.py` preserves existing local credential files; `python3 scripts/run_local.py seed` reuses seeded command identities. Current session uses manually started `kairos-postgres-build001` on55432 with persistent volume `kairos_pg_build001`; do not launch Compose over that occupied port. Compose is configured for a fresh checkout with a pinned image, but complete clean-checkout deployment remains unverified.

Source digest: `63001f448bcbb7ae28435069f05b2f34d1fa7f89d0613dbaf444506e66970e42`. [manifest.json](../evidence/build001/manifest.json) maps implementation paths and raw artifacts to hashes. These hashes provide local correspondence, not signed execution attestation. The implementation is currently an uncommitted working tree over the recorded baseline; no new commit, remote repository or hosted CI execution was created.

Read [BRAIN](../BRAIN.md) first next turn; then only the relevant decision/milestone/source. P00/P01 remain partial. The next work is aligned model task-fit evidence, then durable model intent/result jobs before remote execution. Managed identity, worker leases, replay/checkpoint resume, effect approvals/reconciliation, object storage, held-out statistical gates, restore/load qualification, deployment and outside-user feedback remain open.
