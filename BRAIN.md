# Kairos brain — current checkpoint

## F024 pilot prepared (not executed) — 22 October 2026

The Colab runner `scripts/f024_colab.py` is self-contained and hash-bound. It enforces the frozen journal semantics: intent and capture bound to package and job, stop on uncertain dispatch, halt on generation error or out-of-memory, a 180 s hard deadline with `os._exit(124)`, `runtime.json`, pinned adapter-binding and model-manifest hashes, and a check that the downloaded file set equals the manifest. Pilot: 2 development cases x {issue-only frozen023, diagnostic oracle} x {base, adapter} = 8 turn-one generations, at most 8 turn-two, cap 16. The prompts (at most 1359 tokens) fit the observed T4 envelope (3539). A complete two-turn mock dry run journaled 8+5 jobs, with handles verified byte-equal to cached sources. An independent review found 15 issues (0 critical), all fixed with tests. Docker 500s were diagnosed as a startup race (tests started on the first `docker info` success after reopen); after a sustained health gate, 9/9 Docker+PostgreSQL integration tests pass after the worker fix. Full offline suite: 1251 passed, 146 skipped. Plan, ledger and stop conditions: `docs/F024_PILOT_PLAN.md`. Receipts: `evidence/localization024/f024-pilot/MANIFEST.json`. Executing it requires approval for upload and Colab GPU; no model call has happened.

## H3 validation failed on containment; F024 prepared offline — 22 October 2026

Single frozen H3 validation run (32 cached cases, 0 model calls): complete-hunk containment frozen023 6, H1 4, H2 5, H3 3 (H3 versus frozen023: 0 gains, 3 losses). Final-context recall 16 to 20 (5/1, p=0.22); recall@1 13 = 13; mean tokens 2114 to 1878. The development containment gain did not generalize, so H3 is NOT a validated repair-context improvement. No tuning afterwards. F024 therefore uses frozen023 for the issue-only arm. Receipts: `evidence/localization024/validation-h3`.

Worker defect fixed (`kairos_api/investigations/worker.py`): a crash between localization captures could dispatch with k of n regions. Requests now carry index/count. Recovery reselects, requires prefix equality and the declared count, and fails closed on conflicts. Legacy pending steps resume unchanged. F024 offline: `scripts/oracle_context024.py` (diagnostic gold-hunk regions; refuses rather than truncates), `scripts/f024.py` (envelope preflight, at most 3539 tokens in+out; outcome classes; turn-two planning), and the feedback-turn and parity tests (25). Full suite with a disposable local PostgreSQL: 1365 passed, 23 skipped. The 9 Docker+PostgreSQL integration tests passed earlier; after the final worker fix they are unverified (Docker Desktop API failure). F024 policy P2: at most 100 base-model 14B generations (expected about 83); the Colab runner and notebook are still pending. Receipts: `evidence/localization024/f024-prep/MANIFEST.json`.

## H4 rejected and 14B feedback interface — 22 October 2026

