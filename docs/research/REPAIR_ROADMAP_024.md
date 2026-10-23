# Repair roadmap 024: what blocks successful repairs

Status: 22 October 2026. Development evidence only; validation frozen, holdout never fetched.
Receipts: `evidence/localization024/{h1,h2,h3,patch-roundtrip}/MANIFEST.json`.

## Established evidence

| Stage | Measurement (development, 36 cases) | Source |
|---|---|---|
| Target file in final context | v3 14, H3 23 | h3/dev.json |
| Complete gold hunks in final context | v3 3, H1/H2 5, H3 8 | h3/dev.json |
| Beyond 2-file/40-line edit scope | 6 | h3/dev.json |
| Known gold patch applies cleanly (in scope) | 34/34 | patch-roundtrip/dev.json |
| Gold edit through source-handle protocol, pipeline faults | 0 | patch-roundtrip/dev.json |
| H3 remaining: file in context, hunk missing / file absent | 13 / 9 | h3/dev.json |

Historical exposed cohort (unseen023, aggregate only): base 0/20, adapter 0/20 verified repairs;
27 invalid patches, all from single-shot generation with no feedback turn. Of 27 syntax-rejected
edits, 17 shift first-line indentation against the original start line, 9 end on a block opener.
Training5 learned its 2 training cases (2/2); no held-out gain was shown.

Validation, one frozen run each: H1 final-context recall 16 to 20/32 (5/1, p=0.22) and recall@1
13 to 9. H3 final-context recall 16 to 20/32, recall@1 13 = 13, but complete-hunk containment
**6 to 3/32 (0 gains/3 losses)**. The development containment gain (3 to 8/36) did not generalize.
Localization changes improve file-level recall only; they are not validated improvements for
repair-relevant context.

## What is preventing repairs (ranked by evidence)

1. **Missing editable context.** Only 8/30 in-scope development cases expose every edited hunk.
   A model cannot emit a valid source-handle edit for lines it never sees. This bounds any
   model, base or adapter.
2. **Single-shot generation.** Every historical invalid patch was final. The validator already
   produces precise rejections and `scripts/repair010/feedback010.py` already renders exact
   indentation and coordinate feedback, but the 021 protocol never used it.
3. **Model capability with sufficient context: unknown.** No experiment has given the model
   complete hunks and measured repairs. This is the largest open question.
4. **Edit scope.** 6/36 development fixes exceed 2 files/40 lines. Expanding scope is not
   justified until in-scope repairs succeed.
5. **Edit pipeline.** Not a bottleneck: 0 faults on known-correct edits.

## Recommendation, ranked by expected value

1. **Engineering, deterministic (do now, no approval):** keep improving hunk-level context on
   development only: module-level hunks (imports, class attributes) and the 13
   file-present/hunk-missing cases. Stop after two more non-improving iterations.
2. **Feedback-based inference (needs approval):** decisive and cheap; see the proposal below.
3. **Training (not justified now):** no evidence supports it. Justify only if the oracle-context
   experiment shows the model fails *with* complete hunks *and* one feedback turn, and the
   failures are protocol-format errors (indentation, coordinates) rather than wrong fixes. Then
   train on diverse verified source-handle edits split by repository family and patch target,
   with feedback-correction turns, scored by independent regression tests on a fresh cohort.

## Proposed experiment F024 (approval required, not executed)

Purpose: separate retrieval, model and feedback limits on development cases.

Constraint found on inspection: the two model paths are not interchangeable.

| Path | Model | Protocol | Feedback |
|---|---|---|---|
| 021 single shot (unseen023) | pinned 14B, Colab T4 only (4-bit CUDA profile) | JSON source-handle edits | none implemented |
| Worker `-v8` (`kairos_api` worker) | Qwen3-1.7B Q8 GGUF, llama.cpp loopback on this Mac | line-handle actions | `feedback010` |

