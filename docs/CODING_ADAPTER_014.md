> Current result: training completed (100 supervision examples, 40 optimizer updates). The separate completed same-base repair comparison found 0/9 repairs in each arm, with three cases unavailable. No improvement is claimed. [Final evaluation](research/ADAPTER_EVALUATION_020.md). Earlier unstarted/pending notes below are preserved historical planning checkpoints.

# Current status correction — 20 October 2026

Real 14B adapter training has completed: 100 public supervision rows and 40 optimizer updates, with 58 result-manifest files verified. Independent repair-effectiveness evaluation remains open; only two qualification captures were admitted. See [the closeout report](CLOSEOUT_020.md) for distinctions between training, development generation, retrieval diagnostics and repair success. The historical plan below is retained, including its original constraints.

---

# Coding-model adapter: bounded improvement plan

Status: next backend/training priority after real-service verification. Coding-model fitting and training-data upload have not started. One explicitly approved read-only Colab inventory used an available T4, then deleted the owned runtime and signed out. The completed 24,576-parameter retrieval-head experiment remains separate. The old three-family repair-data audit predates the current fresh study; refresh the inventory after that study finishes, but reserve every current evaluation case from future training.

## Decision and intended benefit

Test whether supervised adapter training improves a small open coding model's independently verified repairs and valid source edits. Do not train merely to add a résumé keyword. The existing strong-model investigation system remains usable regardless of the adapter result. This follow-up does not reopen the current frozen study or block its delivery.

The initial proposal used official `Qwen/Qwen2.5-Coder-1.5B-Instruct` for conservative resource testing. After the user requested a stronger primary model, target the 7B coding model below and retain 1.5B as a baseline/resource smoke profile. Select using measured resource fit and development repairs, not parameter count alone. This is a new candidate; it is not the current remote coding model, the existing 3B GGUF profile, or a guaranteed improvement. Compare it against the exact same 1.5B base revision. Never train proprietary CLI models or claim that an adapter modifies them.

## Gate1: refresh and qualify training data

1. Inventory all existing attempts, distinct task families, source revisions, patches and check receipts. Preserve earlier audit snapshots. Current development evidence can inform failure taxonomy; all current 24 frozen cohort IDs and their issue families remain excluded from this adapter's training and model selection.
2. Begin with the official SWE-Gym real-issue collection, which currently lists 2,438 instances from 11 Python repositories. Pin dataset revision, row hashes, upstream commits and licenses before intake. The dataset's MIT label does not replace upstream repository license review.
3. Examine at most 500 candidate issues in deterministic ID order. Target 200 independently verified training repairs spanning at least five repositories; cap any repository at 25%. This is a project admission threshold, not a universal statistical law. If qualification falls short, publish the shortfall and do not silently lower the gate or duplicate rows.
4. Independently reproduce baseline regression failure and reference-repair success under the registered sandbox. Keep every exclusion, dependency issue and incomplete test run. A dataset's `resolved` flag or a plausible patch is not sufficient evidence.
5. Deduplicate by issue/PR family, source revision, normalized patch and near-duplicate code regions. Split entire issue families and repositories before making examples. Keep model evaluation repositories out of training and development.
6. Convert accepted reference repairs mechanically into the actual Kairos source-handle/line-range edit schema. Require exact source digests, valid bounds, protected-path rejection, successful replay and syntax validation. Reject ambiguous conversions instead of using another model to invent labels.
7. Inputs contain public issue text and original source. Targets contain the verified edit action. Hidden tests, reference answers in the prompt, test output showing the target fix, credentials and private traces must not enter inputs. Loss applies only to assistant target tokens. Reference-derived supervision is labeled as such; it is not claimed as agent-generated training data.
8. Freeze tokenized input/output hashes and an exclusion ledger. Admit only complete examples fitting the pilot's sequence bound; do not truncate serialized JSON or cut off target edits.

SWE-smith is a secondary, separately labeled candidate for synthetic repair data. Its trajectory dataset contains both resolved and unresolved rows and large traces. Do not download its entire multi-GB payload or mix it into the real-issue pilot without a new data revision, provenance review and independent verification. Generated benchmark defects must remain distinguishable from historical real issues.

