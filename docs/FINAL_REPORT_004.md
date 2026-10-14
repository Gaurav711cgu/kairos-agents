# Kairos build004 evidence report

Updated 2026-10-12. Local engineering release and evidence handoff completed. Claims below distinguish correctness checks, measured targets and model results.

## Delivered engineering

The private workbench separates transport, command state and rendering. Selection changes cancel obsolete reads and reject late results. Pending create/fork commands survive reloads with workspace-scoped identities; uncertain requests retry the same command. Active progress polling stops on navigation/terminal state and backs off after errors. Public and private evidence views show context, patch changes and check output without requiring raw JSON inspection.

The API adds authenticated progress and integrity-checked downloads, stable cursor pagination, listing indexes and an explicit global ceiling of 24 queued/running investigations. One investigation executes globally; each tenant retains six active slots. Existing durable receipts, database-clock leases, fencing, tenant authority and unknown-dispatch semantics remain intact.

V4 edits bind original source digests, excerpts and line ranges. Accepted first patches receive immediate checks before further inference. Required issue, budget and verification context remain intact; overflow fails explicitly rather than sending truncated JSON. The independent-drafts strategy permits up to six fresh-context proposals and selects the first two structurally valid candidates for checks. Earlier configurations and evidence remain available.

## Executed correctness checks

| Check | Observed result | Receipt |
|---|---|---|
| Full backend | 213 passed, two opt-in skips, two dependency warnings | `evidence/build004/backend-final.txt` |
| Real local model schema and Docker isolation | Both opt-in checks passed separately | `evidence/build004/real-provider-docker.txt` |
| Client and request boundary | Seven passed | `frontend-client-final.txt`, `frontend-boundary-final.txt` |
| Frontend lint, types and production build | Passed after final capacity integration | `frontend-final-receipt.json` |
| Actual production public inspection | Passed desktop/390px, comparison, capacity history, keyboard, downloads and errors | `browser-live004.json` |
| Non-root API/web image smoke | All eighteen checks passed | `docker-smoke.json` |
| Isolated browser journeys | Eleven passed after final capacity integration | `browser-final-public.txt` |
| Real OIDC, roles and tenant journeys | Three passed | `browser-oidc-final.txt` |
| Real SIGKILL recovery | Two drills passed; zero recovery model dispatches | `crash-recovery.json` |
| Fresh database/artifact restore | 109 investigations, 1,145 distinct objects, 1,546 references verified | `restore-final.json` |
| Recorded model repair reproduction | 110 tests, one skip; original model patch reproduced | `repair-reproduction-final.json` |
| Dependency audits | No known findings in current npm/API dependency audits | `npm-audit-final.json`, `python-audit-final.json` |

These checks exercise specific invariants and failure scenarios. They do not establish exactly-once external inference, an immutable administrative history, adversarial test-forgery resistance or production-scale operation. The restore used fresh local targets and consistent source snapshot locks; it does not establish offsite recovery or a production recovery-time objective.

## Frozen repair study

All eighteen accepted cases reproduced a baseline behavioral failure and the maintainer repair before model execution. Six development cases preceded twelve locked evaluation cases across Django, pytest and Requests. Both local model-profile pilots earned zero verified repairs. Qwen3 was selected by the elapsed-time tie-break after repair and invalid-response counts tied. This is not evidence of better repair quality.

The final comparison contains 36 attempts: twelve cases with single call, bounded loop and independent drafts. **Zero verified repairs.** The declared quality target of six cases across two repositories was missed. All 78 development/evaluation attempts remain in the ledger.

| Strategy | Verified/attempted | Dispatch intents | Captured tokens | Recorded outcomes |
|---|---:|---:|---:|---|
| Single call | 0/12 | 11 | 25,714 | Eight invalid patches, two failed checks, two environment failures |
| Bounded loop | 0/12 | 66 | 70,544 | Eleven no-patch outcomes, one environment failure |
| Independent drafts | 0/12 | 64 | 149,067 | Five invalid patches, three failed checks, two environment failures, one timeout, one unknown dispatch |

Three Django 11087 attempts exceeded required context in the 4096-token profile before dispatch. Two pytest 10051 attempts could not access their exact pinned verifier image. These remain infrastructure outcomes; they are not evidence of model repair quality. One rebooted attempt timed out after six captured responses. One interrupted attempt retained three captured responses and an uncertain fourth intent. Neither was redispatched. Their duration is incomplete and excluded from elapsed totals; unknown token consumption is not reported as zero.

