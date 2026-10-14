# Build004 advancement ledger

Status: implementation and acceptance in progress. Build003 results remain historical and unchanged. This document is not a completion certificate.

## Release boundaries

The SDE release is independent of repair scores. The local control plane, browser interactions and recovery boundaries must pass before being described as accepted. The study has a separate qualification, development, freeze and evaluation sequence. Lenovo availability is optional; no remote hardware result is inferred from a setup script.

## Implemented, awaiting full acceptance

- Scoped progress summaries; private evidence and patch downloads with existing capture integrity checks.
- Cursor pages (25 default, 100 maximum), stable `(created_at, id)` ordering and scoped cursors. Additive listing indexes.
- Global capacity of 24 queued/running investigations, six per tenant and one executing worker. Durable retries resolve before quota rejection.
- Workbench transport, state hook and rendering modules. Aborted obsolete reads also carry a generation check, so a transport that ignores abort cannot overwrite newer selection.
- Create/fork identities persist in session storage per workspace before dispatch. Uncertain submissions retain the same identity across reload. Storage denial prevents dispatch.
- Progress polling while visible at two seconds, 30-second error backoff, terminal/navigation cancellation. Private readable inspector shares the public evidence components.
- V4 snapshot edits reference original source digest, captured excerpt identity and inclusive line range. Invalid edits are captured without consuming an applied-patch slot. Six calls, two applied candidates, two checks, ten minutes remain server-owned.
- V4 checks each accepted candidate before the next model call. Original reads remain original after edits. Rendered chat-template tokens are counted; context omissions remove complete regions, never a prefix of serialized JSON.
- Independent drafts capture six fresh-context proposals and select the first two structurally valid proposals before any check. Every draft remains inspectable. The selected passing patch determines downloads and the visible verifier result.

## Evidence recorded so far

`evidence/build004/build003-source.tar.gz` preserves all 170 source files named in the previous manifest, verified before mutation. The adjacent JSON records its hash.

`control-plane-before.txt` records four reproduced failures. `browser-before.txt` records the late-detail overwrite and command-key change after reload. Subsequent receipts must be read for their actual pass/fail state.

The first unpooled capacity attempt produced database connection failures after its first stage and was interrupted. Its requests and logs are retained. Connection churn is a working explanation, not a proven root cause. One bounded optimization adds an eight-connection pool with a bounded wait queue, transaction rollback and connection health checks. The repeated full profile is separate under `capacity-pooled/`; completion and target attainment must come from its summary, not expectations.

## Study protocol

Pinned official SWE-bench Verified data: revision and SHA-256 in `dataset.json`. New cases are selected in instance-ID order independently of model performance, with exclusions recorded. Historical attempts and preflights are excluded. A fixed hash ordering seeded with 741903 chooses two development cases per repository and four evaluation cases when all six qualify. Public historical contamination remains possible. Qualification uses disposable 1GB/120-second verification and reviewed, pinned build-time dependencies. Verification commands check a registered regression and selected existing tests, not entire upstream suites.

No evaluation runs are authorized by an incomplete qualification manifest. Development has at most three recorded revisions after the model-profile pilot. Evaluation must freeze configuration and run once. Missing the target does not restart engineering work.

## Remaining acceptance

Full backend/frontend/image checks; real OIDC browser journey; delayed/error/visibility polling tests; restoration and crash drills; deterministic case qualification; v4 live runtime/schema/context pilot; model-profile selection; a frozen three-strategy study if qualification completes; local screenshots; measured capacity page; interview walkthrough. Personal code ownership and mock defense require the candidate's own explanations.

## Explicit limits

No production-scale, broad repair-competence or loop-superiority claim. Shared verification containers do not establish adversarial test-forgery resistance. Fixture traffic measures local HTTP/database control-plane capacity, not model throughput, OIDC provider throughput, distributed scale or customer adoption.

## October 12 recovery and bounded development

Desktop access returned after a Mac restart. Existing PostgreSQL and Keycloak containers were restarted without resetting data. Development revision 1 completed all six coder baseline cases before that restart; all were rejected for missing final replacement newlines. Revision 2 renders whole-line separators mechanically, while preserving the original model action and source text. This is an adapter correction, not a semantic repair. Both model profiles are compared under revision 2. Twelve evaluation cases remain untouched until the selected configuration freezes.

All 18 new cases qualified. The complete pooled capacity repeat passed all four three-minute stages and failed the ten-client soak. See `CAPACITY_004.md` and `capacity-analysis.json`; no sustained-capacity acceptance claim.

## October 12 second reboot and resource policy

