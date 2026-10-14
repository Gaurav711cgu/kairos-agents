# Build 003: real investigations, inspectable repairs

Local implementation and evidence checkpoint, 2026-10-11. No commit, push or public deployment was performed.

## Result

The investigation milestone is implemented. Six historical cases reproduce baseline regression failures and passing reference fixes. The final local model comparison contains twelve actual attempts: **two verified attempts on one distinct case**, repaired by both configurations. The loop did not improve case coverage. Twelve earlier development attempts, the pilot and private crash/browser drills remain separate records.

The earned repair is Django #10914: `FILE_UPLOAD_PERMISSIONS = None` becomes `0o644`. The model authored the replacement; the host only rendered its diff. The selected upstream suite runs 110 tests with one upstream skip. A separate fresh-copy reproduction passed. Reference patches are never substituted for candidate results.

## Frozen comparison

| Case | Split | Single call | Tool loop |
| --- | --- | --- | --- |
| kairos-clock-lease | development | invalid_patch | failed_checks |
| django__django-10554 | development | failed_checks | failed_checks |
| django__django-10880 | development | invalid_patch | invalid_patch |
| kairos-body-limit | validation | failed_checks | failed_checks |
| django__django-10914 | validation | verified_repair | verified_repair |
| django__django-10973 | validation | failed_checks | invalid_patch |

Single-call total: 6 calls, 13,357 input plus output tokens. Tool-loop total: 25 calls, 33,117 tokens. API spend: $0. Calls, wall time, token usage and exact stop reasons are in [attempts.json](../evidence/build003/attempts.json). More inference produced no extra solved case in this sample. Do not derive population accuracy, significance or a leaderboard score from it.

Three development cases and three validation cases each contain one Kairos defect and two public issues. The final v3 development batch ran before validation. Its frozen configuration, source hashes, registry and model manifest digest live in [evaluation-lock-v3.json](../evidence/build003/evaluation-lock-v3.json). Validation was not retuned or rerun to improve its outcome. Interactive reruns are explicitly separate; UI comparison membership uses frozen attempt IDs rather than every newly published v3 record.

## Case qualification and provenance

The registry pins source revisions, images, commands, complete snapshot digests and reference/verification hashes. Public provenance uses a recorded SWE-bench Verified dataset revision. Selection was scoped to lightweight Django Python suites and ordered by instance ID; Astropy was excluded up front for compiled scientific dependencies on the 8 GB host. Django #10097 was excluded before model execution because its reference repair still failed two selected existing tests under pinned Python 3.8. This is not a global scan of every lightweight Python repository.

All six accepted baselines fail and their reference repairs pass. [case-preflight.json](../evidence/build003/case-preflight.json) retains the exclusion and raw checks. Human-selected source entry files and, where needed, line positions are shared across both approaches. The Kairos clock case uses a deterministic timestamp/connection fixture reproducing historical host-clock behavior; it is not an in-container live PostgreSQL clock-skew experiment. The body-limit case executes the historical FastAPI app. Some upstream database-shell tests mock subprocesses; they remain regression tests, not live external database adoption evidence.

Reference fixes, verification files and dataset patches are outside agent-accessible snapshot roots. They are retained in the tracked provenance and ignored runtime verifier area, not inserted into model context. Candidate code and tests share a verifier container during execution. The verifier assumes candidate Python does not forge the test runner or mutate its verification process; no hidden-test secrecy or adversarial attestation is asserted. The earned one-line repair is directly inspectable.

## Implementation decisions

- A separate investigation workflow preserves the existing single-dispatch job contract. Additive idempotent tables store investigations, ordered steps and artifact references.
- Strict actions expose four bounded tools and a final result. No arbitrary URLs, host paths or shell commands are accepted from agents or creation requests.
- Exact source replacements replace raw diff generation in v2/v3. Unique original-text matching, overlap rejection and mechanical diff rendering reduce formatting errors without choosing a repair for the model.
- PostgreSQL owns durable receipts, database-clock deadlines, fencing and a global single-investigation claim. Intent is committed before inference; an uncaptured dispatch stays unknown, while captured results can continue without redispatch.
- The worker preserves issue text, remaining counters and latest verification in measured context, recording source excerpts, omissions and truncation. The model runtime is official Qwen3-1.7B-GGUF Q8_0 with pinned llama.cpp b11552, 4,096-token context, at most 1,024 output tokens, thinking disabled, one slot and fixed generation settings.
- Docker checks use disposable copies, a non-root user, read-only mounts, no runtime network or credentials/socket, two CPUs and 1 GB memory. Python subprocess deadlines and bounded file/output capture limit runaway work. Patches are source-only, at most three files and 200 changed lines.
- Verified repair requires a qualified reproduced regression and the candidate passing the registered regression plus selected existing tests. Execution status and repair outcome stay separate.
- Public records are private until an admin publishes. Downloads and replay verify capture integrity; replay makes zero model/tool calls. Hashes establish local consistency, not immutable or signed history.

## Setbacks kept as evidence

