# Development supervision qualification 021

Seven of seven filtered development supervision targets independently reproduced their declared baseline regressions and passed their complete registered selected suites under both reference and supervision edits. There were no skips or collection errors in the successful attempts. These are reference-derived supervision checks, not model-generated repairs or a benchmark score. No model calls or training occurred.

| Case | Baseline passed | Reference passed | Supervision target passed |
| --- | ---: | ---: | ---: |
| getmoto__moto-5752 | 79/80 | 80/80 | 80/80 |
| getmoto__moto-5794 | 183/184 | 184/184 | 184/184 |
| getmoto__moto-5809 | 87/90 | 90/90 | 90/90 |
| getmoto__moto-5835 | 80/81 | 81/81 | 81/81 |
| pydantic__pydantic-4911 | 67/72 | 72/72 | 72/72 |
| pydantic__pydantic-4920 | 11/12 | 12/12 | 12/12 |
| pydantic__pydantic-5021 | 20/24 | 24/24 | 24/24 |

Each stage executed 543 tests across seven cases. This counts executions, not unique test identities across revisions. The ledger reverified 132 artifact hashes and preserves original provenance, storage and SDK failures.

## Engineering corrections

- Strict admission rejects incomplete reference transformations. The original 100-row training corpus remains frozen; 66 filtered training rows are candidates, not independently admitted repairs.
- Source rebinding verifies pinned repository/revision, full tree and exact excerpt bytes. It changes provenance identifiers only and preserves target ranges and replacement text.
- Incomplete parameter IDs expand to complete test functions; every parameter must collect and finish. Skips and missing tests reject qualification.
- Version-specific Moto and Pydantic dependency reviews bind official wheel hashes and exact image provenance. Builds are offline; checks run without network, credentials or Docker sockets as a non-root user with two CPUs, 1 GiB memory and a 120-second limit.
- Cognito's first image failed two existing tests because its old SDK performed obsolete client-side password validation. A separately reviewed SDK revision corrected the environment; original failures and all 184 tests remain preserved.
- Only this correction run's unused source preparation was losslessly archived for storage, with 2,136 entries verified before removing its expanded copy. Historical data, weights and original corpora remain untouched.

## Acceptance

Complete backend: 1,163 passed, 146 skipped, 16 subtests in 30.44 seconds. Docker Desktop stopped after checks. The service-dependent skips do not establish fresh live PostgreSQL/OIDC acceptance; frontend checks were not repeated for this backend-only change.

## Evidence and next gate

Local receipts: `development-qualification021-ledger-v3.json`, `phase021-development-qualification-acceptance.json`, `storage-after-development021.json` and source snapshots in `phase021-source-snapshots/`. Original failed attempts remain alongside successful attempts.

The next gate is independently admitted training data and generated-action sanity using the same v021 serialization for training and inference, followed by a frozen model comparison. The seven cases above are development examples; they must not be relabeled as untouched evaluation. Historical base/adapter 0/9 remains unchanged. No corrected-training improvement claim is established.