A second Mac restart interrupted frozen evaluation. Docker was reopened once for database inspection. The sole active attempt, `b2117762-cc54-43ae-af56-401ded068bc6`, had six captured model responses and no pending dispatch. Its original deadline and lease had expired. Normal repository claim recovery marked it timed out without execution or a replacement attempt. The terminal record and attempt ledger were saved; `infrastructure/evaluation-reboot-recovery.json` records the timestamp and incomplete duration limitation.

At the user’s request, Docker runs only when database or disposable verification needs it. Inference, builds and capacity runs should not overlap; unrelated host work remains outside Kairos control. These resource decisions do not alter frozen model settings or erase interrupted outcomes. Seven client/boundary tests passed after access was restored.

All ten isolated browser checks passed after the reboot, including public evidence, patch download, keyboard comparison/context inspection, 390px layout, missing records, stale responses and uncertain command retries. The reporting adapter marks the reboot-interrupted attempt’s elapsed duration incomplete and excludes it from duration sums. Frozen model behavior and configuration are unchanged.

## Docker exit during frozen evaluation

Docker exited again during the independent-draft attempt for Requests 1142. Twenty-six outcomes had already been exported. Normal database-clock expiry preserved record `6819f605-7d70-4ca1-9bd9-ca47a6125c56` as unknown dispatch: three model responses captured and one pending intent. No dispatch was repeated and no replacement attempt was created. See `infrastructure/evaluation-docker-exit-recovery.json`. Both interrupted attempts have incomplete duration metadata; sums exclude those durations. The website distinguishes captured tokens and incomplete timing.

`scripts/resume004.py` verifies the frozen lock and refuses any active queue before continuing existing identities. It opens Docker only if unavailable and stops owned inference and unused Docker afterward. Other containers are preserved if present. This operational wrapper does not change frozen worker behavior or retry unknown inference.

## Completed evaluation and final inspection

All 36 frozen evaluation attempts completed or reached explicit terminal interruption outcomes. None earned a verified repair. The complete ledger contains 78 development/evaluation attempts. No evaluation tuning or replacement attempts occurred. Both real SIGKILL drills passed without recovery redispatch, and both opt-in model/schema and Docker isolation checks passed. Final image smoke passed; a consistent restore verified 109 investigations and 1,145 distinct objects. The original Django repair reproduced with 110 tests and one upstream skip. A runner invocation first omitted the module path; that failure is retained separately.

All eleven isolated browser journeys passed. The first live production homepage inspection returned unavailable; individual records were valid. Comparison reads were bounded and indexed to remove unrelated-record fan-out. Three real homepage loads, downloads, three-strategy comparison, keyboard context, 390px layouts and unavailable-record checks subsequently passed. Public screenshots are saved. The transient first-load trigger remains unproven.

The user explicitly selected another full quiet 42-minute capacity repeat. Website, browser checks and inference are stopped during it; the original failed soak remains preserved. Results must come from `capacity-quiet/summary.json`, not this progress note.

## Complete capacity follow-up, October12

The first quieter repeat stopped with two completed stages and partial raw data; benchmark and Docker were absent on resume, with no completion receipt. Cause unproven. The separately named `capacity-quiet-2` completed the full42-minute protocol with435,270 requests, zero errors and zero quota rejections. Soak 272,855 requests: acknowledgement p95 275.19ms, read p95 16.79ms. All five targets passed. Original failures remain preserved. Kairos inference/web/build/browser activity was stopped; a separate project's6.5-second Docker build overlapped the first stage and is disclosed. Local control-plane capacity is measured; inference, OIDC throughput and production scale remain separate.

## Final handoff

Frontend tests/lint/types/build and eleven isolated browser journeys passed after capacity integration. Real production public inspection passed comparison, saved downloads, keyboard controls, errors and 390px layouts. Final non-root API/web smoke passed eighteen checks. Exact historical pytest executable image recovered and baseline/reference independently rechecked without changing evaluation results; optional provenance attachment unavailable and disclosed. Final aggregate receipts corrected. Runtime/free-space guards passed; owned website/API/inference and unused Docker stopped. See `FINAL_REPORT_004.md`, `final-checks.json` and the new local evidence inventory. Candidate ownership defense and Lenovo access remain separate.

## Capacity timing correction

An earlier note incorrectly placed a separate-project Docker build during the first repeat stage. Exact timestamps show it ended about 59 seconds before benchmark startup. `capacity-quiet-2-host-context.json` corrects that interpretation; earlier receipt/note remains preserved. Other shared-host activity was not exhaustively measured. Request counts, failures, latency and target decisions are unchanged. Current website/report use the corrected chronology.
