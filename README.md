# Kairos

Inspect an agent failure. See which evidence disappeared. Run a controlled comparison and check the result.

**Build 001 is a working local full-stack slice:** Next.js incident website, Python/FastAPI API, PostgreSQL persistence, exact context inspection and credential-bound controlled reruns. Its four seeded records are actually executed synthetic scenarios, not invented dashboard activity.

The current product runner is a **deterministic reference policy**, with no LLM calls or external effects. A separate four-case offline Qwen probe failed all four strict checks; raw outputs are preserved in `evidence/task-fit-local-qwen/report.json`. Neither run counts nor those four development cases qualify a model for release.

## Try the incident

Open the local website on **http://127.0.0.1:3100** after starting both services. The lead incident drops an already-compensated-order exception, proposes an incorrect 480-cent adjustment, and is rejected by an independent grader. Inspect the omitted context, then preserve it in a fresh full-scenario rerun. No payment is executed.

## Fresh local setup

Requires Python 3.12+, Node.js 24 (see `.nvmrc`), npm and Docker Compose. The checked local versions and exact validation are recorded in `docs/BUILD_001.md`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-api.lock
python3 scripts/configure_local.py
docker compose --env-file .env.kairos.local up -d --wait
python3 scripts/run_local.py seed
cd dashboard
npm ci
cd ..
```

Start two terminals from the repository root:

```bash
python3 scripts/run_local.py api
```

```bash
python3 scripts/run_local.py web
```

Local credentials are generated once into ignored files. Re-running configuration preserves them. Seeding is idempotent. Port 55432 is reserved for this project's local PostgreSQL; do not start Compose over another container already using it. This build session's manually started container is named `kairos-postgres-build001` and already owns that port.

## Verify

```bash
python3 scripts/run_local.py test
cd dashboard
npm run lint
npx tsc --noEmit
npm run build
```

PostgreSQL tests use temporary schemas and cover commit visibility, duplicate/conflicting commands, concurrent retries, tenant isolation, rollback and tampering. Database connection settings are required; tests skip integration cases if `TEST_DATABASE_URL` is absent. The workflow in `.github/workflows/regression-gate.yml` supplies PostgreSQL and checks the new slice; no hosted execution is claimed until it runs.

## Where to look

- `kairos_api/`: domain scenarios, independent grader, transaction repository, API and seed command.
- `dashboard/`: public site, incident inspector, context views and local-only fork proxy.
- `ARCHITECTURE.md`: choices and their boundaries.
- `PLAN.md`: current implementation contract.
- `docs/BUILD_001.md`: executed checks, source digest and known gaps.
- `scripts/task_fit_local.py`: offline model task-fit probe; optional torch/transformers environment and pre-downloaded weights required. Those heavyweight packages are intentionally outside the product API lock.

## Honest limits

The old `harness/`, `engine/`, `ingest/`, `storage/` and legacy test files are prototype code outside this slice. Their previous README and architecture claims are preserved as historical documents in `docs/legacy-prototype-*`; they are not evidence for the current product.

No arbitrary step resume, immutable ledger, statistical safe-release gate, live commercial integration, production auth, load qualification or real customer adoption is claimed. Hashes provide local consistency checks. Planned milestones remain in the planning brain, not marked complete by this build.
