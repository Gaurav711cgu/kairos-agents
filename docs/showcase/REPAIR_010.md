# Repair workflow010: evidence and next measurement

## Delivered behavior

The optional local workflow accepts a reviewed unresolved Python task without a reference repair. It validates pinned source, an approved source prefix, a reviewed verifier image/command and two independent baseline receipts: the regression fails, while relevant existing tests pass. This removes the old benchmark registry's requirement to possess a known solution before investigating a defect.

The operator supplies reviewed entry files and the execution environment. This is controlled repository onboarding, not arbitrary-URL execution. Existing website/API defaults and historical protocols remain unchanged. The optional command uses `GPT-6.1-Sol` through existing local ChatGPT authentication. It does not enable API billing, discover credentials or fall back to another provider. The CLI version/binary hash and requested model are recorded; a provider-reported resolved model revision remains unavailable.

The experimental worker retains exact rejected edits in subsequent context. It keeps source handles, digest/range validation, syntax checks, immediate independent verification and six-dispatch/two-candidate/two-check/600-second limits. It records whole-region omissions. The 64 KiB prompt guard is distinct from the historical local model's 4,096-context/1,024-output profile. Internal CLI retries remain CLI-controlled, so CLI invocation counts are not underlying HTTP/model request counts.

## What the person does and receives

1. A reviewer opens the website and follows **Read the repair workflow follow-up**. They see two readable before/after patches, actual check output and the complete attempt ledger. Patch/check/original-response downloads contain captured evidence. A dedicated read-only route serves compiled captured bytes after validating their size, canonical encoding and SHA-256. Unknown paths return 404 and corrupt entries return 409; raw static files are not used as a fallback.
2. An operator prepares a new local Python task with a pinned source snapshot and trusted test recipe. The operator captures a completed failing regression and passing existing tests against that same source/image. The recipe and receipts stay outside source tools.
3. `validate-task` verifies registration. A changed snapshot, verifier, receipt, unsafe path or unsupported task is refused before inference.
4. `run` creates a separate private runtime and PostgreSQL instance. It uses the signed-in ChatGPT CLI, accepts bounded source edits and starts the existing Docker engine only if an accepted candidate needs checks. It stops owned services afterward and preserves the original source. A nonblocking per-checkout POSIX lock permits one optional investigation at a time; a competing command is refused before database or model startup.
5. `report` verifies saved evidence hashes and reports the actual outcome. A verified repair includes a proposed patch and completed checks. An existing or interrupted runtime is inspected rather than automatically dispatched again.

The optional unresolved-task execution path is a local CLI. It is not a new browser submission mode. The authenticated browser workbench retains its released pinned local-model workflow.

## Commands

Use Python 3.12 and the locked reviewer dependencies. The command discovers the existing Codex executable; `--codex` can select its explicit local path. PostgreSQL tools and the already prepared Docker verification image are required for execution. `doctor` starts no inference, Docker or database.

```bash
python3 -m scripts.study010 doctor
python3 -m scripts.study010 validate-task --manifest /path/to/reviewed/registry.json --case-root /path/to/prepared/runtime --task-id reviewed-defect
python3 -m scripts.study010 run --manifest /path/to/reviewed/registry.json --case-root /path/to/prepared/runtime --task-id reviewed-defect --runtime .runtime/study010/reviewed-defect
python3 -m scripts.study010 report --runtime .runtime/study010/reviewed-defect
python3 -m scripts.verify_repair010
```

A prepared case lives under `<case-root>/cases/<task-id>/`. It contains `source/`, `test.patch`, `verify.py` and `baseline/regression.json` plus `baseline/existing.json`. The strict manifest version is `reviewed-task-registry-v1`; each case uses `task_kind=reviewed-unresolved-python-v1`, `split=unresolved`, the fixed command `python /verification/verify.py`, explicit entry files/lines and the source/verifier/environment/receipt hashes. `ReviewedTask` and `BaselineReceipt` in `scripts/repair010/unresolved_registry010.py` are the authoritative schemas. The integration test supplies a complete software-fixture example. Do not label that fixture as model performance or a real unresolved-repair demonstration.

## Actual outcomes

Two completed Codex-default development proposals were rejected by an overly strict response adapter because they included a bounded explanatory summary. The correction removes that metadata from tool arguments while preserving exact source handles, ranges and replacement bytes. Independent post-hoc checks verified both original proposals:

| Captured candidate | Check result | Scope |
| --- | --- | --- |
| pytest-dev__pytest-6197 | 22 tests, completed, exit 0; 2.617 seconds | Exact captured one-line deletion, independently checked after adapter correction. |
| django__django-11066 | Four tests, completed, exit 0; 1.967 seconds | Exact captured source replacement; public issue includes a repair hint. |

