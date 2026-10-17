# Kairos brain — current checkpoint

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
- Manifest `evidence/measurement014/manifest.json` sealed across 573 measurement delta files against parent `32c21a9c189b46d755cf4cc9d8149a2ee41371fc`.
- `scripts.verify_measurement014` passed: verified metric arithmetic, selected-head resume bitwise equality, frozen candidate cohort preservation (24 candidates), and 113 training queries.
- Ancestral release verifiers verified against git archive snapshots: `verify_repair010`, `verify_retrieval011`, `verify_loop012`, `verify_evaluation013` all PASSED.
- Full backend suite (`.venv/bin/python -m scripts.acceptance007 backend`): 1,044 passed, 141 optional skips, 16 subtests in 25.54s with 0 failures.
- 014 focused suite: 241 passed, 3 skipped, 5 subtests in 16.25s with 0 failures.
- Gravitas criteria AC-001, AC-002, AC-003, AC-004, AC-005 ALL PASSED.

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

