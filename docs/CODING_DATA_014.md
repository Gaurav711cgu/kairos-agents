# Coding-model training data: intake checkpoint

## Latest conversion result: 17 October 2026

Five independently qualified reference repairs now span two repositories. The new Moto4809 case reproduces five declared regressions with six existing tests passing; its reference repair passes all11. The earlier fixed case4799 was excluded before execution because two required tests make real AWS requests. No tests were omitted and no provider responses were fabricated.

New context v5 follows public issue line citations and their same-file direct callees. It reads only the pinned original source and never fetches linked revisions or uses reference patches to choose regions. It retained the needed Moto code, exposing a separate four-hunk/three-edit conversion mismatch. V6 preserves the existing three-edit contract and unchanged v5 context, combining nonoverlapping hunks only inside the same already captured source handle. Exact reference-byte replay succeeds with two edits. The complete example fits1853tokens, with350supervised tokens. V4/v5 failures remain preserved.

There are now two complete converted examples, not two finally admitted rows. Full corpus admission, rights/family reviews and real coding-model training remain separate. Fresh verification:103focused tests;983backend passes and16subtests, with141optional skips. Docker is stopped. See `qualification-progress-v5.json` and `context-preparation-v6` under the coding-data evidence directory. All older numbered checkpoints below are historical.

## Earlier checkpoint: 17 October 2026

Seven distinct fixed candidates have been attempted. Four reference repairs qualify independently across two repositories: three MONAI and one Moto. Moto4792 reproduced both declared baseline failures with its twelve existing tests passing; the reference patch passed all14 selected tests, with no skips, missing output or source mutation. This is a maintainer-reference qualification, not an agent repair. Metadata and capture hashes are in `evidence/measurement014/coding-data/qualification-progress-v4.json`.

The Moto3.0 verifier uses a separately pinned dependency-only image, with network disabled, a non-root user, two CPUs,1GiB RAM and a120-second deadline. Portable locks and review are in `evidence/measurement014/coding-data/moto-3.0-v1`. The source-only frozen v4 context policy rejects this case because required edit lines were omitted. That failure is preserved; it is not admitted as training supervision. MONAI1086 remains the single complete converted example. Zero examples have completed final corpus admission.

The14B resource pilot ended at its5,400-second limit without resource acceptance. Its raw archive was not retrieved before the Colab session disappeared; Google is signed out. No real coding-corpus training has run. Earlier preflight/model proposals below are historical checkpoints; current selected capacity remains14B, with no silent smaller-model substitution.


## Enforced training admission

The training command now reads and validates the evidence bytes before opening model manifests, creating run output or importing GPU frameworks. A corpus containing valid-looking receipt hashes and admission flags is insufficient. `doctor` reports `ready: false` when the evidence bundle is absent.

Supply `--admission-directory` and `--admission-index-sha256` to `fit` or `train`. The directory contains `index.json` with version `coding-admission-index014-v1`, a `files` map from SHA-256 to safe relative JSON paths, the fixed `exposure_sha256`, and a `rows` map keyed by every training/development instance ID. Each row must reference exactly `qualification`, `binding`, `baseline`, `reference`, `screen`, `image`, `preparation`, `example`, `rights` and `family`. Shared frozen screen, image and exposure files may be referenced by multiple rows. Extra rows, unreferenced files, symlink paths and changed bytes are rejected. Each receipt is bounded to4MiB and the receipt package to256MiB.

Validation reconstructs the original qualification binding; matches repository, revision, source digest and issue; decodes and hashes the complete original test streams; verifies the declared test scope and baseline/reference outcomes; and matches the exact converted input and target to its preparation receipt. Successful conversion is required: a rejected context or conversion cannot be promoted. The fixed exposure inventory is opened and checked by both task ID and normalized issue digest. The admission-index hash is included in run intent and checkpoint identity.

A `coding-rights-review014-v1` receipt binds instance ID, repository, source commit, source digest and normalized issue hash. It requires an attributable reviewer/date, an explicit training-use decision, and separate license, provenance and use-basis entries for `source`, `issue` and `reference_patch`. A `coding-family-review014-v1` receipt binds the same identity, reviewed family ID, near-duplicate decision, method and rationale. These are review records, not automatic legal approval. No real review is fabricated to fill the current gap. The structural corpus floor, diversity, untouched evaluation families and intact tokenization remain independent gates.