## Gate2: freeze development and untouched evaluation

Qualify six development cases and 30 evaluation cases before adapter fitting. Evaluation targets small Python source repairs in `psf/requests` and `sympy/sympy`,15 per repository; exclude both repositories from training and development. Exclude every previously attempted/reserved task and near-duplicate issue family across all Kairos releases. Public upstream history remains potentially present in the base model's pretraining; this split does not prove it was unseen by the base.

Examine at most 60 fresh evaluation candidates in deterministic ID order. Eligibility: at most two Python source files and 40 changed reference lines; reviewed dependencies;1 GiB verification memory;120-second checks; complete original-source context fitting the frozen model input. Reproduce baseline failures and reference repairs before generation. Record shortfalls without selecting by model success.

The first pilot measures **single-call structured patch generation**, not a trained autonomous tool-use policy. This makes cloud batch inference compatible with local independent verification without hosting a model endpoint. Adaptive-loop integration is a later measured deployment gate, not implied by a successful one-shot pilot.

Run the unmodified base on the six development cases first. Classify localization omissions, invalid actions, wrong edits and infrastructure failures. If missing context dominates, fix and freeze context selection before training; do not pretend gradient updates replace unavailable evidence. Development is the only place to make that decision.

## Gate3: free-GPU fit and reproducible training

Use the native notebook UI and an available NVIDIA GPU. Do not create a public inference service, purchase credits, bypass Colab limits or make Lenovo a dependency. Colab explicitly does not guarantee GPU type, capacity or session duration.

Proposed starting profile, frozen only after the measured fit pilot:

| Setting | Initial candidate |
| --- | --- |
| Base | Official Qwen2.5-Coder-1.5B-Instruct, exact commit/tokenizer/weight hashes |
| Quantization | bitsandbytes 4-bit NF4 with double quantization |
| Adapter | LoRA rank 8, alpha 16, dropout 0.05, q_proj/v_proj only |
| Precision | FP16 on a T4; use a separately recorded compatible setting on another GPU |
| Sequence | 2,048 total training tokens; complete action targets |
| Batch | Microbatch 1, accumulation 8, gradient checkpointing |
| Learning rate | At most two development candidates: 0.0001 and 0.00005 |
| Budget | One epoch, at most 500 optimizer steps per candidate; no evaluation-driven extension |
| State | Adapter, optimizer, scheduler, sampler position and Python/NumPy/Torch RNG |

First run 20 forward/backward steps and record actual peak allocated/reserved VRAM, CPU RAM, scratch disk, throughput, finite loss and nonzero adapter gradients. Require at least 15% measured VRAM headroom. Do not claim the full base was trained: QLoRA keeps base weights frozen and updates adapters. Do not silently substitute a smaller model after an out-of-memory failure.

Checkpoint periodically and test a real interruption/resume before the full fit. Pin CUDA, driver, Torch, Transformers, PEFT, TRL and bitsandbytes versions. Record determinism settings. Resume equivalence must be tested in the same recorded environment; do not promise bitwise equality across GPU architectures.

**Storage is an admission gate.** Keep the existing Mac 6 GiB aggregate experiment guard, 4 GiB free-space reserve and every preserved model/image. Record all cloud weights, caches and checkpoints separately as owned temporary usage; do not hide copies by moving them. Cloud scratch needs its own explicit bounded allocation before download. If the original global 6 GiB ceiling must include both machines and cannot accommodate the base, leave training unstarted until it fits or that temporary allocation is explicitly revised. No spending or deletion of preserved assets is implied by this plan.

Upload only the reviewed public training/development package. Export only the adapter, hash manifest, training logs and safe checkpoint state needed for resume. No Google Drive mount, private repository upload or authentication export is required by the experiment.

## Gate4: compare base and adapter fairly

Freeze the chosen adapter using development evidence only. Run both models once on all 30 untouched evaluation cases, with identical input text, source handles, tokenizer, context/output bounds, decoding, seed, quantized base and generation code. Record the adapter's actual trainable parameter count. Do not compare this result directly with the current remote model's score as a controlled model comparison.

