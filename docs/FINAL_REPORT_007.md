# Kairos build007 final report

Local software acceptance passed. The stronger repair target failed: five qualified cases instead of six, with baseline 0/5 and loop 0/5. Both results remain visible. This release delivers an inspectable, reproducible full-stack system; it does not establish effective general autonomous repair.

## What changed

- Ordered, checksummed SQL migrations replace startup DDL across six repositories. Fresh installation and validated build006 adoption preserve historical tables/records. Advisory locks, bounded statements, transactional receipts and separate runtime credentials make authority explicit.
- Versioned missing-value backfills bind their specifications and transformation semantics. Batches update missing values only; completed identities reject drift. Runtime role deadlines bound lock/statement waits separately from pool admission.
- Portable study commands use explicit external paths and read cached weights without copying them. Frozen configuration/source manifests refuse changed execution. V7 source handles, whole-line ranges, exact failure feedback, duplicate-candidate results and repeated-invalid stops address observed workflow failures.
- Review fixed legacy context exhaustion, reinspection overwriting elapsed time and discarded verifier-output prefixes. Complete bounded binary streams now survive durable artifacts/downloads; oversized output fails explicitly. Frozen source and result captures remain unchanged; delivery-source differences are recorded separately.
- The website explains the person's path, highlights source/patch differences, presents check output and keeps every comparison/failure downloadable. 122 records and 1243 original blobs preserve the earlier 76/965 byte-for-byte.

## Actual acceptance

| Run | Observed outcome |
| --- | --- |
| Full reviewer command against real PostgreSQL/Keycloak | 393 backend tests passed, six explicit opt-in skips; no failures |
| Current recorded browser journeys | 8 passed, zero skips |
| Isolated fault-fixture journeys | 11 passed, zero skips |
| Real OIDC browser journeys | 4 passed, zero skips |
| Clean relocated checkout, no initial runtime/credentials/DB/dependencies | Locked installation, builds, 19 browser journeys, 277 backend tests passed/122 explicit environment or opt-in skips |
| Focused post-review migration/protocol/packaging/provider tests | 86 passed, zero skips |
| Actual API/web images | Smoke checks passed; non-root images and explicit unavailable states |
| Actual disposable verifier | Isolation, oversized output, missing dependency and unavailable image checks passed |
| Saved original Django10914 patch | 110 tests, one upstream skip; rebuilt 007-reviewer image difference disclosed |
| Dependency audit/calibration | Frontend zero reported vulnerabilities; locked Python dependencies consistent; null calibration passes and planted regression fails as expected |

The six full-stack skips are four older provider-protocol opt-ins, one Docker opt-in and one local-model schema probe. Current actual-OIDC browser journeys and the separate real Docker probe pass; skipped tests are not relabeled as executed. Clean recorded-only and real full-stack counts are separate invocations. Hosted CI has not run.

## Operational evidence

An actual advisory lock returned 503 after 2.01 seconds and recovered the same request identity. With eight pool connections held and 40 contenders, 32 borrowers timed out and eight were rejected at the waiting ceiling; the pool recovered after release. Intentional DB restart returned 503, recovered in 1.41 seconds after start and preserved all 46 study investigation fingerprints. No inference was dispatched. These are local fault drills, not production SLOs.

A separately restored build006 database adopted explicit migrations while preserving historical rows; 82 investigations and 928 referenced objects were verified. Backups and original archive remain unchanged. Existing 42-minute capacity evidence is retained: 435,270 local control-plane requests, zero unexpected errors, ten-client acknowledgement p95 275.19 ms. It is neither current inference throughput nor proof of production scale.

## Repair study and free API probe

Five fresh Python cases qualified before inference: two Django and three pytest. Candidate order and at-most-five-per-repository qualification limits were preserved, including exclusions. Both frozen strategies attempted every qualified case once. Fresh results: seven invalid patches, three failed checks, zero verified repairs. The loop spent more inference without improving verified outcomes.

Development records remain separate: 36 attempts include 12 zero-dispatch environment failures and one verified already exposed Django repair. Two subsequent format experiments performed worse. The selected configuration was restored and frozen before evaluation. Historical 0/36 and0/10 studies are unchanged. Public cases may be contaminated and entry files were human-localized.

The user authorized a separate billing-disabled Gemini 3.8 Flash pilot using only public development issue/source excerpts. First HTTP 400 rejected an unsupported thinking setting. Corrected LOW request returned HTTP 503 UNAVAILABLE during high demand. No proposal was captured; dispatch uncertainty remains and no resend occurred. This is no repair success, and it does not rewrite the local study.

## Reviewer path and delivery

Run `python3 -m scripts.reviewer demo`, then open `/how-it-works`. Follow the issue, source, highlighted candidate, checks, paired cost and original downloads. See [all tested user actions](USER_JOURNEYS_007.md), [reviewer instructions](REVIEWER_007.md), [five-minute demo](DEMO_007.md), [claims](CLAIMS_007.md) and [architecture audit](ARCHITECTURE_REVIEW_007.md).

`evidence/build007/final-checks.json` is the software acceptance aggregate. The separate manifest/index/archive receipt binds the sanitized distribution. Verify using `python3 -m scripts.package_release007 --verify`. Hashes establish byte consistency, not signed or privileged-rewrite-resistant history. No credentials, browser sessions, dependencies or model weights are packaged. No push, PR or public deployment was performed.

The result is substantive early-career SDE/AI infrastructure evidence with a failed repair target. Personal code ownership requires explaining and changing the code. Production responsibility, outside adoption and staff-level organizational leadership require experience beyond this project.