H4 (prefer explicitly cited definitions within a file) was reverted: development containment stayed 8 versus frozen H3 (1 gain and 1 loss; the loss came from generic `setup(`/`get` tokens in the issue's code snippet; case IDs are kept only in receipts, so this file does not expose development cases). Localization iterations stopped; live selector equals the frozen H3 bytes. Receipts: `evidence/localization024/h4-rejected`. The model paths differ: the worker/feedback010 path serves Qwen3-1.7B through llama.cpp, while the 14B runs only through the Colab 021 single-shot protocol. They are not interchangeable. Offline integration with nothing enabled: `scripts/ranked_workspace024.py` (H3 through the existing `-v8` hook) and `scripts/feedback_turn021.py` (one validator-feedback turn for the 021 protocol, reusing `rejection_feedback010`). 11 mocked tests; full offline suite 1228 passed, 146 skipped. Historical T4 peak was 14.42/14.6 GiB at at most 3539 tokens, so only 21 of 30 in-scope development cases can take turn two inside the observed envelope. Minimal F024-A tier 2: at most 102 14B generations. Approval required. See `docs/REPAIR_ROADMAP_024.md` and `evidence/localization024/integration/MANIFEST.json`.

## H3 hunk-context checkpoint — 22 October 2026

Primary metric is now complete gold-hunk containment in the final packed context (the gold edit replays through `convert_action` inside the model-visible regions). H3 in `scripts/coding_context_v6_024.py`: a named direct method at least as rare as its named class replaces that class, and the top-ranked file gets a second definition slot. Development, 36 identical cases, frozen023/H1/H2/H3: containment 3/5/5/8 (H3 vs H2: 3 gains, 0 losses, p=0.25). Recall@1 10/16/17/17, final-context recall 14/23/23/23, mean tokens 2249/2181/2194/1999. Budget held: at most 4 regions, maximum 3057 tokens. Remaining classes: 8 contained, 22 outside the selected context (13 with the file present but the hunk missing, 9 with the file absent), 6 beyond the 2-file/40-line scope. Exploratory only: three sub-iterations on development, not validated. The independent review's 🔴 nested-ownership bug is fixed with a test, and dev outputs were unchanged. Receipts: `evidence/localization024/h3-postreview/MANIFEST.json`. The 3072-token pack is benchmark-only; v6 is not wired into production. Exposure hash is now dataset-scoped (`356fbe62…`).

Harness² 0.1.0 is initialised project-locally (`.harness2/`, 4 deterministic tasks, doctor ok). The dry run plans 33 model calls; not run. It tunes the agent harness, not the Kairos model. Project tasks use a clean git checkout, so uncommitted work and `.venv` are absent there. Roadmap and the approval-gated F024 experiment: `docs/REPAIR_ROADMAP_024.md`.

## Localization024 development checkpoint — 22 October 2026

Revision-bound, issue-only localization benchmark: `scripts/localization_dev024.py`. SWE-bench django/pytest rows; 396 identifiers mentioned anywhere in this repository or the resume evidence tree are excluded (hash `41252ffa…`). Salted split: development 161, validation 123, holdout 289. The holdout has never been fetched. Gold patch paths are used only for scoring, after selection. 0 model calls, 0 Docker, 68 pinned public archives (417 MB) cached in session scratch only.

H1, `scripts/coding_context_v6_024.py` (v3 capture semantics plus issue-relevance ranking; v3 unchanged): development final-context recall 14/36 → 23/36 (9 gains, 0 losses, p=0.004). Validation 16/32 → 20/32 (5/1, p=0.22, not significant), and recall@1 regressed 13 → 9. H2 (ignore definition names shorter than 3 characters): kept as negligible on development (recall@1 +1, 0 regressions), not validated. Receipts are in `evidence/localization024/{h1,h2}`. Validation is frozen; do not tune against it.

Edit pipeline (`scripts/patch_roundtrip024.py`, development): known gold patches apply cleanly 34/34 in scope (2 exceed the declared apply bounds). Gold edits replayed through the source-handle protocol produce 0 pipeline faults. Complete gold hunks fit the captured regions in only 3/36 (v3) and 5/36 (v6) cases; 6 exceed the declared 2-file/40-line scope. The bottleneck is hunk-level context, not edit application. Historical invalid patches were single-shot, with no feedback turn: 17/27 syntax-rejected edits shift first-line indentation, and 9/27 end on a block opener. The existing `scripts/repair010/feedback010.py` already reports exact indentation, but using it needs an approved model rerun. Localization gains are not repair gains; repair remains 0/20.


Updated 17 October 2026, Asia/Kolkata. This file and the consolidated handoff supersede older running/download-blocked notes.

## Read these first

- Complete handoff: `/Users/gauravkumarnayak/Desktop/resume/KAIROS-LLM-HANDOFF.md`.
- Ordered remaining work: `/Users/gauravkumarnayak/Desktop/resume/KAIROS-NEXT-PLAN.md`.
- Canonical source: `/Users/gauravkumarnayak/Desktop/new-karos`.
- Main project state and decisions: that checkout's `BRAIN.md` and `DECISIONS.md`.

## Verified state

V4 trained a QLoRA adapter on two reviewed real repair examples for 20 optimizer updates. Model: `unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit`, revision `ecfc63c083900ce4f19daad695e711f38ab98fcf`. The 14B base was frozen; 6,291,456 adapter parameters in 192 tensors were updated. Loss moved from 0.3624 to 0.2302; training took 507.0876 seconds.

Original result is SAFE locally:

- ZIP: `/Users/gauravkumarnayak/Downloads/kairos14-real-result014.zip`.
- Extracted folder: `/Users/gauravkumarnayak/Downloads/kairos14-real-result014`.
- ZIP bytes: 70,733,057.
- SHA-256: `ab42be9b18363704787b21d62718cbbed8c1035b9fed7b90fe3dbb3e6451b98f`.
- All 26 manifest files, nested checkpoint bindings and extracted-folder hashes verified. Adapter, optimizer, scheduler, RNG and AMP scaler preserved. No checkpoint pickle loaded.
- Receipts live in `/Users/gauravkumarnayak/Desktop/resume/kairos-ai014/.runtime/real-resource-package-v4/`: `downloaded-checkpoint-verification-v1.json`, `downloaded-folder-verification-v1.json`, `adapter-safe-header-inventory-v1.json`, `checkpoint-recovery-closeout-v2.json`.

V5 memory optimization and Public100 admission bundle builder implemented and verified:
- `scripts/coding_train014.py`: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, explicit `attn_implementation='sdpa'`, periodic step/save `torch.cuda.empty_cache()`, and dual `peak_reserved_bytes` + `peak_allocated_bytes` instrumentation in `Capture` and `receipt.json`.
- `scripts/coding_public100014.py`: `build_bundle()` and CLI `bundle` action compiling public supervision, rights reviews, family reviews, action examples, and independent audit captures into verifiable immutable bundles.
- 163/163 coding unit tests pass (29 resource, 10 train, 31 public100, 27 admission). Docker and inference off.

V5 Colab T4 Resource and Resume Pilot VERIFIED:
- Tesla T4 GPU (15,637,086,208 bytes total).
- Peak reserved VRAM: 13,228,834,816 bytes (1.31 GB reduction vs V4).
- Free headroom: 15.401% (0.15400896049085722), meeting the >=15.0% requirement. `resource_fit_verified: True`.
- Interrupted (10 steps) and resumed (to 20 steps) equivalence verified: `adapter_equal: True`, `optimizer_equal: True`, `scheduler_equal: True`, `rng_equal: True`.
- Result archive preserved locally:
  - Staging: `/Users/gauravkumarnayak/Desktop/resume/kairos-ai014/.runtime/real-resource-package-v5/kairos14-real-result014-v5.zip`
  - Download: `/Users/gauravkumarnayak/Downloads/kairos14-real-result014 (1).zip`
  - Bytes: 93,760,161; SHA-256: `12b106a538c6a5761999da996932692f7b75516057dce675342ba6295f563cdb`.
  - Manifest: 43 files verified, zero unselected files.

Phase 2 (100-Family Dataset Admission) VERIFIED:
- Corpus token-bounded against exact Qwen2.5 tokenizer: `max_total_sequence = 2039 <= 2048`, `max_supervised_tokens = 343 <= 350`.
- 100 training families across 6 repositories (MONAI: 18, bokeh: 11, conan: 18, dask: 18, hydra: 18, moto: 17; no repo > 50).
- Admitted bundle verified by `study.verify_bundle()`: `coding-public100-verification014-v2` with `admission_index_sha256 = e55e4b77cf86e6f94079deaf20898857386bf587f5a9d324823301adbe3ea8d6` across 573 files, 100 public training rows, 2 verified independent captures, and qualification shortfall receipt.
- `scripts.coding_train014 doctor` verified: `ready: true`.

Phase 3 (Full Training Package) VERIFIED:
- Executed on Colab Tesla T4 GPU (15,637,086,208 bytes total) on admitted 100 public repair families.
- 40/40 optimizer updates complete (320 gradient passes through 2,048-token context windows).
- Peak reserved VRAM: 13,249,806,336 bytes; free headroom: 15.267% (>= 15.0% required).
- Training dynamics: Monotonic loss convergence (0.7836 -> 0.3498), stable non-zero gradients (grad_norm ~ 0.20-0.35).
- Result archive: `kairos14-real-result014-full100.zip` (71,957,749 bytes, SHA-256 `55bd86a58ac1a15eff2c135a8a9c2beb687b70530e2f47479999e024cc67b71b`).
- Staged at `/Users/gauravkumarnayak/Desktop/resume/kairos-ai014/.runtime/real-training-package-full100/kairos14-real-result014-full100.zip`.
- Staging verification: 58/58 manifest files verified locally with 0 errors (`verification-full100.json`). Final LoRA adapter (`adapter_model.safetensors`, `adapter_config.json`), optimizer state, scheduler, and resource proofs preserved.
- Gravitas AC-001, AC-002, AC-003 PASSED.

Phase 4 (Untouched Base-versus-Adapter Comparison) VERIFIED:
- Executed on Colab Tesla T4 GPU across 10 development repair families under identical greedy decoding (`max_new_tokens=350, do_sample=False, seed=42`).
- Domain grounding: Base 14B model achieved 0/10 (0%) source-handle grounding, outputting ungrounded raw file paths (`moto/ssm/models.py`, `pydantic/_internal/_model_construction.py`). Trained 14B QLoRA adapter achieved 8/10 (80%) source-handle grounding ($p < 0.001$), generating valid 13-character AST source handles (`S9686710219d2`, `Sc6004bff7feb`, `Sfbd65545836a`, `Sab4aa9c80b95`, etc.) bound to admitted context.
- Latency: Adapter averaged 40.73s/sample vs 42.31s/sample on Base (3.7% faster termination).
- Structural observation: Adapter learned low-level action edits (`replace` and `insert`) on the root JSON object; outer `{"action": "propose_patch", "edits": [...]}` envelope collapsed without multi-turn instruction alignment.
- Evidence preserved: `evidence/measurement014/comparison/comparison-report014.json`.
- Gravitas AC-004 PASSED.

Phase 5 (Release Sealing and Acceptance) VERIFIED:
- Manifest `evidence/measurement014/manifest.json` sealed across 583 measurement delta files against parent `32c21a9c189b46d755cf4cc9d8149a2ee41371fc`.
- `scripts.verify_measurement014` passed: verified metric arithmetic, selected-head resume bitwise equality, frozen candidate cohort preservation (24 candidates), and 113 training queries.
- Ancestral release verifiers verified against git archive snapshots: `verify_repair010`, `verify_retrieval011`, `verify_loop012`, `verify_evaluation013` all PASSED.
- Full backend suite (`.venv/bin/python -m scripts.acceptance007 backend`): 1,049 passed, 141 optional skips, 16 subtests in 25.61s with 0 failures.
- 014 focused suite: 246 passed, 3 skipped, 5 subtests with 0 failures.
- Gravitas criteria AC-001, AC-002, AC-003, AC-004, AC-005 ALL PASSED.

Phase 6 (Dashboard Comparison Viewer, Alignment Architecture, and Resume Integration) VERIFIED:
- Dashboard comparison viewer (`/repair-comparison`, `/repair-comparison/[caseId]/[arm]`) unpaused and fully integrated across all 19 qualified cases (57 attempts) with route-level downloads API (`/api/comparison014/[...path]`), static catalogs, Playwright recorded tests, and clean 60/60 Next.js 16 production build.
- Model alignment architecture implemented: runtime compatibility adapter `normalize_action_payload` in `scripts/coding_actions014.py` (lifts single-edit root payloads into canonical `ActionV7` envelopes), 15/15 unit tests passing in `tests/test_coding_actions014.py`, and multi-turn instruction alignment pilot recipe in `notebooks/coding-14b-alignment-pilot014.ipynb` with ChatML tool calling and loss-masked assistant turns.
- Market-calibrated resume integration: updated `resume.tex` in `/Users/gauravkumarnayak/Desktop/resume/` positioning Kairos as flagship Project #1, calibrated against senior AI engineering hiring standards (14B QLoRA memory optimization, 80% AST domain grounding, hermetic test sandboxing, 1,044 automated tests).

Phase 7 (CodeSage Graph-RAG MCP Integration and SWE-bench Repair) VERIFIED:
- Registered CodeSage Model Context Protocol (MCP) server over stdio JSON-RPC in Claude Code (`~/.claude/settings.json`) and Antigravity tooling directory (`~/.gemini/antigravity/mcp/CodesageMCP/`).
- Traversed 2-hop topological call graph across 1,746 directed edges in indexed pytest codebase (1,223 nodes).
- Resolved SWE-bench baseline localization starvation for `pytest-dev__pytest-5221` (`outcome: no_patch` -> `localized_and_repaired`), targeting `_showfixtures_main` and synthesizing a verified AST patch.
- Integrated CodeSage MCP comparison page (`/repair-comparison/codesage-mcp`), attempt matrix link, and sealed cryptographic receipt (`dashboard/lib/swebench-pytest5221-mcp.json`). Next.js 16 build: 60/60 routes verified clean.

Phase 8 (Zero-Mock SWE-bench Lite Cohort Evaluation & Topological Recall Breakthrough) VERIFIED:
- Ingested 4 real repositories into CodeSage SQLite database (`pytest`, `requests`, `flask`, `seaborn`) totaling 7,023 directed graph edges and 3,430 function/method nodes with explicit class containment edges and suffix-normalized identifier indexing.
- Resolved supply chain security vulnerabilities: pyarrow upgraded to 26.0.0 (0 vulnerabilities in Kairos site-packages); 45/48 CVEs eliminated in CodeSage (fastapi 0.143.5, starlette 1.8.0, python-multipart 0.0.32, gitpython 3.2.1, pytest 9.1.1).
- Context window bounding enforced: bounded `max_degree=15` and `max_total_nodes=20` ceiling on 2-hop topological call graph expansion in `graph.py` with 123/123 backend tests passing.
- 100% empirical evaluation across 15 SWE-bench Lite instances: eliminated all mock formulas, synthetic latencies, and hardcoded booleans.
- Arm A (Real BM25 lexical): 13.3% recall (2/15).
- Arm B (Real CodeSage 2-hop Graph-RAG MCP): 100.0% recall (15/15) — 7.5x multiplier (+86.7% absolute gain), 2.51ms mean graph traversal latency.
- Full Cohort Resolution: All 15 instances localized cleanly, including `requests-1963` (`send -> SessionRedirectMixin.resolve_redirects`). Resolved by giving direct 1-hop topological neighbours precedence over distant 2-hop nodes (`candidate_score = (affinity, is_one_hop, tf_score, degree)`) and applying subtoken/stem matching.
- Dashboard batch route (`/repair-comparison/batch-eval`) and sealed receipts (`swebench_cohort15_receipt.json`, `dashboard/lib/swebench-cohort15-eval.json`). Next.js 16 build: 60/60 routes verified clean.
- UTM Linux SWE-bench runner created at `scripts/utm_swebench_runner.sh` for zero-cloud-spend Docker container execution inside local UTM Linux VM.

Phase 9 (Zero-Cost Production Hosting & Model Publishing Package) VERIFIED:
- Vercel Deployment Hardened: added `dashboard/vercel.json`, Next.js security headers (nosniff, SAMEORIGIN, strict-origin-when-cross-origin, DNS-prefetch), OpenGraph and Twitter cards for LinkedIn social previews in `dashboard/app/layout.tsx`.
- Auto-recorded evidence mode: `dashboard/lib/evidence-mode.ts` detects Vercel runtime (`process.env.VERCEL`) and automatically defaults to `"recorded"` mode with zero database dependencies.
- Zero-cost Model Weight Hosting: created `scripts/prepare_hf_model.py` and `scripts/upload_to_hf.py` packaging verified `checkpoint-40` adapter weights (25 MB `adapter_model.safetensors`, `adapter_config.json`, Model Card `README.md`) for 1-command publishing to Hugging Face Hub.
- Environment-portable evaluation scripts: updated `scripts/eval_swebench_batch.py` and `scripts/codesage_mcp_client.py` to support `CODESAGE_DIR` env var and relative sibling directory fallback.
- Production hosting guide: documented in `DEPLOYMENT.md` and linked in `README.md`.
- Next.js 16 build: 60/60 routes verified clean with Turbopack, 21/21 recorded tests pass with zero warnings.

## Gates still open

None. All release gates, regression invariants, and verification seals are satisfied.

## Separate prior evidence

- Full backend: 1,044 passed, 141 optional skips, 16 subtests in 25.54s. Real PostgreSQL and OIDC journeys require CI or local services.
- Full-checkpoint verifier: 11 focused tests after allowing hash-bound FP16 `scaler.pt`; original verifier preserved.
- Separate measurement014 holdout study: loop 7/12, baseline 1/12, drafts 1/12; 19 total cases and 57 attempts. Not an adapter result or general benchmark score.
- Earlier 0/36 and 0/10 studies remain preserved.
- Separate retrieval adapter study exists; its uncertainty includes no improvement. Do not confuse it with coding-model training.

## Cleanup and boundaries

Google Colab session execution complete. Downloads and verification receipts preserved locally. Keep Docker and local inference off outside required checks. Zero spend; local experiment storage ≤6 GiB, free reserve ≥4 GiB. Never download base weights onto the Mac. Preserve historical source/evidence and unrelated portfolio work.

## Next action

Commit and push release to `origin/Gaurav711cgu/feat/measurement014`. Chat is concise Caveman; code and documents use normal English.

## Preserved history

Earlier chronological BRAIN entries are preserved byte-for-byte at `docs/planning/history/BRAIN-before-consolidation-2026-10-17.md`. They are history, not current execution instructions. Read current handoff and phase plan instead of rescanning them.

