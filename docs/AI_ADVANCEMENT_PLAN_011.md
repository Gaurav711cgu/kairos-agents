# Kairos AI advancement — implementation and evidence plan

Date: 15 October 2026. Baseline: repair010 commit `69432bd`. This is a proposed next release; check receipts for completed work. Chat stays concise; this document preserves decisions and acceptance criteria.

## Objective

Improve source localization and repair decisions, then measure the result. Deliver a reproducible applied-AI workflow: reviewed defect → repository retrieval → source-bound candidate → independent checks → inspectable outcome. Training a model is a separate possible contribution, not a prerequisite for applied AI engineering.

The existing release already has an agent loop, real public SWE-bench-derived tasks, failure feedback, bounded edits and a full-stack workbench. New work must improve those mechanisms rather than duplicate them or claim success from a longer feature list. The audit's numeric hiring scores and interview guarantees are opinions, not acceptance evidence.

## Fixed resources

- Mac: Apple M2, eight CPU cores, 8 GiB RAM; measured on 15 October.
- Optional Lenovo: Windows, 8 GB RAM, RTX 3050 with 4 GB VRAM. It is not required for the first release.
- No new API spend, hardware purchase, public hosting or paid account changes. The user authorized planning free Kaggle/Colab GPU training on 15 October; local software and evidence remain usable independently.
- Existing local model files and signed-in Codex account may be reused. Account capacity is checked before a new experiment; an uncertain dispatch is never resent.
- Preserve the 6 GiB project-owned experiment storage ceiling and 4 GiB free-space reserve. Count dependencies, downloaded weights, indexes and receipts, including older experiment assets. New caches must not quietly evade accounting.
- Run indexing, inference and Docker verification sequentially. One investigation at a time. Stop owned heavy services after checks.

