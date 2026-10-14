# Kairos reviewer guide

The delivery entry point is `python3 -m scripts.reviewer demo|fullstack|repair|check|stop`. Run commands from the repository root. Recorded inspection, live authenticated operation and repair reproduction are separate modes with explicit requirements.

## Requirements

Use Python 3.12 or newer and Node.js 24 with npm on macOS or Linux. The demo installs locked website dependencies and runs the real interface against genuine captures; it needs no Docker, database, credentials or model. Initial dependency installation requires network access. The full-stack and repair commands also require Docker. Repair preparation downloads the pinned historical Django source and builds reviewed dependencies before isolated checks execute.

No paid API, public hosting or Lenovo is required. Fresh reviewer state is stored under the ignored `.runtime/reviewer005/` directory. The original application runtime, credentials, database and historical images remain separate.

## Inspect the website

```bash
python3 -m scripts.reviewer demo
```

Open the printed URL, normally `http://127.0.0.1:3310`. The website shows “Recorded investigations. No live execution.” Open the original repair, inspect its source and context, compare the patch, read independent checks and download the evidence. The new frozen study retains all 36 evaluation outcomes, including zero verified repairs. The capacity page preserves failed and successful runs separately.

Recorded mode validates package files, record schemas, ordered steps, artifact references and original captured bytes. Corruption fails explicitly. A missing investigation shows unavailable evidence. Private commands and login are disabled, and live mode never falls back silently to these records.

## Operate the authenticated system

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer fullstack
```

The isolated environment uses PostgreSQL port 55434, Keycloak port 8090, API port 8310 and website port 3310. Resources carry an owner identity. Repeated setup reuses matching owned resources; conflicts are rejected rather than replacing another installation.

Generated credentials live in mode-0600 `.runtime/reviewer005/identity.local.json`. Open that file locally when signing in; do not paste it into an issue, terminal transcript, screenshot or public evidence bundle. Admin and viewer accounts share a workspace; the operator account uses a different tenant. Published historical records occupy a separate archive workspace.

The default full-stack environment starts no model or worker. Queue/cancel/fork operations exercise durable API behavior without inference. Replay returns captured steps with zero model calls and tool execution. Publication requires an admin role. The existing investigation execution modules and frozen study remain available separately.

## Reproduce the earned repair

```bash
python3 -m scripts.reviewer repair
```

Preparation validates the pinned source revision and tree hash, uses the original recorded model patch and rebuilds the reviewed verifier recipe under a new delivery tag. The receipt reports any image-digest difference rather than presenting the rebuilt image as the old environment. Verification runs in a disposable workspace; the source checkout stays untouched. The original run reported 110 tests with one skip. The new receipt records what this reproduction actually ran.

The maintainer patch is verification provenance, never the agent result. This command uses saved model output; it needs no model weights, live inference, API key or identity service.

## Acceptance and shutdown

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer check --fullstack
python3 -m scripts.reviewer stop
```

The explicit full-stack check records real exit statuses and logs, including fresh PostgreSQL/OIDC journeys. Repair reproduction is a separate command and receipt; run it as well for complete delivery acceptance. The delivery index is `evidence/build005/final-checks.json`; individual receipts describe their environment, counts, failures and skips. The old measured capacity and frozen model studies are reused because delivery packaging does not change their execution modules.

Browser acceptance covers recorded downloads and comparison, keyboard operation, 390px layouts and explicit unavailable states. Real full-stack journeys use actual OIDC sessions for login/logout, roles, tenant boundaries, stable retries, conflicting commands, pagination, queue/cancel/fork, replay and publication. Authentication state, traces and credentials are not exported.

`stop` targets only reviewer-owned processes and containers. It preserves volumes and recorded evidence. It does not reset the original installation or stop unrelated Docker services. Stop the current reviewer mode before switching modes on port 3310.

## Evidence and limits

Run `python3 -m scripts.verify_delivery005` to compare distributed files and historical archive members against their recorded hashes. The separately delivered publication archive also has `publication-index.json` and `publication-receipt.json`; `--bundle` verifies those when all three files are present. The archive excludes its own index and receipt to avoid a circular fingerprint. Raw measurements can be restored to their historical paths with `tar -xzf evidence/build005/historical-raw.tar.gz` after verification; the original bytes and paths are retained.

Use `docs/CLAIMS_005.md` for résumé wording and claim boundaries, and `docs/DEMO_005.md` for a five-minute review. Local fingerprints establish consistency relative to the manifest, not signed provenance or administrator-proof immutability. The newer study does not establish broad repair competence or loop superiority. Public deployment, customer adoption and personal debugging ownership remain separate claims.