Use offline cloud batch generation through the notebook. Evaluation uploads contain only public issue/source prompts, not reference patches or hidden tests. Generate one candidate per case for each condition, save every response before checking outcomes, then download a bounded response package. Execute all independent checks on the Mac, one at a time. This requires no public model server or live connection between Colab and the Mac.

Keep every invalid response, missing output, timeout, cancelled session and infrastructure failure. Never repeat an uncertain generation automatically. Define a frozen interruption policy and paired coverage before starting; an incomplete paired study is reported as incomplete. Do not fill missing adapter outcomes with base outputs or select the best of multiple generations.

Primary metric: verified repairs out of 30 predeclared cases, with denominators intact. Report base-only wins, adapter-only wins, ties and failures by repository. Secondary metrics: valid edit rate, syntax acceptance, preserved existing tests, input/output tokens, wall time and measured memory. A lower training loss or cleaner JSON alone is not improved repair effectiveness.

Publish paired repair-rate differences and a descriptive 95% interval. Related public cases and small repository coverage limit generalization. No optional stopping or retuning on the final evaluation.

## Gate5: promote only an earned result

Predeclare before evaluation:

- Practical target: at least three additional verified repairs out of 30, with no repository performing worse than its base result.
- Default-promotion evidence: paired 95% repair-rate difference lower bound above zero, complete paired measurements, no verifier bypass or increase in incomplete verification, and passing deployment/recovery checks.
- If the practical target passes but uncertainty includes zero, retain the adapter as an experimental profile and describe its measured result narrowly.
- If repairs do not improve, retain the base default and publish the unsuccessful adapter. Diagnose the recorded failure classes; do not extend training or change cases after seeing evaluation.

Before any default change, test the real inference runtime, output-schema support, cancellation, unknown dispatch recovery, artifact integrity and a small newly frozen loop integration suite. If exporting or merging/quantizing the adapter changes inference bytes, disclose the transformation and re-evaluate that deployment profile. A cloud Transformers result does not automatically establish a Mac GGUF result.

## Deliverables and bounded effort

Deliver a dataset card, full exclusion/family ledger, frozen configuration, training notebook, measured resource-fit receipt, resume test, adapter card, complete base-versus-adapter outcomes and a website comparison. Add an explicit claim-to-receipt table. The initial follow-up allows one data freeze, one resource pilot and at most two development training profiles, then one final evaluation. A failure produces a documented result rather than an endless feature cycle.

Estimated effort: 5–10 focused working days plus variable free-GPU waiting time. Data qualification is likely the largest component; GPU training time is measured during the 20-step fit pilot. This is separate from the current measurement014 release ETA.

## Primary sources checked 16 October 2026

