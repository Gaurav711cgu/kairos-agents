# Kairos working brain

Updated: 2026-10-11, Asia/Kolkata. Status: **build 001 local vertical slice implemented and checked; flagship project still in progress.**

## Start here

Primary goal: SDE/full-stack evidence through a polished recruiter website and explainable backend, persistence, debugging and interaction. Applied AI/FDE/harness/loop depth must earn separate evidence.

Product: Kairos turns agent failures into inspectable incidents, isolated experiments and evidence-backed release decisions.

Actual project: `/Users/gauravkumarnayak/Desktop/new-karos`; `resume/new-karos` is a symlink. Resume planning files mirror `docs/planning/` in the project. Do not create another prototype or overwrite unrelated repositories.

## Implemented checkpoint

- Next.js editorial public site: home, incident archive/inspector, engineering, evidence and docs. Paper/ink/forest design, local fonts, actual populated records; no sample-data fallback in active routes.
- Python/FastAPI + PostgreSQL command/run/event authority. Commit precedes response; synchronous commit enforced and fsync required. Scoped idempotency keys bind request digests, tenant comes from configured developer credentials.
- Bounded deterministic reference scenarios: exception failure, ordinary success, missing-evidence abstention. Independent grader reads complete source facts. Fresh full-scenario forks preserve parent lineage.
- Seven published executions/49 events at the saved evidence snapshot: four seeded records plus three browser-created forks. Counts are descriptive and can change.
- Exact context inclusion/omission, filterable timeline, URL event state, keyboard navigation, explicit outage state and production-disabled mutation proxy.
- 27 backend checks passed (14 unit,13 actual PostgreSQL), also passed with locked dependencies in a fresh Python3.12 environment. Lint, TypeScript and production build passed, including Node24.15.0. Manual desktop/mobile/fork/outage/production browser checks saved. Hosted CI has not run.
- Offline Qwen2.5-0.5B probe passed **0/4** strict development cases. Raw responses preserved. This separate probe uses a different exception/threshold and is not integrated with the product runner or a qualification study.

Current services: API `127.0.0.1:8100`, web `127.0.0.1:3100`, PostgreSQL `127.0.0.1:55432`. Container `kairos-postgres-build001`, named persistent volume. Do not launch Compose over the occupied port. Ignored local env files contain credentials; never print or commit them.

## Read only what the next task needs

| Need | Read |
|---|---|
| Current checks, commands, limits | `docs/BUILD_001.md`, `evidence/build001/manifest.json` |
| Product/source boundaries | `PLAN.md`, `ARCHITECTURE.md` |
| User intent and assumptions | `CONTEXT.md` |
| Why a choice exists | Relevant Dxx in `DECISIONS.md`; D17-D19 cover build001 |
| Next milestone | Relevant Pxx in `IMPLEMENTATION_PLAN.md` |
| Failure or claim | Relevant Fxx in `FAILURE_MODES.md`, Exx in `EVIDENCE.md` |
| Website interaction | `WEBSITE_SPEC.md`, then active dashboard source |

Planning links above resolve inside `docs/planning/`; root BRAIN copies this checkpoint. Inspect relevant source before editing; documents do not substitute for execution. Old harness/engine/Go ingest and unused dashboard components remain legacy code outside this path.

## Next work and open gates

P00/P01 remain partial. First align the real model probe with versioned product tasks and independent grading; save a model-specific error taxonomy and baseline. Math belongs in a deterministic tool, schema constraints need explicit validation, exceptions need preserved provenance, and insufficient evidence needs abstention. Do not hide failed outputs through permissive parsing.

Before remote model calls join execution, design durable intent/result jobs and unknown-outcome handling; current bounded reference execution inside one transaction is unsuitable for slow remote work. Compare existing runtime/checkpoint capabilities before building an orchestration framework.

Still unimplemented: managed auth/memberships, async worker leases, arbitrary checkpoint resume, approval/effect reconciliation, object storage, calibrated held-out release decisions, restore/load evidence, hosted deployment and outside-user feedback. Five related high npm audit entries remain in dev lint tooling; runtime audit reports zero. One TestClient dependency deprecation remains.

## Claim discipline

Synthetic records are labeled. Hash consistency is not immutable history. No detected regression is not safe release. Website polish is not usability proof. Deployment is not adoption. Calling a model is not model research. No fabricated metrics, users, model outputs or test results.

Update this checkpoint after meaningful work; add evidence and decision IDs, keep below750words, and do not rescan all documents each turn.
