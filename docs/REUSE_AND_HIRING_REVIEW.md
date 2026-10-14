# Folder reuse and hiring review

Reviewed 2026-10-11 after build003 acceptance. This is a post-release review note, not a new execution receipt. The user confirmed that “karos-new” means `/Users/gauravkumarnayak/Desktop/new-karos`. The resume directory entry links to this checkout; there is no second project to merge.

## What changed since the final source seal

All 170 source files named by the build003 manifest still matched their recorded SHA-256 hashes at review time. No new active implementation files appeared in the Git-visible inventory. This does not inspect ignored private files or prove there was no earlier user work: additions made before the seal are already part of build003. No existing source, evaluation record or manifest was changed during this review.

## Useful full-stack work already active

| Area | Implementation | What it demonstrates | Boundary |
| --- | --- | --- | --- |
| Application UI | Next.js public investigations, readable evidence, comparison and private workbench | A connected user journey with real data, errors, downloads and responsive inspection | Manual browser acceptance; four automated frontend tests cover request bodies, not the UI journey |
| Backend contracts | FastAPI investigation routes and strict registered task/configuration schemas | Authorized commands and inspectable results rather than arbitrary agent shell access | Registered historical cases, not general repository onboarding |
| Identity | Real local Keycloak OIDC, server sessions and database memberships | Protocol integration, role checks and tenant boundaries | One trusted issuer; local development provider, not enterprise adoption |
| Persistence | PostgreSQL investigation/step/artifact tables and content-addressed blobs | Durable receipts, conflicting retry rejection and evidence binding | Local hashes are not immutable or signed history |
| Background execution | Bounded worker, database-clock lease/fencing and recorded recovery | Explicit uncertain dispatch handling and continuation from captured results | One global active investigation; no scale or fairness claim |
| Operations | Non-root images, isolated checks, fresh-copy repair reproduction and consistent restore drills | Reproducible local operations and failure investigation | No public deployment, hosted CI run, SLO history or regional recovery claim |

These are already integrated. Copying them into another backend or rebuilding the same features would add duplication rather than evidence.

## Prototype material kept outside execution

- `harness/events.py`, `harness/context.py` and `harness/verifier.py` contain useful ideas: native events, explicit context selection and deterministic checks. The active workflow already implements narrower, tested versions of those ideas.
- `ingest/storage.go` has a useful transaction boundary for events and outbox entries. Its separate SQLite/Go service does not solve a measured bottleneck in the current one-investigation workload. `ingest/server.go` still shares request push/drain operations, reports success despite drops and ignores an outbox-count error in health reporting. These are source observations in this review, not newly executed failure drills. Do not promote it merely to add Go to the stack.
- `engine/ablation.py` is not credible component-effect evidence. Its named no-verifier condition changes the model stub to return wrong answers while constructing the same verifier-enabled configuration. Its no-compaction condition also changes the token budget. These comparisons confound the claimed cause. Do not import the resulting gains or confidence intervals into model claims.
- `engine/fork.py` and the old recovery path retain the limitations in `LEGACY_REUSE_REVIEW.md`. The current API intentionally creates a fresh case run; it does not pretend to resume arbitrary historical model state.
- `storage/schema.sql` retains the previously documented partition-key issue. Keep the tested additive product schemas.

Decision: reuse the architectural lessons and regression cases already incorporated. No additional prototype runtime code or headline metrics were imported. Existing historical files remain intact.

## Hiring assessment using a staff engineer's review bar

This project merits a technical conversation for a junior SDE or full-stack candidate. The strongest signals are explicit failure semantics, database ownership of state, real identity integration, source isolation and honest evidence. A recruiter can inspect a genuine repair and then follow the engineering decisions underneath it.

It does not establish senior or staff readiness. Those levels require evidence of operating systems under changing requirements, managing tradeoffs at scale, coordinating work with others and influencing outcomes over time. A single portfolio project cannot establish that history.

Applied AI engineering has credible workflow and evaluation work here, but limited model effectiveness: both configurations solve the same one of six small, human-localized historical cases. The loop uses more compute without extra solved cases. This is not model research or general repair competence. FDE readiness also needs a real person's workflow, deployment constraints and adoption feedback; none was measured here.

An interview would test whether the candidate can explain the durable intent/unknown-dispatch decision, diagnose a stale worker, trace a request from browser to database, explain hidden-verifier limits, and modify the implementation while preserving those properties. AI assistance is compatible with ownership; an inability to explain or debug the code is not.

## Highest-value remaining evidence

1. Exercise the complete private user journey with repeatable browser tests, including delayed and out-of-order responses. Current workbench requests can complete asynchronously without a latest-selection guard; this is a source-level review concern, not a reproduced acceptance failure.
2. Improve maintainability in the active frontend and worker/repository code. Dense multi-operation lines and combined request/state/render concerns make review harder. Refactor against meaningful behavior tests rather than adding lines of mirrored tests.
3. Ask a real reviewer to use the local product, record where they get stuck and fix those issues. Recruiter-facing polish should follow observed comprehension, not invented adoption numbers.
4. Improve actual repair coverage only through a new declared development protocol and a fresh evaluation set. Preserve the current validation results and disclose additional compute/localization.
5. Add deployment and load evidence only when a concrete usage target exists. Do not add Kubernetes, another database or an ingest service solely for breadth.

Interview-worthy means a reason to investigate the candidate further, not a promised hiring outcome. The candidate's own explanation, coding, debugging and collaboration remain decisive.
