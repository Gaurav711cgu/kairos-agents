# Kairos: portfolio description (AI engineer, SDE, FDE)

Kairos is an evidence-first AI code-repair workbench: a Next.js dashboard, a FastAPI + PostgreSQL
backend, Keycloak auth, and a network-isolated Docker sandbox that independently verifies every
model-generated patch. Every claim below is backed by a test run or a receipt in this repository.

**Honest status (22 October 2026):** the platform and the evaluation pipeline are verified end to end.
Model repair capability is not yet proven: 0/8 verified repairs in the F024 pilot. A root-cause
analysis led to a redesigned repair engine, which is built and tested offline and awaits its first GPU
run.

## One-line versions
- **AI engineer:** Built and evaluated an LLM code-repair pipeline (Qwen2.5-Coder-14B, 4-bit, Colab T4)
  with hash-journaled inference, contamination-safe benchmark splits and sandboxed verification. A
  forensic root-cause study of 13 generations led to a redesigned SEARCH/REPLACE repair loop.
- **SDE:** Full-stack platform (Next.js, FastAPI, PostgreSQL, Keycloak OIDC, Docker) with tenant
  isolation, a crash-safe job worker and reproducible fresh-clone acceptance: 1257 backend tests, 16
  recorded browser journeys, 99 tests on the new repair engine.
- **FDE (forward deployed engineer):** Took an AI system from "demo" to "provable": designed intake of
  real customer repositories and bug reports with strict data separation, debugged failures across
  model, protocol, retrieval and infrastructure layers, and reported results to stakeholders with
  verified numbers instead of mock success.

## AI engineer
- **Inference:** a pinned model revision and dependency profile; a memory-envelope guard (measured peak
  10.76 GiB of 14.6 on a T4); journaled intent and capture per call, so an interrupted call is never
  silently retried.
- **Evaluation discipline:** development, frozen validation and locked holdout kept separate; an
  exposure scan over 398 protected identifiers; reference patches used only as infrastructure
  controls, never shown to the model.
- **Root-cause analysis (F024 pilot, 13 generations):**
  - issue-only retrieval missed every gold file (6/13 generations);
  - 5 of the 7 full-context generations failed from the line-number edit protocol;
  - 3 of 5 retries were byte-identical, because feedback was buried inside JSON.
- **Redesign (025), read from the source of Aider, SWE-agent, mini-swe-agent and Agentless:**
  - content-anchored SEARCH/REPLACE edits;
  - a static guard against deleting names that are still used;
  - feedback as a separate chat turn;
  - at most 3 corrections;
  - hash-chained receipts;
  - an independent re-validation and Docker scorer.
- **Capability probe design:** format-following tasks vs symptom-only repair tasks, so protocol
  compliance is never mistaken for repair skill.

## SDE
- FastAPI service with PostgreSQL row-level tenant scoping and Keycloak OIDC (real-browser OIDC tests
  4/4).
- Next.js dashboard: recorded 16/16, fixture 11/11, lint, types and build pass.
- Sandbox: `--network=none`, read-only root, all capabilities dropped, memory and pid limits; patches
  applied through a path-prefix gate (no traversal, no test or infrastructure edits).
- Reliability: worker crash recovery, deadlines, duplicate-candidate stops, 12 end-to-end worker tests.
- Supply chain: pinned images by digest, locked dependencies, sealed evidence manifests checked in CI.

## FDE
- **Customer-data path:** a plan for intake of real repositories and issues
  (`docs/REAL_DATA_PLAN_025.md`): pinned fetch, tenant-scoped "field" provenance, consent before any
  engineering use, and no mixing with benchmark data.
- **Build-vs-adopt calls:** evaluated external projects against the problem (for example, rejected an
  AGPL-3.0 multi-agent simulator, MiroFish, as the wrong tool and a licence risk).
- **Debugging in someone else's environment:** fixed Docker Desktop state, storage gates, Finder
  metadata breaking hashes, and parquet schema drift, each with a receipt.
- **Stakeholder reporting:** every milestone ends with verified-vs-hypothesis separation and explicit
  approval gates for spend (GPU) and irreversible actions.

## Numbers to quote (all verified in-repo)
| Metric | Value | Source |
|---|---|---|
| Backend tests | 1257 passed, 29 skipped | `evidence/acceptance024` |
| Browser journeys | recorded 16/16, OIDC 4/4 | `evidence/acceptance024` |
| Repair-engine tests (025) | 99 passed | `tests/test_*025*.py`, `tests/test_f025_*.py` |
| Pilot generations | 13 on a Colab T4, 0/8 verified repairs | `docs/F024_PILOT_RESULTS.md` |
| Evidence integrity | 164 files, 0 problems | `scripts/verify_evidence024.py` |

Do not claim: production readiness, or any repair success rate. Neither is supported yet.
