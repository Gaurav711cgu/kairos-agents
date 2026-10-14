# Build007 claims and receipts

Every claim below retains its release and scope. Acceptance status is authoritative in `evidence/build007/final-checks.json`; a code review alone cannot replace it.

| Claim | Evidence | Meaning and limit |
| --- | --- | --- |
| Full-stack workbench | Build007 full-stack acceptance, backend and browser receipts | Next.js/FastAPI, real PostgreSQL/OIDC, durable retries, roles/tenants, progress, pagination, cancel/fork/replay/publication and downloads. No production traffic claim. |
| Explicit migration discipline | Migration regressions and `adoption-restoration.json` | Ordered checksums, bounded locks, transactional receipts, validated build006 adoption, separate runtime role and resumable missing-value operations. No zero-downtime deployment claim. |
| Bounded operational recovery | `operational-drills.json` | Held-lock 503 and same-key recovery; eight held pool connections/40 contenders; restarted local DB preserves 46 study rows. No distributed availability claim. |
| Inspectable source-bound repair workflow | Protocol regressions, source snapshots and 46 genuine new records | Line handles, original digest/bounds, omissions, failure feedback, duplicate-candidate reuse and repeated-invalid stop. Fresh repair effectiveness remains failed. |
| Measured local capacity | Preserved `evidence/build004/capacity-summary-final.json` and lossless raw archive | 435,270 control-plane requests over 42 minutes, zero unexpected errors; ten-client acknowledgement p95 275.19 ms. Historical configuration; not inference/OIDC/production scale. |
| Saved Django repair reproduction | Build007 repair reproduction receipt | Original model patch, pinned source, actual 110 tests/one skip, rebuilt image difference explicit. No broad competence claim. |
| Complete current study | Build007 study report, qualification/exclusions, frozen lock and website | Five qualified cases, baseline 0/5 and loop 0/5. One development repair is separate. Historical failures preserved. |
| Reviewable distribution | Build007 manifest/index/publication receipt | Sanitized source/evidence archive and exact byte verification. No GitHub publication or signed provenance claim. |

## Résumé bullets

- Built a Next.js/FastAPI investigation workbench with PostgreSQL durable receipts, OIDC tenant authorization, fenced workers and sandboxed patch verification; added explicit checksummed migrations and reproducible reviewer setup.
- Measured 435,270 local control-plane requests over 42 minutes with zero unexpected errors and 275 ms acknowledgement p95; tested crash recovery, bounded lock/pool failures and database/artifact restoration.
- Delivered 122 inspectable investigation records and reproduced a recorded Django patch against 110 tests with one skip; published complete failed repair comparisons and source-bound verification evidence.

## Interview explanation

“Kairos makes repository-repair attempts inspectable and recoverable. A reviewer can see exactly what source the model received, what it proposed and which checks ran. I can trace browser identity through authorization, durable receipt, fenced worker, artifact capture and sandbox verification. The software has measured local behavior; the fresh repair target failed. I separate those outcomes instead of claiming an effective general coding agent.”

Personal code ownership must be demonstrated through explanation, debugging and modification. No automated test establishes staff-level production impact, organizational leadership or outside-user adoption.