- [Official SWE-Gym dataset](https://huggingface.co/datasets/SWE-Gym/SWE-Gym): real-issue collection and dataset license.
- [Official SWE-Gym implementation](https://github.com/SWE-Gym/SWE-Gym): environment and training workflow.
- [Official SWE-smith trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories): source, resolved flags, synthetic origin and size.
- [Official Qwen 1.5B coding model](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct): model identity and Apache2.0 license.
- [Hugging Face PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization): supported 4-bit adapter training mechanics.
- [Google Colab FAQ](https://research.google.com/colaboratory/faq.html): variable free-resource availability and native notebook constraints.


## Checkpoint after backend verification

On16 October2026, real-service backend acceptance passed1,014 tests and16 subtests; separate CPU ML mechanics passed39 tests and six subtests. The saved Django14752 repair reproduced against19 tests without new inference. Coding-model fitting remains unstarted. The refreshed exposure audit contains180 records and15 verified task IDs, but admits zero new training tasks from the reserved014 cohort. Next collect and independently verify separate supervision; then run the free-GPU fit and resume pilot before either training profile. Current account allowance constrains orchestration, not evidence standards. Preserve completed receipts and avoid restarting experiments.


## Intake update

The pinned SWE-Gym dataset has now been acquired and statically screened. Exactly 500 candidates across six repositories are pending qualification. No training repairs are admitted from this intake yet. Exact acquisition, exclusions, license samples, the first source-preparation receipt and the resource notebook are described in [Coding data checkpoint](CODING_DATA_014.md). The explicitly approved inventory notebook ran on a Tesla T4 (15,360 MiB VRAM), then its runtime was deleted, notebook moved to the recoverable bin, and account signed out/removed from the chooser. No training data or model weights were uploaded. Coding-model fitting remains unstarted; resource-fit, corpus and bounded scratch gates remain. See the linked preflight receipt for exact environment and cleanup limits.

## Primary model revision: target 7B, measure before fitting

The primary training candidate is now Qwen2.5-Coder-7B-Instruct, with the1.5B proposal retained as historical baseline/resource smoke. This is an engineering choice for the focused repair study, not a universal industry minimum or an achieved effectiveness claim.

- Official upstream: `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, Apache2. Four BF16 weight shards total15,231,271,864bytes.
- Resource candidate: `unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit`, revision `4858886f896bd05db823557fc5cbc4ac28342af7`, Apache2 metadata. Its single prequantized weight file is5,547,254,632bytes. This is a third-party quantized derivative, not an independently reproduced conversion from the current official revision. Use the same exact quantized bytes in base and adapter arms.
- Metadata, file sizes and available LFS hashes are captured under coding-data/model-candidates. No weights were downloaded and no T4 fitting result exists.
- Keep source, tokenizer, quantization, LoRA targets, package versions, context and optimizer configuration frozen before the20-step fit/resume pilot. Measure peak VRAM and require15%headroom. Never silently shrink the model or shorten complete action targets to pass.
- Existing Mac aggregate storage limits remain unchanged. A reviewed bounded cloud scratch admission is still required before downloading any candidate. No metadata lookup authorizes deleting preserved assets or hiding copied weights.

The broader corpus, independent checks, clean splits and frozen base-versus-adapter evaluation remain required. A larger base does not repair missing source context or incomplete supervision.

Sources checked16October2026: [official7B card](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct), [pinned derivative](https://huggingface.co/unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit), [PEFT quantized-adapter training](https://huggingface.co/docs/peft/developer_guides/quantization).

## Larger-model and provider policy

The user authorized considering a larger model and another free provider if Colab cannot support the intended work.7B is the first primary candidate, not a ceiling. Add exactly one larger candidate before model selection: Qwen2.5-Coder14B. Preserve1.5B as a baseline/resource smoke; do not turn it into an additional full-training search. Select between resource-qualified7B/14B using development verified repairs, invalid-action rate and elapsed time. Freeze the selected model before the two allowed training profiles and untouched evaluation. More parameters alone do not earn promotion.

Official14B revision `aedcc2d42b622764e023cf882b6652e646b95671` has29,540,133,960weight bytes. The separate Unsloth NF4 derivative revision `ecfc63c083900ce4f19daad695e711f38ab98fcf` has9,932,337,343weight bytes. Both metadata snapshots list Apache2. No weights were downloaded and no runtime fit has been established. Use the same exact derivative in base/adapter arms; its transformation provenance is not independently reproduced here.

Use Colab free capacity first, then an eligible Kaggle free GPU if actually available. Do not buy credits, add hosting, train a large model on the8GiB Mac or evade provider limits. Colab documents that free GPU type, availability and duration vary. A second GPU does not automatically double per-device memory; any distributed setup requires its own measured recipe. No new login is needed while the corpus and training runner are incomplete.

Before downloading, admit a bounded cloud scratch allocation that counts weights, caches, checkpoints and duplicate copies. The resource policy proposes a20GiB temporary cloud ceiling with actual capacity checked at execution; this proposal has not admitted any download or changed the6GiB Mac guard. Run the same20-step training/15%VRAM-headroom/resume gate for either model. Record unavailable resources and failed fits. Do not change model/provider within an uncertain dispatch or use held-out scores to choose a larger model.

Machine-readable policy: `evidence/measurement014/coding-data/model-candidates/resource-policy-v1.json`. Provider sources: [Colab FAQ](https://research.google.com/colaboratory/faq.html), [Kaggle notebooks documentation](https://www.kaggle.com/docs/notebooks).