`feedback010` cannot be used with the 14B without new 021-protocol feedback code. Running the
worker path instead would silently substitute a smaller model. Choose one explicitly:

- **F024-A (14B, Colab, closest to historical results):** uses `scripts/feedback_turn021.py`
  (offline-tested with mocked generations; nothing enabled). Turn one is the unchanged 021 prompt.
  Captures are validated on the Mac with the scorer's own parser and validator (no Docker). Only a
  validator rejection earns one turn two; its prompt is the turn-one payload plus
  `rejection_feedback010`. Turn two is a second Colab session.
  - Memory constraint: historical T4 peak was 14.42 of 14.6 GiB at at most 3539 input+output
    tokens. Turn two must stay inside that observed envelope or fail closed. With a 512-token
    turn-two output cap and about 500 feedback tokens, 21 of 30 in-scope development cases fit
    (16 of 30 at a 1024 cap). The real limit is unmeasured.
  - Issue-only arm uses **frozen023**, not H3. H3's single frozen validation run showed lower
    complete-hunk containment than frozen023 (3/32 versus 6/32); see
    `evidence/localization024/validation-h3`.
  - Measured on cached development sources (`scripts/f024.py`, `scripts/oracle_context024.py`):
    of 30 in-scope cases, the issue-only arm builds 30 prompts (maximum 3060 tokens) and the oracle
    arm builds 29 (1 needs more than 4 regions; maximum 2670 tokens).
  - Memory preflight (`scripts/f024.py`): prompt + max_new_tokens must not exceed 3539, the
    largest input+output ever observed on the T4 (14.42 of 14.6 GiB peak). A CUDA out-of-memory
    error at run time is a captured generation error that halts the arm; it is never retried.

    | Policy | Turn-one output cap | Issue-only turn one | Oracle turn one | Turn two at most (500-token feedback, 512 output) | Maximum generations |
    |---|---|---|---|---|---|
    | P1 historical cap | 1024 | 16 (14 refused) | 28 | 15 + 28 | 87 |
    | P2 recommended | 512 | 28 | 29 | 15 + 28 | **100** |

    P2 keeps more of the issue-only arm, but any turn-one output longer than 512 tokens is
    truncated and counted invalid; historically 4/40 outputs exceeded 504 tokens. It is base model
    only. Expected turn-two count is about 26 if the historical 12/20 invalid rate holds (an
    estimate), so about 83 generations. Runtime: mean 33.8 s and hard deadline 180 s per
    generation give about 47 minutes expected and at most 5 hours, plus model load, in 2 Colab
    sessions (turn one, then turn two after local validation). Docker scoring follows, using
    pinned images already present locally.
  - Runner, notebook and a 16-generation pilot are prepared and mock-tested; see
    `docs/research/F024_PILOT_PLAN.md`. Run the pilot before this experiment.
- **F024-B (1.7B, local, zero cost):** the same cases through the worker. `baseline-v8` = 1 call,
  1 patch, 1 check. Existing `loop-v8` = up to 10 calls, 4 patches, 4 checks, 900 s per case,
  so up to 300 calls per arm. A bounded 2-call feedback configuration would need a new
  configuration identity. Results would not transfer to the 14B.

Common to both:
- Scoring: parse-valid, syntax-valid, clean apply, then regression tests in the pinned
  per-repository images. That needs Docker, which is also approval-gated. Repair is reported
  separately from validity.
- Interpretation: oracle near 0 means model capability dominates; oracle much higher than
  issue-only means context dominates; feedback gain is measured only on rejected first turns.
- Stop: no second turn without a rejection; never redispatch an uncertain capture; halt the arm
  on any generation error; stop after the budget even if incomplete.

## Readiness for independent evaluation

Freeze selector and protocol on development; run validation once; require positive verified
repairs on development with complete receipts; then admit a fresh, project-excluded cohort.
Localization or validity gains alone are not readiness.
