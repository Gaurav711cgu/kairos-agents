# Retrieval-assisted repair013

Date: 16 October 2026. Source parent: `4f487000d5d6d92c10c4b08589d4dbf9644816ae`.

## Earned result

One end-to-end development investigation retrieved original pytest source, made five model calls, proposed one patch and passed one independent check comprising **22 tests**. Elapsed investigation time was **79.809237 seconds**. Captured usage was **66,744 input tokens and 402 output tokens**. The original source checkout remained unchanged; owned PostgreSQL and Docker services stopped without cleanup errors.

The provider was the existing signed-in ChatGPT CLI, explicitly requesting `gpt-6.1-sol`. The provider did not attest a resolved model ID or weight hash. No API billing fallback, credit purchase or new GPU was used. Internal CLI retries are opaque. The 64,000 reported-input-token admission ceiling stops subsequent calls, so the final call could and did overshoot it. This is not a hard billing cap.

This is a previously exposed development case, `pytest-dev__pytest-6197`, with repair hints in its public issue. Existing baseline-failure and reference-repair qualification was reused. Dense selection did not use registered maintainer entry-file hints. The result establishes that this retrieval-assisted workflow completed this investigation; it does not establish fresh generalization, retrieval causality, loop superiority or an official SWE-bench score. Historical **0/36** and **0/10** studies remain unchanged.

| Claim | Exact evidence |
| --- | --- |
| Five calls, one patch, one check, 22 tests | `evidence/evaluation013/pilot/summary.json` and original `bundle.json` |
| Original captured patch and check bytes | `pilot/candidate.patch`, `pilot/checks.json`; download catalogue verifies bytes and SHA-256 |
| Six initial source regions and later reads | `pilot/retrieval.json` and ordered steps in `pilot/bundle.json` |
| Source isolation and successful cleanup | `pilot/receipt.json`, bound to original private result and experiment hashes |
| Local software checks and original failures | `evidence/evaluation013/acceptance.json` |
| Historical preservation and current source | `evidence/evaluation013/manifest.json`; `scripts.verify_evaluation013` |

The static capture was explicitly reviewed for public-upstream content. It is a development export, not a change to the original record's private publication flag. Credentials, process environments, database dumps and model weights are excluded.

## What a website visitor does

1. Run `python3 -m scripts.reviewer demo` and open `http://127.0.0.1:3310`.
2. Select **Inspect the completed repair investigation**, or open `/repair-investigation` directly. Read the issue and pinned original revision.
3. Expand a retrieved-source region. It shows original code and the context supplied before generation, rather than an opaque JSON response.
4. Inspect the highlighted proposed change: removal of the premature `_mount_obj_if_needed()` call. Open the check output and inspect the **22-test** result.
5. Expand timeline entries to see model actions, source reads, patch construction and the independent check. Download the exact patch, check output, retrieval capture, receipt and complete evidence bundle.

The visitor obtains an inspectable proposed repair and evidence for human review. Browsing this saved investigation makes no model call and modifies no repository. Live submissions remain in the authenticated workbench with registered tasks and explicit inference setup. The saved view does not simulate login or progress.

Desktop and 390 px browser journeys verify navigation, keyboard-operated source/check controls, highlighted patch rendering, exact downloads, invalid identifiers and absence of horizontal document overflow. Screenshots are in `evidence/evaluation013/screenshots/`.

## Comparison and exposure infrastructure

`scripts.cohort013` freezes metadata from the pinned 300-row SWE-bench Lite test split. Only seven reviewed metadata columns are retained; reference fixes, test patches, hints and hidden test identifiers are excluded. Selection excludes prior IDs and normalized issue digests, then uses SHA-256 of the fixed seed and instance ID. Each repository contributes four development and eight held-out candidates: **24 candidates total** across Django and pytest.