```bash
python3 -m scripts.coding_train014 doctor --profile 14B \
  --corpus /counted/private/corpus.json \
  --corpus-sha256 "$CORPUS_SHA256" \
  --admission-directory /counted/private/admission \
  --admission-index-sha256 "$ADMISSION_INDEX_SHA256"
```

Evidence: `evidence/measurement014/coding-data/admission-hardening-v1`. Ninety focused tests passed; the broad backend run passed967 tests and16 subtests, skipped141 optional checks and encountered three sandbox socket denials. Those three checks passed separately with local loopback permission. All four existing real reference qualifications also passed offline raw-stream validation. No Docker, model allocation, new repair attempt or final corpus admission occurred in this phase.


## Completed

Acquired the official SWE-Gym train parquet at revision `bb94ed9e39bbeb96a7fcbfb533b80f25a7fd59cb`: 43,644,473 bytes, SHA-256 `60569cea74bb281f7a5579467436a2bc1932c6e0c5f2f7fa0d084392abd9ad97`. It contains 2,438 historical issues. Raw reference and test patches remain in private persistent storage. Public receipts expose only identities, source-path names, hashes and dispositions.

The fixed prefilter rejects exposed/reserved IDs or issue text, the evaluation repositories Requests/Sympy, unsafe/protected paths, non-Python edits, creation/deletion/rename/binary operations, missing regressions and exact normalized issue/patch/source-revision duplicates. Candidate reference scope is at most two files and 40 changed lines. Source replay, syntax checks and near-duplicate/issue-family resolution remain separate gates; static scope parsing does not prove a valid patch.

After those prefilters, select the first 500 candidates in ascending instance-ID order. Preserve all 2,438 dispositions and every excluded reason. Do not replace the selected cohort according to verification or model outcomes.

| Repository | Pending candidates |
| --- | ---: |
| Project-MONAI/MONAI | 198 |
| bokeh/bokeh | 15 |
| conan-io/conan | 55 |
| dask/dask | 109 |
| facebookresearch/hydra | 44 |
| getmoto/moto | 79 |

The first selected source revision per repository has an exact captured upstream license sample: Apache-2.0, BSD-3-Clause or MIT. Those samples do not establish rights for every candidate revision or issue text. Preserve notices, review each case and resolve related issue families before training admission.

The first candidate, `Project-MONAI__MONAI-1012`, has a fresh pinned source tree and a matching license. Its source archive hash and tree digest are captured. Its first independent qualification is now complete: baseline regression failure with all 13 existing tests passing, then all 14 tests passing under the reference repair. Source stayed unchanged, no tests skipped and no model ran. This is a qualified reference repair, not an agent repair or an admitted training example. MONAI imports Torch and NumPy; its selected regression also needs parameterized. A reviewed, hash-locked CPU image now supplies those dependencies. Do not substitute an extracted function or mocked package for the real repository checks.

## Next gate

Qualify the fixed candidate list with complete baseline regression failure and reference-repair success. The target remains at least 200 verified repairs across at least five repositories, with no repository above 25%. Preserve dependency failures, incomplete suites and shortfalls. Do not lower the gate or train failures as repairs.

Convert admitted source changes into exact source-handle actions and preserve independent test receipts. Keep all current evaluation families out of training and model selection. The new evaluation split, tokenized examples, cloud scratch allocation and measured GPU fit must be frozen before full fitting. See [the coding-adapter protocol](CODING_ADAPTER_014.md).

## Reproduce static intake

The optional environment needs PyArrow. Application dependencies remain separate. Supply every owned experiment root; the command refuses a partial or changed dataset and does not execute source, install dependencies, upload data or fit a model.

```bash
python3 -m scripts.coding_data014 \
  --runtime /counted/private/coding-intake014 \
  --exposure evidence/measurement014/training/repair-exposure014.json \
  --budget-root /counted/all-owned-experiment-root
```

