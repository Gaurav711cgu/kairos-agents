# F024 pilot plan (prepared offline; not executed)

Status: 22 October 2026. Approval is required before any upload, Colab session, model call or
Docker scoring. Everything below was exercised with mock responses only.
Receipts: `evidence/localization024/f024-pilot/`.

## Purpose

Verify the complete 14B pipeline end to end before any larger experiment: hash-bound package,
Colab journal, base and adapter arms, issue-only and diagnostic oracle context, local validation,
one bounded feedback turn, and independent Docker regression scoring. The pilot measures pipeline
correctness, not repair effectiveness; with 2 cases no rate is meaningful.

## Components

| Step | Where | Code | Tested offline |
|---|---|---|---|
| Turn-one package (frozen023 issue-only context, oracle context, base and adapter pairs) | Mac | `scripts/f024.py:build_pilot`, `make_job` | yes; real package built (8 jobs) |
| Package rules: pinned model, pairing, protocol shape, envelope | Mac and Colab | `scripts/f024_colab.py:validate_package` | yes |
| Journal: intent, hashed capture, halt on error, stop on uncertainty | Colab | `scripts/f024_colab.py:run_jobs` | yes (mock generate) |
| Re-render every prompt and check its token digest and envelope before the model loads | Colab | `run_gpu` | GPU path not executable offline |
| Local validation, outcome classes, turn-two planning | Mac | `scripts/f024.py:turn2`, `scripts/feedback_turn021.py` | yes; full mock dry run on the real package |
| Regression scoring of accepted edits | Mac, Docker | existing qualification and scorer path | Docker+PostgreSQL integration 9/9; F024 scoring itself not run |

## Generation ledger (all counts are maximums unless marked)

| Run | Cases | Contexts | Arms | Turn one | Turn two at most | Maximum total |
|---|---|---|---|---|---|---|
| **Pilot (recommended first)** | 2 (1 django, 1 pytest) | issue, oracle | base, adapter | 8 | 8 | **16** |
| F024 base only, policy P2 | 30 in scope | issue 28, oracle 29 | base | 57 | 43 | 100 |
| F024 base and adapter, policy P2 | 30 in scope | issue 28, oracle 29 | base, adapter | 114 | 86 | 200 |

Turn two exists only for a rejected turn one that fits the envelope; there is never a third turn,
and nothing is retried after a generation error or an uncertain dispatch. The pilot mock dry run
planned 5 turn-two jobs (13 total); real counts depend on model outputs.

## Resources and cost exposure

- Model and adapter: pinned base `unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit@ecfc63c0`, downloaded
  inside Colab (about 9 GB, no local download); adapter training5 checkpoint 80 (25 MB, hash-bound).
- Uploads requiring approval: pilot package, `scripts/` runner modules, adapter binding and files,
  model manifest, notebook.
- GPU: free Colab T4 (14.6 GiB). Historical peak 14.42 GiB at at most 3539 tokens in+out; every
  pilot job is at most 1359 + 512 = 1871 tokens. Expected 16 x 34 s (about 9 minutes) plus model
  load; hard maximum 16 x 180 s plus load. Two sessions: turn one, then turn two after local validation.
- Money: $0 on the free tier; the risk is quota or GPU unavailability, which stops the run without
  partial reruns.
- Docker: local scoring only, with pinned images already on disk (no pulls).

## Stop conditions

- Package, runner or adapter hash differs: refuse before the model loads.
- Any prompt re-render digest differs or exceeds the envelope: refuse before the model loads.
- Dependency profile or GPU memory below 14 GiB: refuse.
- Any generation error (CUDA out of memory included): captured, run halted, never retried.
- An intent without a capture (uncertain dispatch): no further dispatch.
- Turn two: only for parser or validator rejections; one turn at most; refused if over the envelope.

## Pilot pass criteria (pipeline, not effectiveness)

All 8 turn-one jobs captured; 0 uncertain dispatches; Colab re-render digests equal the package;
every capture classified locally; turn-two package valid; peak reserved memory recorded below the
GPU total; accepted edits scored by Docker with complete receipts. Any failure is a pipeline
finding, fixed offline before F024.

## What evidence would justify training versus retrieval or feedback work

- **Retrieval is the bottleneck** if the oracle arm repairs clearly more often than issue-only.
  Then improve hunk-level context; training cannot fix missing lines.
- **Feedback is the lever** if turn two converts many parser or validator rejections into valid
  edits. Then wire feedback into production before any training.
- **Training is justified only if** the oracle arm, with feedback, still fails mostly on protocol
  format (indentation, coordinates, schema) rather than wrong fixes, and the adapter does not
  close that gap. Then train on diverse verified source-handle edits split by repository family,
  including feedback-correction turns, and judge by independent regression tests on a fresh,
  project-excluded cohort. Training loss and training-case wins never count.
- **Model capability is the limit** if the oracle arm produces valid but behaviourally wrong
  edits. Then a larger or different model, not more of this training data, is the question.
