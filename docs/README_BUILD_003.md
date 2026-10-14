# Kairos

Investigate a repository defect, inspect the model's patch, and reproduce the verdict.

Kairos is a local full-stack investigation workbench: Next.js, FastAPI, PostgreSQL, a durable bounded worker, content-addressed captures and isolated Docker checks. Public reading needs no account or live inference. Writes use local Keycloak OIDC, tenant membership and role authorization. Existing single-dispatch jobs and synthetic demonstrations remain separate historical workflows.

## Start with one real repair

[Django #10914](https://github.com/django/django/pull/10914) reported inconsistent uploaded-file permissions. Official local Qwen3-1.7B proposed this change against a pinned historical revision:

```diff
-FILE_UPLOAD_PERMISSIONS = None
+FILE_UPLOAD_PERMISSIONS = 0o644
```

The independent selected upstream suite passed: **110 tests, one upstream skip**. A fresh source copy reproduced that result. Inspect the complete captured response, both patch proposals, accepted patch and check output at `/investigations/8b03a42f-149e-4d44-937f-0d61636f6042`.

**Both approaches solved the same one of six cases.** The loop used three calls and 3,493 tokens for this case; the single call used 1,852 tokens. The twelve-attempt final comparison contains two verified attempts on one distinct case. Twelve earlier development failures remain published. No statistical superiority, general repair capability or SWE-bench leaderboard score is claimed.

## Reproduce the checks

On this prepared installation, from the repository root:

```bash
PYTHONPATH=. .venv/bin/python scripts/reproduce_investigation.py --record evidence/build003/django__django-10914-baseline-v3.json --output /tmp/kairos-repair.json
```

This does not call the model or database. It verifies frozen case material, applies the recorded candidate in a disposable source copy, and runs the registered checks without network access. See [the receipt](evidence/build003/repair-reproduction.json).

For a fresh machine, prepare dependencies and cases first. Requires Python 3.12+, Node.js 24, Docker, and at least 4 GiB free after preparation. Native inference installation currently supports **macOS ARM64 only**; other platforms need a separately reviewed runtime, not an automatic provider fallback.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-api.lock
python3 scripts/configure_local.py
docker compose --env-file .env.kairos.local up -d --wait
npm --prefix dashboard ci
docker build -f Dockerfile.api -t kairos-api:build003 .
# Case preparation resolves this compatibility tag to an immutable image ID.
docker tag kairos-api:build003 kairos-api:build002
docker build -f Dockerfile.investigation-django -t kairos-investigation-django:build003 .
PYTHONPATH=. .venv/bin/python scripts/prepare_investigation_cases.py
.venv/bin/python scripts/setup_investigation_runtime.py
```

Reuse occupied project ports and existing frozen image IDs on this installation. **Do not retag its historical build002 image or rerun preparation over frozen evaluation material.** On a fresh machine, rebuilding an image can change its ID even with pinned inputs. Preparation writes a new manifest/preflight receipt. Preserve the shipped evaluation lock and ledger. For the recorded Django candidate, use `--image kairos-investigation-django:build003` to explicitly record the reviewed replacement image. The reproduction CLI allows an image-only provenance difference, requires all other case material to match, and reports the environment change. A rebuilt environment is not the byte-identical original evaluation.

Provision Keycloak using [infra/identity/README.md](infra/identity/README.md). Existing ignored credentials and memberships are reused. Then start separate terminals:

```bash
python3 scripts/run_local.py api          # 127.0.0.1:8100
python3 scripts/run_local.py web          # 127.0.0.1:3100
python3 scripts/setup_investigation_runtime.py --serve  # 127.0.0.1:8130
python3 scripts/run_local.py investigator
```

Open `http://127.0.0.1:3100`. Public inspection works while inference is stopped. Keep heavy frontend builds separate from inference on an 8 GB host: swap growth previously triggered the enforced free-space reserve. Added runtime storage is about 2.1 GB; the reviewed Django image is additional. Persistent investigation resources remain below 6 GiB at the recorded checkpoint.

## What the worker can do

Four tools: literal `search`, bounded `read_file`, exact source replacements through `propose_patch`, and registered `run_checks`; plus a final-result action. Version 3 uses the runtime's actually enforced nested JSON schema contract. Patches are mechanically rendered as unified diffs, never semantically repaired by the host.

Each loop has six model calls, two proposals, two checks and ten minutes. Patches are restricted to approved Python source, three files and 200 changed lines. Check containers run as UID 10001 with no runtime network, credentials or Docker socket, two CPUs and 1 GB memory. Dependencies are prepared separately. Source snapshots and the working checkout stay untouched.

PostgreSQL commits request identity before 202, fences workers using database-clock leases, and retains ordered requests/results. Capture files are fsynced before references commit. Captured responses can continue after recovery; uncertain dispatches are never repeated automatically. Replay performs no execution. Records default to private; admin publication exposes read-only evidence and downloads.

## Active module map

| Module | Responsibility |
| --- | --- |
| `kairos_api/investigations/` | Contracts, registry, path and patch validation, sandbox, durable repository, model adapter, worker, scoped routes |
| `kairos_api/app.py`, identity modules | API composition, OIDC sessions, memberships and role checks |
| `cases/` | Frozen public provenance, selection exclusions, source/test/reference digests and recipes |
| `scripts/*investigation*` | Runtime preparation, case qualification, descriptive evaluation, crash drills and reproduction |
| `dashboard/app/investigations/`, investigation components | Public ledger, comparison, patch/context/check inspection and private workbench |
| `evidence/build003/` | Complete attempt ledger, frozen versions, actual local checks and screenshots |
| Existing jobs/effects/evaluation modules | Preserved single-dispatch jobs and historical synthetic demonstrations |

Legacy `harness/`, `engine/`, `ingest/` and `storage/` are outside the active path. This installation uses local filesystem artifacts, not S3/WORM. Docker socket access belongs only to the trusted host worker; candidate containers never receive it. Hidden verification is outside model tools and source access. Candidate Python runs inside a verifier containing its tests: this does not establish secrecy against adversarial code or a hardened multi-tenant execution service.

## Verification and limits

```bash
KAIROS_TEST_IDENTITY_PROVIDER=1 KAIROS_TEST_INVESTIGATION_DOCKER=1 KAIROS_TEST_INVESTIGATION_PROVIDER=1 python3 scripts/run_local.py test
npm --prefix dashboard run test:boundary
npm --prefix dashboard run lint
npm --prefix dashboard run typecheck
npm --prefix dashboard run build
```

The optional live test flags require the prepared provider, Docker images and running local model. Isolated fixture tests do not count as model repairs. [Build 003](docs/BUILD_003.md) records executed checks, setbacks, selection scope and remaining limits. [BRAIN.md](BRAIN.md) is the compact continuation map. [Architecture](ARCHITECTURE.md) explains the decisions. Earlier evidence and [the build002 README](docs/README_BUILD_002.md) remain preserved.

Six historical human-localized cases are a descriptive sample, with possible public-issue training contamination. One simple repair establishes this workflow's ability to capture and independently verify a real candidate, not broad model competence. Public hosting, external adoption and model research remain separate milestones. Local hashes detect mismatches against recorded references; they do not prove immutable history. The CI definition has not been run on a hosted runner in this session.
