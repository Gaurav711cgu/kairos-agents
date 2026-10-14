# Build007 reviewer guide

Use Python 3.12 and Node 24 from a clean checkout. No model, key or Docker is required to inspect recorded evidence.

```bash
python3 -m scripts.reviewer demo
```

Open http://127.0.0.1:3310/how-it-works. Follow the saved investigation, highlighted patch, checks, paired comparison and downloads. Current results are at `/advancement`; earlier studies remain at `/follow-up` and `/study`. Recorded mode closes private commands and never substitutes for a failing live API.

For the real control plane, stop the demo first and run:

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer fullstack
```

The isolated environment uses PostgreSQL 55434, Keycloak 8090, API 8310 and website 3310. Credentials are generated privately under ignored `.runtime/reviewer005/identity.local.json`. Choose the appropriate synthetic account locally; never publish the credential file. Runtime credentials have DML access but cannot migrate or alter the migration ledger. Provisioning applies checksummed migrations explicitly, then imports genuine captures. Inference and worker execution remain off by default. Queue, cancel, fork, replay, publication and downloads exercise real services.

Acceptance and saved repair reproduction:

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer check --recorded-only
python3 -m scripts.reviewer check --fullstack
python3 -m scripts.reviewer repair
python3 -m scripts.reviewer stop
```

The complete reviewer lock includes preserved statistical/replay test dependencies. API containers retain their separate smaller lock. Repeated setup reuses only matching owned resources. Conflicting ports, credentials/configuration fingerprints, changed captures or unknown schema revisions cause explicit errors. Shutdown preserves volumes and historical images. Stop Docker Desktop after container work on the current Mac.

The repair command reproduces the original Django10914 model patch against pinned source under a new build007-reviewer image. Read its actual tests and environment-change receipt; it is neither new inference nor the newer Django11066 development result.

Study007 uses explicit `--model-cache`, `--dataset`, `--case-root` and `--environment-file` arguments. `doctor` reads only and starts no inference or Docker. Pinned inference is macOS ARM64; portable paths do not establish Windows support. Frozen evaluation commands refuse delivery-source changes. Reproduce frozen execution only from the preserved source/configuration manifests; do not rerun or tune the locked cases.

The optional free-provider pilot is separate. It requires an explicitly selected private key file and billing-disabled project. Its HTTP400 setup rejection and HTTP503 uncertain dispatch are retained; no repair was captured. Do not bypass its durable no-retry ledger.

Verify the distribution after sealing:

```bash
python3 -m scripts.package_release007 --verify
```

Hashes establish consistency relative to the trusted local receipt, not signed or administrator-proof history. Hosted CI, external publication and customer adoption remain separate.