The initial audit found about 5.47 GB of existing counted assets, leaving about 930 MiB. This favors a small code encoder, exact local search and reusing source snapshots. Official full SWE-bench evaluation guidance recommends substantially more storage and memory; the full 300-case run is a resource-gated milestone, not a one-week promise. [Official Docker requirements](https://www.swebench.com/SWE-bench/guides/docker_setup/).

## Decisions

| Proposal | Decision and reason |
| --- | --- |
| RAG for source selection | Implement lexical, dense and hybrid retrieval over original source. Retain AST boundaries and existing edit authority. Measure retrieval before spending model calls. |
| CodeBERT by default | Trial the code-retrieval-trained CodeRankEmbed 137M instead. Its documented CLS pooling and query instruction are explicit. Pin revision, code and weights; do not assume arbitrary mean-pooling produces a good code retriever. [Model card](https://huggingface.co/nomic-ai/CodeRankEmbed). |
| FAISS or Chroma service | Use exact normalized inner product with NumPy first; offer FAISS's exact index when installed and measured. No vector database service is needed for this single-machine corpus. Report which backend actually ran. [FAISS metrics](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances). |
| Ten iterations | Add a new v8 configuration with ten model calls, four applied candidates, four checks and 900 seconds. Ten model calls are not ten full repair attempts. Preserve historical v1–v7 settings. |
| Chain-of-thought and self-reflection | Request concise hypotheses, source/test citations and next actions. Judge observable check feedback and edits; do not require or publish hidden reasoning or treat verbosity as evidence. |
| LoRA from 122 records | First audit distinct tasks and verified targets. Current 122 records cover 31 tasks; nine successful records reduce to two distinct Django tasks and three rendered patches. Two later post-hoc candidates add a pytest example, not 122 clean training triples. |
| Full SWE-bench Lite | Implement official-format prediction export and a blinded, declared subset workflow first. Run the official harness only when resource preflight passes. Never report a subset as a 300-case result. [Evaluation format and harness](https://www.swebench.com/SWE-bench/guides/evaluation/). |
| More concurrency | Preserve one active investigation on this hardware. Fix concrete process-safety issues before experimenting with workers. Async route syntax alone does not make synchronous database calls asynchronous. |

## Phase 1 — source retrieval and leakage control

1. Index only a pinned original-source snapshot beneath a registered source prefix. Exclude hidden verification, reference repairs, credentials, generated files and symlinks. Do not use maintainer patch paths or line ranges to seed candidate selection.
2. Parse Python functions/classes and bounded whole-line windows. Store repository revision, path, inclusive line range, source/file hashes and stable chunk ID. Keep full original chunks independently of embedding-input limits.
3. Compare lexical BM25, dense code embeddings and reciprocal-rank fusion. AST identifies source boundaries; it remains useful alongside learned retrieval.
4. Pin the CodeRankEmbed revision and dependency versions. Its custom source must be reviewed and hashed before local execution. Store a documented FP16 derivative if needed to fit disk; run CPU inference with explicit dtype and token limit. Treat this as a distinct measured encoder profile.
5. Save exact ranking, selected regions, encoding truncation/omissions, latency, index size and peak memory. A stale or corrupt index must fail, never silently serve another revision.
6. Retrieval results become the existing original-source handles before editing. Search results cannot bypass approved paths or digest/range validation.

Acceptance: malicious paths/links rejected; no hidden or reference material indexed; stale source detected; finite vectors and model identity validated; deterministic lexical ranking; exact cosine backend checked; a real encoder smoke and repository retrieval run produce receipts. A fixture encoder proves software behavior only.

## Phase 2 — bounded iterative repair

Introduce `baseline-v8` (one call, one candidate, one check, 600 seconds) and `loop-v8` (ten calls, four candidates/checks, 900 seconds). Coordinate contracts, API validation, database constraints, worker deadlines, provider limits and frozen configuration snapshots.

Retain immediate verification, full rejected-edit feedback, original-source handles, duplicate-candidate reuse, repeated-invalid stop, cancellation, fencing and explicit unknown dispatch. Search/read remain bounded; the agent receives no arbitrary shell. A new experimental worker injects retrieval observations and a semantic search action into the existing typed workflow.

Use the stronger authenticated provider with the exact requested model recorded. The earlier CLI-default candidate captures have no proven resolved model identifier; do not retroactively name them. Internal CLI retries remain distinct from harness invocation counts.

Replace threaded-parent `preexec_fn` output-limit setup with a fresh trusted process that establishes the limit before executing Docker. Keep actual output/timeout tests and container cleanup.

Acceptance: all old configurations retain their budgets; v8 cannot exceed any budget; deadline recovery uses the saved configuration; duplicate candidates spend no extra check; canceled/stale workers cannot commit; interrupted calls stay unknown; a real software integration journey uses PostgreSQL and Docker. A separate new model investigation is needed for a repair-performance claim.

## Phase 3 — fair retrieval and repair measurements

Create an exposure ledger before choosing cases. Include prior model attempts, qualification work, public captures and candidate selection. All 19 pytest and eight Requests tasks in the cached Verified dataset already appear in the broader exposure history. Do not promise fresh tasks from an exhausted pool.

Two explicitly different measurements:

- **Retrospective retrieval diagnostic:** reuse already exposed source snapshots to test indexing, latency and localization. Compare ranking against privately held changed-source paths/ranges as a proxy. This is not fresh repair validation, and maintainer edits are not the only valid solution.
- **Fresh evaluation:** select from pinned SWE-bench Lite metadata after cross-dataset ID exclusion, with a deterministic seed and predeclared repository/resource eligibility. If the requested repositories cannot supply cases, report the shortfall and freeze any revised repository choice before inference. Never replace cases based on model outcomes.

Target a small new cohort: eight development and sixteen held-out retrieval cases, balanced across two supported repositories if feasible. Require a reproduced failing baseline and successful reference verification before any case enters repair evaluation. Examine a bounded candidate list; retain every exclusion. A deterministic eight-case subset of the held-out cohort receives repair evaluation after all profiles are frozen.

Retrieval metrics: file Recall@1/5/10, reciprocal rank, changed-region overlap and complete region coverage, with per-case ranks, query latency, indexing time, storage and memory. Compare AST/lexical, dense and hybrid using the same source inventory and returned context budget. Report private patch-derived relevance as a proxy, including its incompleteness.

Freeze three repair arms before the first held-out run:

| Arm | Context | Budget | What the comparison tests |
| --- | --- | --- | --- |
| A | Existing AST/lexical selection without maintainer file hints | Six calls, two candidates/checks | Current mechanism on the same stronger model |
| B | Chosen retrieval profile | Six calls, two candidates/checks | Retrieval effect at the same budget |
| C | Same retrieval profile | Ten calls, four candidates/checks | Added iteration and compute effect |

Eight cases × three arms means at most 176 harness model invocations and 64 checks. Actual consumption, internal-provider retry uncertainty, unavailable tokens and infrastructure errors remain visible. Pause new work before quota exhaustion; preserve completed captures. Do not restart unknown dispatches.

Primary result is verified repairs per attempted case. Report intent-to-run totals, completed grading, invalid patches, infrastructure failures, timeouts and unknowns separately. Use paired outcome differences and descriptive uncertainty clustered by issue. Eight cases do not justify broad superiority, a production regression guarantee or the synthetic Hoeffding gate's assumptions. An operational target is at least one additional verified held-out case without worsening invalid-patch rate; the target is not a promised outcome or a reason to retune on evaluation cases.

Export `instance_id`, `model_name_or_path` and `model_patch` in the official format. A full Lite score requires accounting for all 300 instances under the declared official protocol. A custom sandbox subset must retain that name and scope.

## Phase 4 — model-level work, only with suitable data

Deliver a data-quality report now: distinct issues, repositories, successful patches, duplicates, licenses/provenance, exposure history and disjoint splits. Failed proposals may become labeled negatives; they are not successful supervised targets. Never train on held-out issue families or use their maintainer fixes as few-shot examples.

A small retrieval reranker or contrastive encoder adaptation is a more plausible first training study than a 7B repair model. Use independently separated issue/code relevance examples and hard negatives, compare with BM25 and the frozen encoder, and retain losses, seeds and held-out retrieval outcomes.

Use a free Kaggle GPU notebook first, with Colab as a fallback. Discover actual GPU/VRAM and runtime quota before selecting a training profile; checkpoint optimizer/RNG/adapter state for interruption. Pin datasets, model revision, libraries, seeds and training configuration. Upload only a reviewed public-data bundle; keep credentials and private runtime files out. Do not enable paid compute or bypass quotas. Free GPU type/availability is variable: [Kaggle notebooks](https://www.kaggle.com/docs/notebooks), [Colab FAQ](https://research.google.com/colaboratory/faq.html).

Repair LoRA remains conditional: qualify a substantially broader, deduplicated set of verified issue/context/patch examples; first prove that the training runtime, activations, optimizer and checkpoints fit measured RAM/VRAM/storage. GGUF inference files do not prove training feasibility. Standard QLoRA uses a supported quantized training backend with adapters; a 4 GB GPU does not automatically fit a 7B training job. [PEFT quantized training](https://huggingface.co/docs/peft/developer_guides/quantization), [QLoRA paper](https://arxiv.org/abs/2305.14314).

If training does not fit, preserve the resource receipt and deliver the retrieval/agent study. Do not buy hardware or substitute a toy training result for repair competence. Lenovo is optional for a measured small-model pilot after its actual runtime is prepared.

## Phase 5 — product and engineering presentation

Public visitor path: choose a captured issue → inspect retrieved source and selection method → read highlighted candidate changes → inspect independent checks → compare retrieval/iteration cost → download evidence. Show real outcomes and dated study scope. A context-selection graphic displays retrieved chunks, not transformer attention.

Private operator path: choose a reviewed registered task → validate its source/environment → choose a versioned profile → submit → inspect phases and budgets → cancel/fork/replay/download. Recorded mode provides evidence inspection; live commands require the prepared worker/provider. Never simulate live progress.

Add one concise comparison page using current muted design, accessible tables, keyboard controls and 390 px layouts. Link each claim to receipts. Every remaining gap gets cause, evidence, fix/next experiment, required resource and closure test in README/DECISIONS/BRAIN.

Engineering cleanup is evidence-driven: new Python modules get lint/type checks and focused property tests for source/range/index boundaries; avoid a repository-wide formatting churn. Measure coverage before choosing a gate. Add operational timings and failure counters without logging raw source or secrets. Existing pooling and Go build tests should not be described as absent. S3, horizontal workers, production alerts and adoption remain separate scope requiring an actual deployment/use case.

## Release acceptance and stop conditions

- Run focused retrieval, provider, budget, migration and process tests, then existing backend/frontend/recorded/real-OIDC acceptance.
- Run genuine encoder/index smoke; real database/container checks sequentially; no model inference in routine CI.
- Verify source isolation, downloads, private artifact exclusion and additive archive/manifests. Preserve build007–010.
- Record original failures and focused fixes. Retry only known-safe infrastructure work with new receipts; never silently replace model attempts.
- Release software when its acceptance passes. Record measured AI outcomes separately. No endless feature cycle triggered solely by a disappointing score.

Estimated implementation effort is a range, not a deadline: retrieval and safety 2–4 focused days, loop/integration 1–3, study qualification and presentation 2–4, plus measured compute and quota waits. Full Lite and training require their resource gates first. Work may complete sooner through reuse; no fixed one-week promise.

## Current external check

Repair010 was pushed as `69432bd`; both jobs in [GitHub run 38726663747](https://github.com/Gaurav711cgu/kairos-agents/actions/runs/38726663747) passed. New011 work starts on a separate branch and needs its own acceptance.

## Additional experiments covered by the roadmap

- **Model comparison:** compare the two existing local profiles and the explicitly selected stronger provider on development cases; freeze the selected profile before held-out evaluation. Record real hardware, availability, tokens and elapsed time. Do not multiply every evaluation arm by four models without a compute budget.
- **Prompt ablations:** compare concise evidence/next-action instructions, a separate review action, and disjoint few-shot examples at matched budgets. Examples must come from development/training issues, not the five exposed historical evaluation cases relabeled as a new holdout. Treat extra review calls as compute.
- **Confidence calibration:** capture an explicit probability before independent checks in a separately versioned experiment. Report Brier score, reliability bins with counts, abstentions and unavailable confidence; stratify by issue and model. A few outcomes cannot establish reliable confidence thresholds.
- **Attention inspection:** optional local-encoder hooks may capture actual attention weights while leaving outputs unchanged. Label the exact local encoder/layer/head/token alignment. Retrieval rankings are not attention, and black-box repair-provider attention is unavailable. Neither is an explanation of causal correctness.
- **Free generation comparison:** compare source-handle constrained actions with unconstrained generation under the same allowed paths and independent verifier. Parsing failures stay failures. Preserve the safety boundary for every arm; a grammar guarantees allowable syntax/handles, not correct program behavior.
