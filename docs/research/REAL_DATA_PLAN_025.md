# Real-data intake plan (025)

Status: plan only, 22 October 2026. Nothing here is built. Goal: let real user repositories and bug
reports flow through the same repair path as benchmark cases, without leaking into the benchmark
splits and without weakening the sandbox.

## Is MiroFish the answer? No (checked 22 October 2026 via the GitHub API)

`666ghj/MiroFish` (AGPL-3.0, Python and Vue) is a swarm social-prediction simulator. It turns seed
documents (news, reports, novels) into a GraphRAG memory (Zep Cloud), generates thousands of agent
personas, simulates social interaction, and writes a prediction report. It needs a paid
OpenAI-compatible LLM API and a Zep key. It does not ingest code repositories, edit code, run tests or
verify patches, so it does not solve Kairos's real-data problem.

- **Licence:** AGPL-3.0. Copying its code into Kairos would put Kairos under the AGPL.
- **Idea worth reusing:** turn raw seed material into a queryable graph before the model sees it. For
  code this is a repository symbol/import graph, which Kairos already partly has
  (`scripts/codesage_mcp_client.py`, `kairos_api/investigations/context_v7.py`). It targets root
  cause 1 of `REPAIR_REDESIGN_025.md` (the issue-only context missed every gold file).

## What exists today
- Cases enter only through the server-owned registry `cases/investigations.json`
  (`kairos_api/investigations/registry.py`, `CaseRegistry`): curated SWE-bench cases with frozen
  provenance and `tree_hash` fingerprints.
- The repair path is already case-agnostic: `Workspace` (snapshot, prefix gate, read-only original),
  the 025 loop (`scripts/repair_loop025.py`) and Docker `workspace.checks` (network none, read-only,
  cap-drop). There is no intake for a user's own repository or issue.

## Design: one new adapter, everything else reused

```
user submits: repo (git URL + full commit SHA, or tarball) + issue text + optional visible test command
      │
      ▼
intake025: bounded fetch (size cap, approved hosts, pinned commit) → tree_hash → registry case
      │      tenant-scoped, provenance = "field", never benchmark
      ▼
retrieval: issue → symbol/import graph (context_v7 + CodeSage) → regions (+ bounded READ in loop)
      ▼
repair_loop025 (≤3 corrections) ── feedback: match/scope/syntax/dangling + visible test in Docker
      ▼
verification: user's visible tests in the pinned sandbox → patch + hash-chained receipts
      ▼
human review in dashboard → accept / reject  (only a human-accepted patch leaves Kairos)
```

| Piece | New or reused | Note |
|---|---|---|
| `scripts/intake025.py` | new | Writes a case in the existing `repository-cases-v1` schema. Fetches only a pinned commit from approved hosts, with a size cap (same limits as `qualify014.pinned_source`). Accepts no credentials in phase 1 (public repos only). |
| Environment image | new per repository | Phase 1: a fixed list of base images per language. Unknown dependency sets are refused rather than installed with network access during checks. |
| Retrieval | reuse | context_v7 + CodeSage graph; measure recall on dev cases first (gold-file hit rate). |
| Repair loop | reuse | `repair_loop025` + `search_replace025`; check = Docker `workspace.checks` with the user's visible command. |
| Storage and tenancy | reuse | `InvestigationRepository` (PostgreSQL, tenant column, Keycloak auth). |
| Dashboard | reuse + one view | Patch review and accept/reject; a mock status stays labelled as mock (`evidence-mode`). |

## Data separation (non-negotiable)
- Field cases get provenance `field` and live per tenant. They are never added to development,
  frozen validation or the locked holdout.
- Before any field case is used for engineering, it must be (a) consented by the tenant, (b) checked
  by the existing exposure scan against the 398 validation/holdout identifiers and their repository
  commits, and (c) placed in a separate "field development" pool.
- No field data is used for training without a separate, explicit decision. No retraining is planned.

## Security
- Untrusted repository code runs only in the existing Docker sandbox: `--network=none`,
  `--read-only`, `--cap-drop=ALL`, memory and pid limits. No host execution
  (`subprocess_check` stays synthetic/Colab only).
- Fetch: pinned SHA, approved hosts, size cap, no submodules, no LFS, symlinks preserved but never
  followed out of the tree (`source_path` gate).
- The issue text is untrusted input. The model only ever sees it as data, and no model output is ever
  executed outside the sandbox.

## Phases and exit criteria
1. **Prove repair first.** The F025 Colab probe must show at least 1 verified dev repair before field
   intake matters. Without it, real data only collects failures.
2. Retrieval recall: gold-file hit rate on the development set, before and after graph retrieval.
   Target: higher than the F024 issue arm's 0/2.
3. `intake025` + 1 language (Python) + public repos, offline tests with a local fixture repository.
4. Dashboard review flow; end-to-end on 3 consented field cases. Report verified rate with its count.
5. Only then: private repos (credential handling), more languages, a sustained GPU host (spend
   decision).

## Open questions for the owner
- What "real data" means here: user repositories and bug reports (assumed above), or production logs
  and incidents?
- Whether paid inference is acceptable for field use. A free T4 cannot serve concurrent users.
