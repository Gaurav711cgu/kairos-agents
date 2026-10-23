# Training and inference alignment audit — 20 October 2026

## Scope and outcome

Read-only audit of the actual full100 input ZIP, original pinned SWE-Gym Parquet, captured training receipts, canonical training/admission code, frozen evaluation020 prompts and final report. No training, inference, source reconstruction or Docker execution was performed. Frozen artifacts were not modified.

**The immediate defect is invalid supervision admission, not demonstrated GPU insufficiency.** Only **66 of 100 training targets** and **7 of 10 development targets** reproduce the complete reference transformation. All 110 rows parse; the remaining **37 targets differ**, rather than failing the audit parser. This does not establish that the 73 reference-equivalent targets independently repair their issues.

## Confirmed findings

### 1. High: partial reference targets admitted as complete supervision

`new-karos/scripts/coding_public100014.py:190–201` verifies the example, reference-patch and preparation hashes but accepts any syntactically valid `rendered_patch_sha256`. It does not re-render the action against original source or prove that the rendered change equals the reference transformation. `make_bundle` at lines 374–377 permits fallback preparation evidence whose rendered hash defaults to the reference hash. A hash-shaped claim cannot substitute for replay.

The new offline audit reconstructs the same sparse original from captured source and unified-diff context, applies both reference and assistant edits, then compares their resulting lines. Unique placeholders represent unknown unchanged lines; no source content is guessed. Equivalent coalesced edits pass. Missing hunks, changed replacement content, extra edits and no-op proposals fail. Exact counts:

| Split | Rows | Complete reference-equivalent targets | Different targets |
| --- | ---: | ---: | ---: |
| Training | 100 | 66 | 34 |
| Development | 10 | 7 | 3 |

A separate authority coverage scan finds **29/100 training examples** with reference changes outside all captured source blocks. Remaining mismatches can occur within captured authority; merely checking bounds is insufficient.

Concrete example: `Project-MONAI__MONAI-1012` asks to preserve filenames containing multiple periods. Its assistant target adds a blank line, reformats a function signature and changes documentation punctuation. The public reference also changes extension-stripping behavior at original lines 442–453 and format matching near original line 526. Those behavioral edits are absent from the target. Its source excerpt ends at line 438. Training on this target rewards an incomplete response.

Files: `training-target-completeness020.json` (exact per-row results), `training-target-authority-audit020.json` (separate conservative coverage diagnostic).

### 2. High: training and inference use different source serialization

`coding_train014.py:100–103` trains on a user object containing `instruction`, `issue` and `original_source`; each source block contains `numbered_original_source`. The actual full100 input ZIP confirms those fields. Evaluation020 uses `coding_eval020.py:72–75`: no user `instruction`, and source blocks contain unnumbered `original_source` with `origin`. The system prompts also differ.

This mismatch is a fact. Its share of the 0/9 result is unmeasured. Numbered lines make inclusive editing easier; removing them during evaluation plausibly contributes to wrong ranges, but is not a proven sole cause. Use one shared versioned serializer and action contract for future training and generation; preserve evaluation020 unchanged.

### 3. High: independent repair evidence does not cover the full corpus

The public100 protocol explicitly permits distributor supervision with a recorded qualification shortfall. Its public evidence documents state `verification_basis: dataset_authors; not locally reproduced`. Only the separately reviewed two-family resource examples have independent admission captures. The 100-row corpus therefore cannot be described as 100 independently verified repairs.

The new gate proves reference-equivalent supervision only. A separate captured baseline failure and post-action regression/relevant-test success remains required before calling a row independently verified. Keep both fields distinct; never silently convert a reference-equivalence pass into repair success.

### 4. Evaluation020 tests one proposal, not the successful system loop

`coding_eval020.py:18` freezes `calls_per_arm_case: 1`. Final report records four candidates per arm reaching checks and failing; remaining responses fail patch/action admission. The earlier 7/12 loop result used another model transport. It cannot establish this adapter's effectiveness, and this single-call result cannot establish that feedback has been tested for the adapter.

## Loss masking and training mechanics

No confirmed label-shift defect found. `coding_train014.py:98–106` requires exact chat-template prefix agreement, masks system/user tokens with `-100`, supervises the assistant suffix and refuses sequence truncation. `coding_resource014.py:52–83` selects prediction position `index - 1` and labels `index`, preserving causal shift. The full100 receipt records `loss_projection: supervised-causal-positions-v1`, 40 completed updates, finite loss, nonzero gradients and changed adapter weights. The frozen 14B base was not fully fine-tuned.

This read-only audit does not numerically re-run GPU loss/gradient equivalence. Forty updates, q/v-only LoRA and cross-repository generalization may limit performance, but their causal contribution is a hypothesis. Fix supervision completeness and interface alignment before paying more compute or increasing model size.

## Smallest development-phase corrections and gates

1. **Already implemented offline:** reject any row whose complete target transformation differs from the reference. Preserve this corpus and its receipts; create a new admitted corpus version rather than editing old evidence. The audit exits 1 on any mismatch.
2. Route training and inference through the same explicit versioned serializer. Assert byte-identical system/user messages for the same development example and action contract. Do not change the completed evaluation020 prompts.
3. Require a replay receipt produced by the production source-authority validator; independently compare all affected file bytes against the reviewed reference result. Reject missing hunks and extra edits, not only invalid ranges. Never expand issue-only context using hidden evaluation answers; insufficiently localized examples must be excluded or handled by an explicitly separate training-data policy.
4. Separate `reference_equivalent`, `independently_reproduced`, and `training_admitted` flags. Bind each to source, target, verifier and capture hashes. Require complete raw outputs for independent admission.
5. Before any new large run, use development-only examples for a tiny overfit and held-out development smoke. Verify actual generated action replay and tests, not training loss alone. Freeze the next protocol before evaluation on new cases. The already exposed evaluation020 cohort must not become a fresh holdout by renaming it.

## Reproduction

```sh
/Users/gauravkumarnayak/Desktop/new-karos/.venv/bin/python -m pytest -q /Users/gauravkumarnayak/Desktop/resume/kairos-closeout020/training_audit/test_target_completeness.py

/Users/gauravkumarnayak/Desktop/new-karos/.venv/bin/python /Users/gauravkumarnayak/Desktop/resume/kairos-closeout020/training_audit/target_completeness.py \
  --input-zip /Users/gauravkumarnayak/Desktop/resume/kairos-ai014/.runtime/real-training-package-full100/kairos14-real-input014-full100.zip \
  --dataset /Users/gauravkumarnayak/Desktop/resume/kairos-ai014/.runtime/coding-intake014/swe-gym.parquet \
  --output /tmp/training-target-completeness020-new.json
```

Measured: **9 tests passed**; complete-corpus audit exits **1**, correctly rejecting the corpus. The report stores exact ZIP and dataset hashes. Output creation is exclusive to preserve prior receipts. No claim of repaired model behavior follows from these software checks.
