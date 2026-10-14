# Kairos: claims and their evidence

Updated 2026-10-13. Use the bounded claims below on a résumé, in a repository description and during interviews. The delivery acceptance receipt is separate from the frozen engineering and model-study evidence.

## Three résumé bullets

- Built a Next.js/FastAPI investigation workbench with PostgreSQL durable command receipts, OIDC role and tenant authorization, fenced workers, and disposable Docker verification of proposed source patches.
- Measured 435,270 local control-plane requests across a 42-minute load protocol with zero unexpected errors; the ten-client soak recorded acknowledgement p95 of 275 ms.
- Demonstrated crash recovery without additional model dispatches and reproduced a recorded model-generated Django repair against 110 tests, with one skip; exposed patch, context, check output and unsuccessful attempts for inspection.

Use “built” only when you can explain the request path and debug the implementation. The repository and receipts support software claims; candidate code ownership still requires the candidate’s own explanation.

## Claim-to-receipt map

| Claim | Evidence | Exact boundary |
|---|---|---|
| Full-stack investigation workflow | Source modules, `evidence/build004/backend-final.txt`, `browser-oidc-final.txt`, `docker-smoke.json` | Next.js UI, FastAPI, PostgreSQL, actual OIDC and sandboxed checks. Local operation; no outside-user adoption claim. |
| Durable submissions and tenant authority | Backend regression receipts and real OIDC journeys; delivery real-browser receipt | Repeated command identities return the saved investigation. Conflicting payloads reject. Roles and tenants are checked on the server. |
| Recovery without repeated model dispatch | `evidence/build004/crash-recovery.json` | Two real SIGKILL drills: a pending dispatch stays unknown, and a captured result resumes without another dispatch. This does not establish exactly-once execution at an external inference provider. |
| Measured local control-plane capacity | `evidence/build004/capacity-summary-final.json` and preserved raw measurements | 435,270 requests; four three-minute stages and a 30-minute ten-client soak. Soak acknowledgement p95 275.19 ms, read p95 16.79 ms. This is not inference, OIDC, production or hardware-saturation throughput. |
| Recorded agent patch reproduced | `evidence/build005/repair-reproduction.json`, prior `evidence/build004/repair-reproduction-final.json` and original `build003` record | One distinct historical Django defect. Fresh source and the original model patch ran 110 tests with one skip. The rebuilt image difference is disclosed. Single-call and loop solved the same case; this does not establish loop superiority. |
| Evidence survives restore | `evidence/build004/restore-final.json` | Fresh local database/artifact target restored 109 investigations, 1,145 objects and 1,546 references. No offsite recovery or production recovery-time objective was measured. |
| Reviewer can inspect without live inference | `dashboard/evidence/manifest.json`, recorded integrity tests and delivery browser receipt | Genuine published captures; explicit recorded mode. Private execution and sign-in are disabled. There is no silent fallback when live services fail. |
| Clean-checkout delivery works | `evidence/build005/final-checks.json` and delivery manifest | Claim this only after the aggregate receipt is passing. Installation, isolated services, browser journeys and reproduction retain their own outcomes and logs. |

Relative receipt names in the first six rows refer to `evidence/build004/` unless a complete path is shown. The delivery receipt reports current checks; build004 receipts preserve the environment and outcomes actually measured at that release.

## Results to disclose accurately

The newer frozen study contains 36 evaluation attempts across twelve cases and three strategies. **Zero verified repairs.** All 78 development/evaluation attempts remain recorded. Two interrupted attempt durations are incomplete; unknown response usage is not assumed to be zero. Public historical cases may have appeared in training data, and source regions were localized manually.

The original mixed-workload soak failed during a database restart. The quieter completed repeat passed after bounded connection-pool and benchmark-harness corrections. Both outcomes remain visible. The restart’s original cause is unproven; the repeat does not retroactively make that run successful.

Build004’s full backend invocation reported 213 passed and two opt-in skips. The local model-schema and Docker-isolation opt-ins passed in a separate invocation. Do not combine them into a fictitious single test run. Delivery checks state their own skip reasons; recorded mode cannot test live inference.

Do not claim production scale, broad repair competence, proven multi-call superiority, model research, signed provenance, immutable history against privileged rewrites or adversarial test-forgery resistance. A hash manifest proves local consistency relative to the manifest being trusted. Containers exercise bounded isolation; the current verifier does not establish resistance to an agent forging the test environment.

## A concise interview explanation

“Kairos makes repository-repair investigations inspectable. A browser submission carries a stable identity; PostgreSQL commits its durable receipt before acknowledgement. A worker claims work using database-clock leases and fencing. The agent receives bounded source tools, while registered checks run in a disposable container. The website shows saved context, proposed patches, check output and comparative inference cost. Recovery preserves uncertainty rather than quietly calling the model again. The control plane passed the measured local load protocol; the newer model study earned zero verified repairs. I can reproduce one earlier successful Django patch and explain why the newer failures limit the model claim.”
