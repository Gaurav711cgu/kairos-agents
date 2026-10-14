# Kairos

**Turn an agent failure into an inspectable incident, a controlled rerun and a release decision with evidence.**

Kairos is a local full-stack agent reliability workbench. Its public website leads with an actual synthetic incident: context compaction removes a prior-compensation exception, a reference policy proposes an incorrect 480-cent adjustment, and an independent grader rejects it. Preserving the exception changes the proposal to zero. No commercial payment is made.

Build002 adds real local Keycloak OIDC, tenant and role authorization, durable model jobs, fenced workers, captured request/response blobs, controlled recovery, transactional sandbox approvals and task-level evaluation reports. The current dark website retains source records, model failures and explicit unavailable states. It does not substitute invented canonical data when the API fails.

## Review in five minutes

1. Open `/` and toggle the lead incident’s recorded context. See what was omitted and why the grade failed.
2. Open `/incidents`, select an event, filter the timeline and inspect raw payloads. Event selection survives a refresh through the URL.
3. Open `/executions` to inspect actual local Qwen calls, their unmodified responses and independent grades.
4. Open `/reports` to inspect the paired bounds, hard checks, task rows and downloadable JSON.
5. Sign in through `/workbench` to create a bounded job, inspect progress, cancel or create a fresh fork. Review a sandbox adjustment proposal before approving and dispatching it.

Public reading needs no account. Writes require authentication. Synthetic local credentials stay in ignored mode0600 files.

## Observed model results

The initial six durable Qwen2.5-0.5B-Instruct jobs passed **0/6** independent grades: four wrong policy outcomes, one missing required evidence citation and one strict-schema failure. Their requests and responses remain inspectable. This is a small development probe, not six independent holdout samples.

A separate versioned development batch planned 32 tasks: **three passed, 12 returned captured model responses, and 20 had provider errors**. All planned outcomes remain in the report, and the gate failed its strict-schema invariant. Do not describe this as 32 valid model-quality observations. The earlier build001 offline probe remains unchanged at 0/4 and used a different task contract.

Deterministic 1,024-task null and planted-regression calibrations exercise the gate. They do not qualify the model for release. Current model release remains blocked.

## Local setup

Requires Python3.12+, Node.js24, npm and Docker. Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-api.lock
python3 scripts/configure_local.py
docker compose --env-file .env.kairos.local up -d --wait
python3 scripts/run_local.py seed
npm --prefix dashboard ci
```

Configuration generates ignored credentials once and preserves existing values. PostgreSQL uses loopback port55432. Reuse an existing project database rather than starting another container over that port. This build session uses `kairos-postgres-build001`.

Provision local Keycloak by following [infra/identity/README.md](infra/identity/README.md). The provider runs on loopback8088; its provisioning script generates synthetic accounts, explicit memberships and ignored `.runtime/identity.env`. Restart the API after provisioning.

Start each service in its own terminal:

```bash
python3 scripts/run_local.py api
python3 scripts/run_local.py web
python3 scripts/run_local.py worker
```

Open `http://127.0.0.1:3100`. API runs on8100. The optional model service runs on8120 in a separate environment with torch, transformers and pre-downloaded weights:

```bash
python3 scripts/serve_local_model.py --model /absolute/path/to/qwen2.5-0.5b-instruct --port 8120
```

The loader uses local files and disables remote model code. The convenience `python3 scripts/run_local.py model` defaults to this build machine’s cache at `../resume/.local-models/qwen2.5-0.5b-instruct`. `KAIROS_MODEL_ENDPOINT` configures the server-controlled adapter URL. `KAIROS_BLOB_DIR` selects local content-addressed storage, default `.runtime/blobs`.

## Verify and reproduce

```bash
python3 scripts/run_local.py test
npm --prefix dashboard run test:boundary
npm --prefix dashboard run lint
npm --prefix dashboard run typecheck
npm --prefix dashboard run build
npm --prefix dashboard audit --audit-level=low
```

PostgreSQL tests require `TEST_DATABASE_URL` and create isolated temporary schemas. Real-provider tests additionally need provisioned Keycloak and `KAIROS_TEST_IDENTITY_PROVIDER=1`. The final backend run passed **169 tests**, with two dependency deprecation warnings. Both Docker images built successfully. API-lock vulnerability audit found no known vulnerabilities; the frontend audit was also clean at its recorded checkpoint. Final frontend/build/audit/browser receipts are tracked in [docs/BUILD_002.md](docs/BUILD_002.md).

Evaluation CLI saves every planned task and failure:

```bash
.venv/bin/python scripts/run_evaluation.py --mode null-calibration --output /tmp/kairos-null.json
.venv/bin/python scripts/run_evaluation.py --mode planted-regression --output /tmp/kairos-planted.json
```

The fixed paired Hoeffding gate uses alpha0.05, margin0.10 and at least1,024 predeclared synthetic holdout tasks. It returns PASS, FAIL or INCONCLUSIVE. Hard invariant failures block immediately. Calibration modes are deterministic; `--mode model --split development` performs real model calls and requires the configured adapter.

## Deployment and evidence

`Dockerfile.api`, `Dockerfile.web` and `compose.production.yaml` package API, worker, PostgreSQL and website. Production configuration rejects developer authentication and non-HTTPS identity URLs. A trusted HTTPS OIDC provider, TLS edge proxy, protected secret injection, provider durability and deployment-specific backup policy remain operator prerequisites. Container builds are not a public deployment.

The CI definition exercises PostgreSQL integration, actual local OIDC protocol flows, synthetic gate calibration, frontend audit, lint, types and build. A hosted workflow run is not claimed until a corresponding receipt exists.

- [ARCHITECTURE.md](ARCHITECTURE.md): boundaries, decisions and recovery semantics.
- [docs/BUILD_002.md](docs/BUILD_002.md): validation, setbacks, evidence and remaining gates.
- [BRAIN.md](BRAIN.md): compact checkpoint and targeted reading map.
- [docs/LEGACY_REUSE_REVIEW.md](docs/LEGACY_REUSE_REVIEW.md): useful prototype ideas and reproduced defects.
- [docs/IDENTITY_BOUNDARY.md](docs/IDENTITY_BOUNDARY.md): single-issuer trust and migration constraint.
- [kairos_api/JOBS_RUNTIME.md](kairos_api/JOBS_RUNTIME.md): exact worker, capture, replay and recovery contract.
- [evidence/build002/](evidence/build002/): raw reports and executed local drills.

## Scope of the portfolio claim

This project demonstrates full-stack implementation, persistence, concurrency, authorization, failure analysis, applied model integration and evaluation engineering. It does not demonstrate model research, public production operations, real customer adoption or universal agent safety.

All published tasks are synthetic. Hashes establish local consistency, not immutable history. Fresh forks rerun a whole scenario; arbitrary historical-step resume is unsupported. Sandbox receipts establish a transactional PostgreSQL effect contract, not exactly-once commercial integrations. Filesystem blobs are not an S3 deployment. Legacy `harness/`, `engine/`, `ingest/` and `storage/` code remains outside the active product path. Build001 evidence is preserved separately.
