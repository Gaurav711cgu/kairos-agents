# Kairos working context

Updated 2026-10-14. Main: Desktop/new-karos. Preserved seals: build007 and showcase008. Current follow-up: CI portability009. Chat uses concise Caveman; saved prose uses normal English.

## Pointers

README.md introduces the project and earned benchmarks. docs/showcase/FINAL_REPORT.md maps current acceptance; ARCHITECTURE.md and OPERATIONS.md describe implementation. VISITOR_WORKFLOW.md records DOM behavior; DEMO.md is the interview walkthrough; LINKEDIN.md is the publication-scoped draft. Decisions D86–D91 explain the final changes.

## Current evidence

Full-stack acceptance: 434 collected, 428 passed, six explicit skips, zero failures. Frontend units, lint, types and both builds passed. Browser journeys: eight recorded, eleven fault fixtures, four actual OIDC and one separate real-model journey. Total 24 across those scopes.

The real browser submitted Django11066 development through OIDC and durable API. Two model calls produced one candidate; one check passed four tests. Worker elapsed time: 35.100004 seconds. Context, downloads, replay without execution, mobile layout and logout passed. Source issue supplies a repair hint; source entry files were human-localized. Exclude this exposed demonstration from locked validation.

## Preservation and limits

Original build007 archive/index/manifest/receipt and 122 public records/1,243 blobs remain unchanged. API, worker protocol, model/case profiles and frozen evidence are preserved. Declared008 delta changes presentation, documentation, reviewer setup/cleanup, private-state validation and tests. scripts.verify_showcase008 binds the active delta; --publication verifies the new archive. Original package_release007 verification applies to its unchanged extracted snapshot.

Fresh v7 remains 0/10; older 0/10 and 0/36 remain visible. Historical local capacity: 435,270 requests over approximately 42 minutes, zero unexpected errors, soak ACK p95 275.19 ms/read p95 16.79 ms. Original Django10914 patch reproduced 110 tests/one skip. Operational and migration/restore receipts remain.

## Operation

Only the recorded website on 3310 stays on at handoff. Docker, model and worker are stopped; volumes/images remain. Fullstack defaults inference off. --with-inference reuses pinned existing cache and has a 900-second deadline. .runtime/live-showcase008 preserves the real demonstration; .runtime/showcase008-acceptance is separate. Never print credentials, export sessions, rerun locked studies or resend uncertain API calls. The free API400/503 pilot has no proposal and no retry.

## Handoff

GitHub PR1 exposed two test defects after the original release commit 0759751: the legacy ingest fixture hardcoded the developer binary, and pool reuse assumed consecutive checkouts share a PID. CI009 builds Go from checkout sources into a temporary directory, installs the go.mod toolchain in both jobs, warms every pool slot and verifies reuse plus rollback of an actual row. Failure diagnostics expose bounded redacted logs. The first corrected native PostgreSQL18 suite passed 428 with six skips; new diagnostics/provenance tests are checked separately. Hosted outcomes remain in GitHub run records, not the historical acceptance receipt. scripts.verify_ci009 verifies the active correction and original008 archive; the older008 command applies to its preserved snapshot. See docs/showcase/CI_009.md.

Professional README, website, acceptance and live workflow are complete. The user authorized commit and push of release 0759751 to Gaurav711cgu/feat/finalize-kairos-reviewer-release in kairos-agents; PR1 exists. CI009 follows up the first hosted failures without changing main. The repository is private; public hosting and visibility changes were not authorized. Localhost is not a public URL. Interview practice remains separate from software acceptance.