The exact historical pytest executable image was recovered from digest-checked local BuildKit bytes and tagged separately. Its optional provenance attachment was missing, so no signed-provenance claim is made. All four registered image digests are now available. A fresh baseline/reference check in the recovered image passed; no frozen agent result changed. Local inference startup now refuses missing pinned verifier images before model dispatch. See `verifier-image-recovery.json` and `verifier-image-reference-smoke.json`.

Paired descriptive differences are zero because all observed strategies failed. Degenerate bootstrap intervals do not prove equivalence or safe future behavior. Cases were public, potentially seen in training and manually localized to source regions. No leaderboard, broad-competence or loop-superiority claim is supported. Evaluation configurations were not retuned after seeing results.

## Preserved earned demonstration

Build003 repaired one distinct Django file-permissions case with both single call and loop, earning two verified attempts. Its one-line model patch reproduced in a fresh disposable copy with 110 tests and one skip. The website labels this original study separately from build004's 0/36 result. It is a reproducible successful case, not a representative repair rate.

From the prepared repository, with Docker available:

```bash
PYTHONPATH=. .venv/bin/python scripts/reproduce_investigation.py --record evidence/build003/django__django-10914-baseline-v3.json --output /tmp/kairos-repair.json
```

This command uses saved source and the captured model patch. It requires neither an API key nor live inference. Source checkout isolation, registered commands and integrity checks remain in force.

## Capacity

The complete follow-up processed 435,270 requests across four 180-second stages and a 1,800-second ten-client soak. Zero unexpected errors and zero quota rejections occurred; all targets passed. The soak completed 272,855 requests with acknowledgement p95 275.19 ms and read p95 16.79 ms. Raw rows match aggregate request counts. The original failed mixed-workload soak and interrupted quieter attempt remain preserved.

Kairos workloads were quiescent. A separate project's 6.5-second Docker build finished about 59 seconds before measurement began. An earlier overlap interpretation was incorrect and is preserved with its correction. Other shared-host activity was not exhaustively measured. This is a measured local control-plane result, not an isolated-hardware saturation limit, inference/OIDC throughput result or production-scale claim. The original restart cause remains unproven. See `CAPACITY_004.md` and `capacity-summary-final.json`.

## Website and failure ledger

The release leads with the earned original repair, exposes the new frozen failure cohort, and links source, patch, context, checks and evidence downloads. Sentence-case writing, muted colors and shared controls are retained. Public inspection uses captured evidence and requires neither login nor inference.

Initial production inspection displayed unavailable records despite successful individual API responses. Its transient cause was not conclusively isolated. Code review found separate request amplification: comparisons fetched all cohort records before filtering by case, while dense links prefetched details. Comparison reads now select case IDs first, retain digest/profile/configuration checks and run at most four concurrently. Dense record links disable eager prefetch. The regression observes three distinct record reads for a three-strategy case, and subsequent production inspection passed.

Other preserved failures include the original connection-churn benchmark, original mixed-workload failed soak, interrupted quiet repeat, interrupted evaluation dispatches, an incorrect reproduction-runner import invocation and the release-browser script's first lint failure. Corrections have separate receipts. No failure was deleted or converted into a successful model outcome.

## Hardware, storage and handoff boundaries

No API spend, hardware purchase or public hosting occurred. Both model profiles ran on the Mac. Lenovo setup remains documented but untested without access to that machine. Investigation runtime measured 4,847,943,680 bytes with 34,560,233,472 bytes free. Runtime/reserve guards passed. Shared Docker layers/cache and installed footprints are not exact per-release physical additions. Website, API, inference and unused Docker were stopped after checks. Interrupted fixture schemas were removed only after proving their exact fixture scope; raw evidence and application data remain preserved.

Build003's archived 170 source files and 72 evidence files match preserved fingerprints; historical tagged images are checked separately. Hashes establish local consistency, not signed provenance or immutability against a privileged rewrite.

The five-minute demonstration and code-path questions are in `INTERVIEW_DEFENSE.md`. Candidate code ownership and an unfamiliar debugging exercise remain unassessed until the candidate performs them. External adoption, hosted CI, production deployment and model research remain separate milestones. The engineering release can be demonstrated independently of the missed repair target.

Final acceptance index: `evidence/build004/final-checks.json`. Local source/evidence fingerprints: `evidence/build004/manifest.json`. Screenshots include `home-viewport.png`, `repair-viewport.png`, `capacity-viewport.png` and `capacity-mobile-viewport.png`.