These are metadata candidates: **zero have completed new baseline/reference qualification**. Source-edit eligibility, dependencies and independent checks must qualify before inference. The frozen pool cannot be replaced according to model success. A public historical benchmark may already occur in model training; task-exposure exclusion cannot prove otherwise.

```bash
python3 -m scripts.cohort013 verify \
  --metadata evidence/evaluation013/cohort/metadata.json \
  --history evidence/evaluation013/cohort/prior-exposures.json \
  --cohort evidence/evaluation013/cohort/cohort.json
```

`scripts.repair_report013` validates frozen case/arm/config/model identities and a complete attempt ledger. It reports missing and unknown outcomes explicitly, preserves infrastructure failures and absent costs, and computes descriptive paired issue-level bootstrap differences. Optional pre-check confidence supports a Brier/reliability report only when captured before verification. This is tested reporting infrastructure; no new multi-arm study or calibration result is claimed. See `REPAIR_REPORTING_013.md`.

## Training preparation

The current audit contains **123 records, 286 model calls, ten verified trajectories, three distinct verified tasks and four rendered verified patches**. It reserves 91 exposed or planned task IDs. Records are not independent positive training examples. The earlier 122-record audit remains preserved.

`scripts.training_bundle013` checks licensed provenance, issue families, exact and near duplicates, original-source ranges, independently evidenced labels, current exposure guards and family-disjoint splits. It exports deterministic allowlisted training/development data while withholding held-out material. The committed empty inventory deliberately reports `training_data_ready: false`; it is not a fitted adapter or a training corpus. The notebook is an inert runtime preflight. No Kaggle/Colab account action, upload or training occurred. See `TRAINING_PREPARATION_013.md` and `CLOUD_TRAINING_013.md`.

Two defects found during review are fixed: normalized historical issue digests now participate in exposure checks, and verification receipts must bind the same source revision, path, range and bytes. Separate regression tests prevent alias leakage and retagging unchanged code to another revision.

## Acceptance and owned corrections

Local acceptance passed **803 backend tests**, with **138 explicit environment/opt-in skips and eleven passing subtests**. It passed **12 recorded browser journeys and eleven interaction-fault journeys**, 23 frontend unit checks, lint, types and a production build. No model or Docker service was needed for this software acceptance. Real database/OIDC acceptance runs separately in hosted CI; local skips are not counted as passes.

The first acceptance attempt found a missing `node:url` import in the new browser test. Later browser assertions incorrectly required a bare test count and stderr despite the existing renderer including timing and stdout. Fixes preserve actual product output and assert its visible semantics. Original failed receipts remain bound in acceptance. The passing production build was reused only after confirming unchanged product source; the later edits affected tests and documentation.

Reproduce software acceptance with Python 3.12 and Node 24:

```bash
python3 -m scripts.reviewer check --recorded-only --runtime .runtime/review013
python3 -m scripts.verify_evaluation013
```

The source seal binds all additive013 files and inherited historical seals. Old verifiers run against exact old Git snapshots. Checksums establish consistency against these references, not signed immutable history. Hosted workflow outcomes are linked separately in the pull request; a local receipt never predicts a hosted pass.

## Ordered work still required for broader AI claims

| Gate | Current evidence | Next bounded action and completion condition |
| --- | --- | --- |
| Fresh comparison | Frozen 24 metadata candidates; no newly qualified cases | Qualify baseline/reference behavior within reviewed dependencies and storage limits, freeze arms, then execute once and publish every attempt. |
| Model training | Validated export/preflight software; zero eligible acquired examples | Acquire and review licensed issue families, pass frozen data gates, measure free-GPU fit/resume, then compare a pinned adapter against its base. |
| Official benchmark score | Development pilot and historical curated studies | Run the actual official harness on its declared set with complete predictions and infrastructure accounting; do not extrapolate a subset to 300 cases. |

These are separate measured phases. They do not invalidate the delivered full-stack evidence viewer, durable runner or the successful development investigation. They cannot be marked complete by more documentation or software fixture passes.
