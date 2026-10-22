# Session handoff (resume point)

Updated: 22 October 2026. Read this, then `docs/PRODUCTION_READINESS.md`, then `BRAIN.md`.

## State
- Branch `Gaurav711cgu/feat/measurement014`; last commit `c357e1b` (pushed). Later work is
  uncommitted: the F024 qualify/score/GPU-mock/e2e/verifier files and these docs.
- 65 pre-existing user paths are uncommitted and must never be touched (list kept in the lead's
  scratch board; recreate with `git status --short`, excluding f024/F024/e2e/verify/STATUS/
  READINESS/HANDOFF files).
- Docker Desktop is stopped. Control it with `docker desktop start` and `docker desktop stop`,
  and gate on pinned-image inspection before any qualification or scoring.

## Pilot (approval-gated)
- Staged upload: `~/Desktop/resume/kairos-closeout020/f024-pilot/upload-v2/`, runner
  `9b244ef5…`, package `71b184b4…`. The old `upload/` is stale.
- Qualification: `qualification-v4` (both cases qualified). Use `--capacity-gib 8` for future
  qualification runs, because pre-existing runtime data exceeds the default 6 GiB gate.
- Steps and commands: `docs/F024_PILOT_MANIFEST.md` section 6.

## Team
Teammates A (repair-engine), B (inference-bridge) and C (verification-qa) are coordinated
through a scratch board. On a context reset, recreate ownership from `docs/PRODUCTION_READINESS.md`
owners. Open tasks at the last update: T5 security triage (C), T6 local CI parity (C), T7 worker
timeout and duplicate-candidate tests (A), T8 REAL security fixes (A, depends on T5).
Cycle 1 result: T5 0 REAL of 17, T7 done (12 e2e tests), T8 nothing to fix, T6 found the pre-existing
measurement014 seal failure (see PRODUCTION_READINESS row 10). No open permitted tasks remain.

## Invariants
Development cases only; validation is frozen (one H3 run recorded); holdout never fetched;
exposure scan 398 identifiers locally. No commits, pushes, Colab, downloads or Docker workloads
without approval. Repair success unverified.
