# Retrieval011 — Phase 1

## Outcome

The repository now has a local retrieval layer for source context: AST-bound chunks, BM25, real CodeRankEmbed embeddings, exact FAISS search and reciprocal-rank fusion. `search_codebase` returns the existing original-source handles; it does not grant new edit authority. This phase exposes a local build/query API and CLI. Worker and website integration belong to later phases.

The pretrained encoder is `nomic-ai/CodeRankEmbed` at revision `3c4b60807d71f79b43f3c4363786d9493691f8b1`. Its reviewed custom code, tokenizer and original weights are pinned. A documented FP16 storage conversion is expanded to FP32 for CPU inference, with CLS pooling, query-only instruction, 512-token encoding limit and two CPU threads. Original chunks remain exact even when the encoder omits trailing tokens; per-input offsets/counts are captured. The 512-token profile is a measured resource choice, not the model's full advertised capacity. [Official model](https://huggingface.co/nomic-ai/CodeRankEmbed).

## Actual experiment

One previously exposed pytest issue, `pytest-dev__pytest-6197`, was queried against its original revision `e856638ba086fcf5bebf1bebea32d5cf78de87b4`. The index covers all 55 eligible files and 1,652 regions beneath `src/_pytest/`. Ranking uses the issue and source only. No maintainer entry files, patch paths, changed lines, hidden verification or candidate source were supplied. Reference-derived labels were read afterward by the offline scorer.

| Method | Maintainer-changed file within returned regions | Scope |
| --- | --- | --- |
| Existing AST selection, entry hints removed | Missed in its four returned regions | Actual existing heuristic; no fallback from maintainer paths |
| BM25 | Missed in top ten | Same source index |
| Dense code embeddings | First hit at rank five | MRR 0.2 for this one issue |
| Hybrid fusion | First hit at rank six | Not better than dense on this diagnostic |

At an equal four-region budget, every method missed the changed file. Dense top-five/top-ten coverage is an observation, not proof that replacing four AST regions improves the repair loop. Only one of four maintainer changed-region groups appeared in the top ten. The reference diff is an incomplete localization proxy; other valid repairs may edit elsewhere.

The original index build took **145.557 seconds**, excluding model initialization. Queries took **0.217 seconds lexical, 0.379 seconds dense and 0.432 seconds hybrid** in that captured process. These are single measurements rather than latency percentiles. Query-process peak RSS was **992,329,728 bytes** on macOS. FAISS control-process peak RSS was **1,142,980,608 bytes**. The exact FAISS and NumPy top-ten rankings agreed; ten selected regions were re-read through actual source-handle capture. Reusing the saved vectors to prepare the FAISS profile took 0.260 seconds. CPU-only; Docker and repair-model calls were off. The diagnostic JSON counter `model_calls: 0` refers to repair-generation calls; pretrained embedding inference did occur.

Receipts: [index](../evidence/retrieval011/index-build.json), [rankings](../evidence/retrieval011/ranking-diagnostic.json), [FAISS/AST controls](../evidence/retrieval011/controls.json). This is a retrospective localization diagnostic, not a new repair result or evidence of broad retrieval superiority.

## Reproduce

Use a separate Python 3.12 environment for optional ML dependencies. The existing API environment is unchanged. On Linux install the official CPU-only PyTorch wheel; do not accidentally download the CUDA dependency stack for this CPU profile.

```bash
python3.12 -m venv .venv-retrieval
.venv-retrieval/bin/python -m pip install -r requirements-retrieval011.lock
mkdir -p .runtime/retrieval011
.venv-retrieval/bin/python -m scripts.prepare_retrieval011 \
  --encoder-dir .runtime/retrieval011/encoder \
  --budget-root .runtime/retrieval011
```

Declare **every owned experiment root**, including existing model caches, with repeated `--budget-root` flags. The command de-duplicates nested roots and enforces 6 GiB owned storage and 4 GiB free reserve. Downloaded FP32 weights are hashed in bounded memory; only the smaller documented derivative persists. A pinned serialization header reproduces its exact bytes. Existing prepared files are verified and reused without network access. Incomplete/corrupt preparations are refused rather than overwritten.

Prepare a reviewed original source snapshot at its declared commit, then run:

```bash
.venv-retrieval/bin/python -m scripts.retrieval011 build \
  --source-root /path/to/original/source --approved-prefix package/ \
  --revision FULL_SOURCE_COMMIT --index-root .runtime/retrieval011/indexes \
  --mode hybrid --exact-backend faiss --profile profiles/coderank011.json \
  --encoder-dir .runtime/retrieval011/encoder --budget-root .runtime/retrieval011 \
  --output .runtime/retrieval011/build.json

.venv-retrieval/bin/python -m scripts.retrieval011 query \
  --source-root /path/to/original/source --approved-prefix package/ \
  --revision FULL_SOURCE_COMMIT --index-root .runtime/retrieval011/indexes \
  --index-id INDEX_ID_FROM_BUILD --mode hybrid --query "Describe the defect" --limit 5 \
  --profile profiles/coderank011.json --encoder-dir .runtime/retrieval011/encoder \
  --budget-root .runtime/retrieval011
```

Indexes store checked JSON and non-pickle arrays. FAISS reconstructs `IndexFlatIP` from validated saved vectors in a fresh process, avoiding native-index deserialization and the observed PyTorch/OpenMP conflict. Missing FAISS or encoder state fails explicitly; no fabricated semantic fallback is used. [FAISS distance semantics](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances).

## Owned failures and next tests

| Finding | Cause and delivered action | Closure test |
| --- | --- | --- |
| Initial FAISS process aborted | Two native OpenMP runtimes; isolated FAISS without the unsafe duplicate-runtime override | Exact backend agreement and bounded child-process/malformed-array tests |
| All methods miss under four-region cap | Relevant file ranked below four on this issue | Precommit a context/token budget and evaluate more unseen issues; do not claim top-ten recall at a four-region deployment budget |
| Embedding input can exceed 512 tokens | Bounded CPU/memory profile | Record every truncation; compare a larger limit only on development cases before freezing |
| No fresh repair score from retrieval | This phase measures localization only | Later worker integration and independent held-out repair evaluation |
| LoRA data too small as claimed | 122 records reduce to 31 tasks; successful trajectories cover two distinct Django tasks | Deduplicate and qualify disjoint training examples; prepare a free cloud GPU notebook with actual runtime/VRAM checks |

The broader [advancement plan](AI_ADVANCEMENT_PLAN_011.md) includes free Kaggle/Colab training, prompt/model ablations, confidence calibration and optional real local-encoder attention. No cloud upload or training has occurred in Phase 1. Full SWE-bench Lite still requires an official-harness resource check; a subset must not be labeled a 300-case evaluation. Two successes out of 300 would be 0.67%, not 2–5%.

## Acceptance and preservation

`evidence/retrieval011/acceptance.json` records actual test invocations and skips. This phase changes no API, auth, database schema, worker budget or published historical outcome. Existing seals are preserved; CI runs the original repair010 verifier against its exact Git snapshot and separately verifies the current retrieval overlay. We retain the initial native failure and the measured nulls.
