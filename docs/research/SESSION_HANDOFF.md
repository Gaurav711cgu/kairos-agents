# Session handoff (resume point)

Updated: 22 October 2026. Read this, then `docs/PRODUCTION_READINESS.md`, then `BRAIN.md`.

## State
- Branch `Gaurav711cgu/feat/measurement014`. Pushed: `c357e1b`. Local, not pushed: `eda2565`
  (pilot qualification/scoring/tests/docs) and `15d48b9` (fullstack acceptance receipts).
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
- Steps and commands: `docs/research/F024_PILOT_MANIFEST.md` section 6.

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

## Latest results (cycle 2)
- Fresh-clone fullstack acceptance passed (`evidence/acceptance024`) once the user's uncommitted e2e
  and codesage fixes were applied in a scratch clone. The user must commit those fixes for HEAD
  alone to pass.
- The measurement014 CI seal fails since pre-session commits. The reseal needs a workflow change,
  which the auto-mode classifier blocks; the user must allow `.github/workflows` edits or apply
  the change.
- The Colab pilot turn one needs the user's browser (steps in the lead's last message and in
  `docs/research/F024_PILOT_MANIFEST.md`). Results go to
  `~/Desktop/resume/kairos-closeout020/f024-pilot/turn1-results.zip`.

## Pilot turn one (actual results, cycle 3)
- `turn1-results.zip` verified: 8/8 generations captured on a Colab T4; journal and hashes valid; peak 10.76 GiB.
- Local validation: 3 accepted, 3 syntax, 1 parse (truncated at 512 tokens), 1 no-op.
- Independent Docker scoring: 0 verified repairs. All 3 accepted edits broke module import, so 0 tests ran.
  These are now classified `candidate_execution_failure` instead of `environment_failure`.
- Fixes made: turn-two planner gates on the token envelope (a 1500-byte budget wrongly refused 2 jobs);
  scorer gained `--work-root` (Finder `.DS_Store` broke the Desktop-hosted registry hash) and
  `--capacity-gib`.
- Turn two is staged: `~/Desktop/resume/kairos-closeout020/f024-pilot/upload-turn2/` (5 jobs, notebook
  `f024-pilot-turn2.ipynb`). The user runs it in Colab and saves `turn2-results.zip` beside the turn-one zip.
- Evidence: `evidence/localization024/f024-pilot/turn1/`. These changes are uncommitted.

## Pilot final (cycle 4)
- Turn 2 came from `~/Downloads/f024-results.zip`, copied unchanged to `f024-pilot/turn2-results.zip`.
  5/5 journals verified; 13 generations in total.
- Final independent scoring: 0/8 verified repairs; 1 executable but behaviourally wrong; 3/5
  turn-two outputs identical to turn one.
- New opt-in `scripts/edit_preflight024.py` (`dangling_removals`) catches all 3 import-breakers
  retrospectively, with 0 false positives.
- Analysis: `docs/research/F024_PILOT_RESULTS.md`; evidence: `evidence/localization024/f024-pilot/turn2`.
  Uncommitted.
