# Public100 adapter study and real-data resource pilot

The resume release targets 100 distinct training families, 10 development families and 20 untouched evaluation families. This separate study uses public repair supervision, a fixed ten-family independent training audit, and independent qualification of every development/evaluation case. The original independently reproduced 200-case study remains unchanged and is follow-up work.

## Implemented entry points

`python -m scripts.coding_train014 doctor|fit|train --study public100` selects the new contract explicitly. The default `independent200` retains the original requirements. Public100 requires the pinned dataset bytes, a hash-bound evidence index, source-bound conversion receipts, attributable provenance/family reviews, all 40 independent audit/development/evaluation captures, and exactly 100/10/20 distinct families. A prior training-only candidate cannot be reassigned to development or evaluation. The training audit is determined by a fixed seed and family identities, not by successful results.

`python -m scripts.coding_public100014 plan` creates a candidate-only plan from the exact pinned dataset and prior screen. Actual preparation selected 100 training candidate IDs across six repositories, 10 development candidates and 20 evaluation candidates outside the original training-only cohort. This is not 130 qualified families or a training-ready corpus. Family review, conversion and qualification remain separate gates.

`python -m scripts.coding_train014 doctor|fit --study resource2` accepts exactly two real examples with their full independent evidence graph. It cannot run `train`, admit a smaller model, bypass Public100 counts or become a repair-effectiveness result. The prepared package passed this actual evidence check: two examples and 20 captured-evidence files.

The native Transformers runner shares adapter settings, padded 2048-token geometry and source identity between the resource pilot and Public100 fitting. Public100 plans 40 optimizer updates; the resource conditions are full 20, interrupted 10 and resumed 10 additional updates. Checkpoints record typed adapter/optimizer/scheduler/random-state digests. `python -m scripts.coding_resource014 --root RUNS` verifies stage identities, every checkpoint hash, interrupted-checkpoint provenance and actual state equality. Full Public100 training accepts only a matching measured recipe with successful memory-reserve and resume checks. Transfer of resource evidence does not establish repair quality or that 100 examples were trained.

## Approved cloud workflow

`notebooks/coding-14b-real-resource014.ipynb` and the 771,054-byte `kairos14-real-input014.zip` are specifically approved for Google Colab. The ZIP contains project Python source, two reviewed public repair examples and their public-test captures. No account state, credentials or weights are included. Its SHA-256 is `2b552de098e0e5c61185c0d914ea59d92798f94baaa5007453f87c90b84e4178`.

The notebook first verifies its input package and downloads a tiny probe. Actual local probe verification is required before package installation or the 9.93 GB model download. Each condition is a separate explicit dispatch, with no automatic retries. A failed resource check prevents further conditions. Export includes failures, state proofs, a resumable interrupted checkpoint and the final adapter; base weights and account state are excluded. Verify the received archive before owned runtime cleanup and Google sign-out. Provider-retained logs are outside that cleanup.

Chrome native control was unavailable because Computer Use permissions were not granted. The approved v2 notebook and input ZIP were uploaded through the supported in-app browser. Input hashes passed on a free Tesla T4. The download preflight has not passed; weights and real-data training have not started. A download failure must stop the workflow before model allocation.

## Verification and limits

Focused tests: 78 passed. Fresh shared backend acceptance: 1,024 passed, 141 optional skips and 16 subtests passed; two existing deprecation warnings. Docker and inference remained off. This is not a new PostgreSQL/OIDC journey run or a GPU compatibility result. Fixtures are isolated tests, never corpus examples or successful model repairs.

Receipts and source hashes: `evidence/measurement014/coding-data/public100-v1`. Raw backend output, candidate identities and prepared cloud package remain in the persistent private staging root. Model quality still requires the frozen paired evaluation. Reporting must distinguish externally supplied training supervision, ten locally audited training families and independently qualified development/evaluation cases.

The v2 pilot keeps frozen large embedding/output matrices in FP16 and normalization in FP32. An isolated tiny CPU fixture verified checkpoint/resume state equality under FP16 autocast; it is not GPU compatibility evidence. The received-export streaming verifier passes nine checks, including source identity, corrupted artifacts and unsafe members. Current cloud preflight evidence is `cloud-preflight-v2.json`; older preparation/progress receipts are preserved snapshots.

A later preflight resolved the browser download failure: actual cloud files were transferred through visible notebook output. Both the52-byte original probe and a1MiB test were saved locally and matched observed cloud hashes. This permits dependency setup; it does not establish GPU fit or model improvement. Final evidence still requires bounded byte transfer and full manifest verification.

## Observed v2 loader failure and prepared v3 correction

V2 loaded the pinned model but failed before any optimizer update because the quantization configuration was an object rather than a dictionary. Its complete764,657-byte export was received and all10member hashes verified. The correction normalizes the public configuration representation without relaxing the frozen NF4 checks.58focused checks, an actual Transformers configuration-object check and the shared backend suite pass (1,031passed,141optional skips,16subtests). V3 is prepared for separate upload approval and reuses the existing pinned environment/weights. It has not been uploaded or trained. Public receipt: `failed-pilot-v2.json`.

## V3memory result and next resource recipe

V3loaded the model but failed in full-vocabulary loss allocation before an optimizer update. Its763,539-byte export and all9members are verified locally. The next recipe preserves the14Bmodel and2048-token inputs while using supervised-token vocabulary projection.66focused checks and native loss/gradient/Trainer equivalence tests pass. A new GPU run and full backend acceptance after this change remain pending. No new training or effectiveness claim is made. Detailed proof: `memory-failure-and-fix-v1.json`.

## V4 readiness

Complete backend acceptance after the selective-logit memory fix and measured-target coverage gate passes: 1,040 tests, 141 optional skips and 16 subtests. The measured pilot bounds future supervised target demand; larger targets require a new resource measurement. V4 is prepared for a fresh free runtime because the former session expired. Upload and execution await approval of the exact versioned files. No V4 training result exists. Current receipt: `v4-ready-v1.json`.
