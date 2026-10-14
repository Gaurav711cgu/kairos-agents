# Kairos build006 reviewer guide

Updated 2026-10-13. Start with the recorded website, inspect the model proposal and checks, then compare the complete follow-up results. Build006 adds 28 genuine captures to the preserved 48-record package. Its local software acceptance passed; see [the current report](FINAL_REPORT_006.md) for exact status.

## Run from the repository root

Requirements: Python 3.12 or newer and Node.js 24 with npm on macOS or Linux. Initial locked dependency installation needs network access. Recorded inspection needs no Docker, database, model, API key or account.

```bash
python3 -m scripts.reviewer demo
```

Open `http://127.0.0.1:3310`. The entry point installs locked website dependencies, builds the interface and serves genuine captured records. It labels recorded authority and disables login/private commands. An unavailable record or corrupt artifact remains an explicit error; live failures never trigger an automatic recorded fallback.

Keep Docker and inference off for this inspection. The initial website build is real computation; avoid running builds and inference together on the existing Mac. Ctrl-C stops the owned website process. Stop an older reviewer mode before changing modes on the same port:

```bash
python3 -m scripts.reviewer stop
```

## Five-minute inspection

1. Open the homepage's Django multi-database development investigation. Read the original issue. It includes the proposed `using=db` change; this is disclosed, not evidence of novel diagnosis.
2. Inspect retained original source and the captured model context. Source remains visible after tool observations. Exclusions and truncation decisions are captured explicitly.
3. Read the patch and registered check output. Only passing independent checks produce a verified repair; correcting one regression while breaking an existing test remains unsuccessful.
4. Open `/follow-up`. Compare 18 development attempts with ten frozen fresh-validation attempts. All development successes cover Django11066; fresh validation remains 0/10. Compare calls, tokens, checks and elapsed time alongside outcomes.
5. Download an investigation and its original artifacts. Open `/study` for the unchanged older 0/36 comparison, then `/capacity` for the measured local control plane. Connect each statement to its receipt rather than inferring model or production claims from a polished interface.

The package contains 76 records and 965 original blobs. Captured byte hashes, schemas, ordered steps and references are validated before serving. The complete follow-up aggregate is `dashboard/public/follow-up/results.json`. Unknown dispatch consumption is unavailable, not zero. V6 reasoning results are a separate development experiment; no fresh v6 validation claim is made.

## Operate the isolated full stack

Docker is required only for live PostgreSQL/Keycloak operation and disposable verification. The documented entry point and ownership namespace remain unchanged:

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer fullstack
```

Ports are PostgreSQL 55434, Keycloak 8090, API 8310 and web 3310. Private state lives under ignored `.runtime/reviewer005/` unless an explicit `--runtime` path is provided. The `reviewer005` name identifies the stable entry-point ownership namespace; it does not assign new investigation results to the old release. Generated credentials are private. Read `.runtime/reviewer005/identity.local.json` locally when needed; never publish its contents or browser authentication state.

Setup reuses resources only when their owner identity and configuration match. Conflicts fail instead of overwriting an existing installation. Fullstack starts no model or worker by default. Authentication, roles, tenant boundaries, stable command receipts, queue/cancel/fork and replay exercise the real control plane. Recorded imports remain historical results. Replay dispatches neither a model nor tools. Actual PostgreSQL and four OIDC browser journeys passed; see the final acceptance receipt for exact scope and skips.

After a required live check, stop the owned services. The command preserves volumes and historical images and does not stop unrelated projects:

```bash
python3 -m scripts.reviewer stop
```

## Reproduce the original saved repair

```bash
python3 -m scripts.reviewer repair
```

This existing entry point reproduces the **original Django10914 file-permissions repair**, not the new Django11066 development demonstration. It downloads pinned source, prepares reviewed dependencies, applies the original captured model patch in a disposable copy and writes actual outcomes/image provenance. No model or database is required. Build005 observed 110 tests with one skip and disclosed that the rebuilt image differed from the historical identity. A fresh invocation must be described using its own new receipt; it is not a fresh inference attempt.

The new Django11066 proposal, context and checks are inspectable through recorded evidence. Development/validation source snapshots and configuration receipts identify their exact execution environment. Frozen studies must not be rerun silently or presented as new unseen cases.

## Run acceptance and verify scope

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer check --recorded-only
```

Recorded-only checks cover recorded inspection and frontend acceptance without Docker. For actual database/OIDC journeys when Docker is required:

```bash
python3 -m scripts.reviewer check --fullstack
python3 -m scripts.reviewer stop
```

The entry point records actual outcomes and explicit skips. Tests with isolated fixtures do not count as model repairs. Existing build005 receipt counts remain historical; build006 acceptance records 291 backend passes/six opt-in skips, six recorded browser journeys and four actual OIDC journeys, with separate clean-source evidence. Runtime files, credentials, installed dependencies and model weights are excluded from the release.

`python3 -m scripts.verify_delivery005` verifies the unchanged preserved build005 source snapshot and its historical archives. It must not be used to certify changed build006 source. Verify the separate current release with `python3 -m scripts.package_release006 --verify`. An extracted source archive uses `--verify --source-only`; this checks its embedded inventory, while the external index/receipt verify the downloadable archive itself. Do not overwrite or reseal old manifests to match new files.

## What to defend in an interview

Explain durable command acknowledgements, stable retry identities, database-clock leases, fencing, artifact durability and uncertain dispatch handling. Show the context-retention failure in captured requests, then explain why exact original-source handles and independent checks prevent plausible prose from counting as a repair. State that fresh validation failed even after fixing the harness defect; a correction to tool access is not proof of model capability.

Use [build005 claims](CLAIMS_005.md) for already earned engineering statements, identifying their original receipts. Use [build006 report](FINAL_REPORT_006.md) for the new audit and complete results. The public issue supplies the successful development fix, source locations are human-localized, public training contamination is possible, and verifier tests have declared limits. Personal explanation/debugging demonstrates code ownership; package integrity alone cannot.