The raw dataset remains private. `evidence/measurement014/coding-data/screen.json` contains the complete metadata-only exclusion ledger. The dataset's MIT label is not an automatic training-rights approval for all upstream material.

## GPU preflight and current access

`notebooks/coding-preflight014.ipynb` is a standalone read-only hardware/package inventory. It downloads no model or data, installs nothing, mounts no Drive and starts no training. The official coding-model candidate is pinned to `Qwen/Qwen2.5-Coder-1.5B-Instruct` revision `2e1fd397ee46e1388853d2af2c993145b0f1098a`; weight hashes and actual fit remain unmeasured.

The user explicitly authorized sign-in and the exact inventory-notebook upload. The notebook ran once on an available Tesla T4 with 15,360 MiB total and 14,913 MiB free VRAM. The observed environment was Python 3.13.15, Torch 2.11.0+cu130, Transformers 5.18.0 and PEFT 0.21.1; TRL and bitsandbytes were absent. This is resource inventory, not a measured QLoRA fit or compatible frozen training environment. No packages, weights or datasets were installed or downloaded by this command, and coding-model training did not start. The exact visible JSON and notebook hash are bound in [the preflight receipt](../evidence/measurement014/coding-data/colab-preflight014.json).

The owned runtime was disconnected and deleted immediately. The uploaded notebook was moved to the recoverable Drive bin. Google sign-out and removal of the remembered account from the chooser were verified; the final page shows a blank Email or phone field. No credentials were saved or passkeys created by the agent. The available browser interface exposes no cookie/history purge control, so that cleanup is not claimed. Google-retained logs, device records and a permanent Drive-bin purge are not claimed. A later training session requires user-controlled authentication again.

## Persistent state and preservation

The earlier `/private/tmp/kairos-qualification014` directory is no longer present; this check did not establish why. All 57 published original comparison captures still match their report hashes, and earlier qualification archives remain preserved. Do not claim the missing private final registry or scheduler state was recovered. New data and source preparation use persistent private staging. The storage check now counts all of `/private/tmp`, including any other temporary additions, instead of silently treating the absent path as recovered.


## Dependency qualification, first two cases

The first candidate passed the complete 14-test before/after protocol in a non-root, network-disabled, read-only container with two CPUs, 1 GiB RAM and a 120-second check deadline. Exact image: `sha256:66071ad14f60992a221024d1ab2959603689121e2a9919258aafe4f572275b3e`. Its portable requirements and Dockerfile are published without local resolver paths. Reinvoking the installed qualifier reused the original checks instead of executing them again.

The next fixed candidate, MONAI1037, failed collection because ITK was missing. Both original captures remain, with zero tests executed. A separately named dependency image adds official native ARM ITK wheels without changing source, dropping tests or replacing the failure. The revised image independently qualified MONAI1037: expected baseline regression failure and all 14 selected tests passing under the reference repair. The initial zero-test dependency failures remain. A new qualification revision is permitted only for a captured pre-model environment failure; successful and completed behavioral outcomes cannot be replaced this way. The original study results remain frozen.

`python3 -m scripts.coding_qualify014` validates the selected dataset row, exact source/image and complete registered test suite. It permits no model inference, arbitrary issue URL or agent-selected shell command. Explicitly reviewed MONAI 0.2 and 0.3 environments are registered; other versions remain pending until their dependency recipes are reviewed.

## Training checkpoint after six candidates

The separately reviewed MONAI0.3 image pins Ignite0.4.2 and preserves the earlier profiles. MONAI1086 qualified with four declared regression tests. The next three fixed cases1107,1116 and1121 did not produce complete verifier results; all partial outputs and return codes remain in qualification-progress-v3.json. Three of six distinct attempted cases have independently verified reference repairs. Zero examples are finally admitted for training.

Source-bound action preparation now mechanically replays targets through the production line-handle validator, including exact candidate bytes and original-source integrity. Its first three real conversions were rejected because the issue-only AST context did not cover the whole change. Preserve these v1 rejections; fix localization using issue/source evidence before any new preparation revision. Never expand a prompt from the answer to make admission pass. The focused conversion/environment/verifier suite passed21 checks with no skips. These are preparation mechanics, not model-fitting results.