Both original source snapshots remained unchanged. These are **post-hoc candidate verifications**, not replay, successful original investigations or fresh validation. They added zero model calls. Original version 2 used three pytest CLI dispatches and one Django dispatch. Those earlier captures used the CLI default model; its resolved identifier was not recorded. Future unresolved-task runs explicitly request `gpt-6.1-sol`; do not retroactively assign that identity to earlier outputs.

The full ledger retains five development attempts: one local feedback context failure; one CLI warning-classification uncertainty; two response-adapter rejections; and one later usage-limit uncertainty. Two uncertain CLI dispatches were not resent. The last end-to-end attempt stopped when the account reported its usage limit. No new API billing was enabled. See `evidence/repair010/attempts.json`, `posthoc-summary.json` and per-candidate original responses, contexts, patches and raw check output.

The frozen build007 study, completed 13 October 2026, remains baseline 0/5 and loop 0/5. It is the dated result for those local weights/configuration, not today's overall product score. Reference-patch file headers seeded benchmark entry-file selection. The replacement text stayed outside model tools, but that assistance must be disclosed. Earlier 0/10 and 0/36 studies remain preserved.

## Owned gaps and closure plan

| Gap | Cause and evidence | Delivered mitigation | Resource and closure criterion |
| --- | --- | --- | --- |
| Weak historical repair effectiveness | Captured local-model proposals contain numbered-code prefixes, indentation/range errors and incorrect behavior. | Exact rejected proposals survive context; a stronger authenticated provider is available; two captured candidates passed checks. | Existing subscription capacity, not a new GPU. Complete one new reviewed unresolved task, then freeze a fresh cohort before inference. Publish all outcomes; do not retune on that cohort. |
| New live provider score not yet earned | The corrected end-to-end attempt hit the account usage limit; no final response was captured for that dispatch. | Preserve unknown; no automatic resend or paid fallback. Software integration is independently exercised with real PostgreSQL and Docker. | After normal quota is available, use a new registered task/runtime with the frozen explicit model profile. Require a captured response, completed independent checks and an unchanged original source. |
| New repositories need preparation | Dependencies, allowed paths and regression tests differ across repositories. | Reference-free strict registration accepts reviewed source and independently captured baselines. | Operator review and a prepared image/test recipe. Close a repository's support claim with its actual baseline and end-to-end investigation receipts. No arbitrary-repository claim. |
| Candidate checks have finite coverage | Passing selected tests cannot establish all intended behavior; candidate Python shares the verifier environment. | Protected tests/recipe, complete-execution markers, bounded output, source isolation and failure retention. | Add independently authored behavior tests for the supported task scope. Strong adversarial isolation would require a separately designed verifier boundary and evidence. |
| Hosted model revision is not fully observable | CLI exposes requested model and usage, not a resolved weight/revision identifier in these captures. | Pin CLI bytes, requested alias, source, verifier and exact patch/output captures. | Record a provider-reported revision when supported. Exact saved patch/check reproduction is available now; bit-identical regenerated model output is not claimed. |
| Production/adoption claims need external history | Current capacity is local and the release has no public hosting/customer usage. | Preserve measured local receipts and isolated operational drills. | A separately authorized deployment and observed real-user operating period. This is outside the zero-hosting portfolio release, not substituted by a load-test number. |

A missed result is an engineering input with an owner and a next test. Resource limits do not excuse adapter defects: both warning classification and metadata handling were our implementation mistakes and now have regressions. We preserve those failures to make the correction auditable, not to suggest they are permanent limits.

The optional runner is locally verified on macOS ARM64 with native PostgreSQL18 and Docker Desktop. CI also declares its native lifecycle dependencies explicitly; hosted outcomes are separate from local results. It uses POSIX process groups and `flock`; portable paths do not establish Windows support.

## Acceptance and provenance

`evidence/repair010/acceptance.json` records actual current invocations, skips and cleanup. Three new real PostgreSQL/Docker software journeys cover independent baselines, durable submission/retry, exact fixture-patch checks, downloads, source isolation, replay without execution and refusal after source mutation. The provider in these three journeys is explicitly a prewritten mechanical fixture, not model inference. Unit tests separately cover source authority, malicious paths/links, corrupt receipts, exact rejection recovery, metadata normalization, native-tool refusal, usage/timeout failures, owned process cleanup, requested model and evidence verification.

The static website changes reuse existing readable evidence components and muted styles. Desktop and 390 px journeys inspect patches, check output, keyboard controls, original outcomes and exact downloads. Existing API/authentication/provider defaults are unchanged; previous hosted CI009 remains separate evidence for the released OIDC journeys. The new hosted workflow includes the new backend tests and a pinned Python base image for its reference-free software fixture.

`verify_repair010` checks an additive source overlay over CI009 and verifies the original008 archive members and historical seals. It does not rewrite earlier manifests or claim cryptographic immutability. No credentials, authentication state, installed packages, model weights or private process/database files are included in the public evidence.