1. Raw-diff v1 and exact-replacement v2 development batches each failed all six attempts. Their requests, responses and rejections remain published.
2. The adapter initially sent a JSON-schema shape accepted but not enforced by this runtime. The adversarial provider probe exposed it. v3 uses the enforced nested `json_schema` form, and the live contract test now proves it. This was an integration defect, not six clean measurements of schema-constrained v1/v2 behavior.
3. Memory pressure and swap growth during combined inference/build work reduced free space below 4 GiB. Checks refused execution. The failure receipt is retained as `backend-tests-resource-stop.txt`. Stopping inference and removing only generated frontend output allowed the OS to reclaim space; the guard was not bypassed.
4. Final review found the public patch route lacked the bundle route's integrity rejection. Added a 409 guard and regression test after evaluation. The evaluated route is preserved under `evaluated-source/routes.py`; model, worker, contracts, registry, patch validation and repository hashes still match the frozen v3 run. A second post-evaluation restriction adds Docker `--pull=never`, preventing a missing image from fetching dependencies during checks. The evaluated sandbox is also archived, and [source-provenance.json](../evidence/build003/source-provenance.json) checks both archived hashes against the lock. No validation rerun was used to change the score.
5. Standalone website startup initially missed copied static assets. Assets were installed before the final restart and actual browser rendering was verified. HTTP 200 alone was insufficient.

## Executed verification

- Backend suite: **199 passed, zero skipped, two dependency warnings** in [backend-tests.txt](../evidence/build003/backend-tests.txt). Includes real PostgreSQL, Keycloak, actual local schema enforcement and Docker isolation. Fixtures are confined to isolated protocol and failure cases. Missing dependencies produce failed checks; a missing image produces an environment failure without a pull.
- Crash drills: two actual SIGKILLs, exit -9. Intent-only becomes unknown; a real captured response continues. Both recover with zero extra model dispatches. Lease expiry is explicitly fault-injected after process death. [crash-recovery.json](../evidence/build003/crash-recovery.json).
- Restore: consistent exported PostgreSQL snapshot and referenced artifacts restored to fresh targets; both current initializers run twice. Receipt covers 25 investigations at that snapshot, before later private browser/crash records. [restore.json](../evidence/build003/restore.json).
- Source and sandbox checks cover tenant isolation, conflicting keys, stale workers, cancellation, counters/deadlines, corrupt configuration/blobs, symlink/traversal/protected edits, overlapping replacements, hidden-material tool rejection, read-only source, no socket/network and oversized output.
- Frontend boundary tests, lint, types and production build have tracked receipts. Browser observations and screenshots record desktop/390 px inspection, comparisons, keyboard/URL step selection, filters, empty/error states, downloads and local authenticated commands.
- Dependency audit and non-root image smoke receipts are specific to the recorded build. The historical Python 3.8 reproduction image is intentionally isolated and is not qualified as a production service or claimed free of every historical dependency issue.

## Reproduction and handoff

[README](../README.md) contains the working fresh-copy command, setup and active module map. A prepared local reproduction uses the exact recorded image. Fresh-machine image replacements require explicit `--image`, retain identical source/verification material, and report changed environment provenance. They do not recreate the original immutable image byte for byte.

The public site leads with real source, actual patch and observed outcome. The inspector presents source changes as before/after panels with real line numbers and muted highlighting. Check counts and failure summaries appear before expandable logs. Context budgets, selected excerpts and model actions use readable summaries; exact requests, captured JSON and complete diffs remain expandable. This is semantic change highlighting, not a language-aware editor or generated explanation of patch intent. It exposes context selection, exact model input/output, ordered steps, independent checks, comparison cost and downloadable evidence. The private workbench exposes registered cases, queue/cancel/fork, recorded replay and admin publication. Historical synthetic URLs remain preserved under a labeled collection.

This supports a full-stack engineering portfolio claim: scoped interfaces, persistence, authorization, recovery, isolation, debugging, testable applied inference and readable evidence. It does not establish general model repair competence, model research, production-scale multi-tenant sandboxing, cloud operations or outside-user adoption. The single successful defect is simple and source-localized; describe its scope plainly.

## Final local acceptance receipts

Frontend boundary tests: 4 passed; lint, TypeScript and production build passed. The final non-root API/web image smoke passed all recorded checks. The earned repair reproduced after the no-pull restriction. [Browser acceptance](../evidence/build003/browser-acceptance.json) covers desktop and 390px layouts, keyboard selection, readable evidence, comparison, downloads, actual unavailable states and private commands. [Final desktop](../evidence/build003/screenshots/kairos-build003-readable-desktop.png) and [mobile](../evidence/build003/screenshots/kairos-build003-readable-mobile.png) captures show the revised inspector. Dependency audits report zero known findings in the recorded npm tree and 30-dependency API lock; this is not a claim about the historical reproduction image.

[Resource snapshot](../evidence/build003/resource-snapshot.json): investigation runtime 2,175,381,504 bytes, frontend build 136,912,896 bytes, three owned image sizes totaling 190,810,132 bytes and 15,148,929,024 bytes free. The 6 GiB guard measures the runtime tree; the 4 GiB reserve measures host free space. Shared Docker cache is not governed by a global project disk quota. Owned measured additions remain below 6 GiB, but shared cache attribution is incomplete.

[manifest.json](../evidence/build003/manifest.json) fingerprints reviewable source and receipts. These are local consistency checks, not a signed release or immutable audit trail. Services remain local; hosted CI, public HTTPS, outside-user adoption and general model research remain separate milestones.
