# Kairos interview defense

Updated 2026-10-12 for build004. This guide is not evidence of a passed interview or personal code ownership. Build003 sources, receipts and tagged images remain preserved. See `FINAL_REPORT_004.md` for final execution receipts and `REPAIR_STUDY_004.md` for the complete new comparison.

## Accurate opening

“I built a local full-stack repository investigation workbench. It runs a bounded local model workflow, records requests and results durably, proposes source-only patches in disposable copies, and checks them against reproduced regressions and selected existing tests. I focused on recovery and inspectable evidence. The original study repaired one distinct historical case with both strategies. The new frozen comparison attempted twelve cases with three strategies and earned zero verified repairs. I have not demonstrated broad repair competence or a loop advantage.”

Disclose AI assistance accurately. Describe your own decisions, reviews, changes and debugging; do not claim unaided authorship if that is untrue.

## Five-minute working demonstration

1. Open `/investigations/8b03a42f-149e-4d44-937f-0d61636f6042`. Explain the original Django file-permissions defect, pinned revision and observed outcome.
2. Show the one-line before/after patch. Explain what `0o644` means and why the selected tests validate this case. State that the suite ran 110 tests with one skip.
3. Expand the captured model response and independent check output. Distinguish model proposal, patch acceptance and verified repair.
4. Show the single-call comparison: both solve this case; the loop costs three calls and 3,493 tokens versus one call and 1,852 tokens. Do not generalize from one case.
5. Open `/investigations/357a7977-033c-447d-8d88-e72408d7a440`. Show the bad patch and failed checks. A failure is preserved rather than relabeled as success.
6. Download the patch/evidence. If time permits, reproduce the saved repair using the command below. Public inspection and reproduction require no live inference. Private queue/cancel/fork/replay uses local OIDC and the separate worker; interactive attempts do not enter the frozen cohort.

From the prepared repository root:

```bash
PYTHONPATH=. .venv/bin/python scripts/reproduce_investigation.py --record evidence/build003/django__django-10914-baseline-v3.json --output /tmp/kairos-interview-repair.json
```

This uses the recorded candidate and fresh source copy. It does not call the model or database. Do not retag historical images, rerun preparation over frozen material, or rerun validation to obtain a better-looking demonstration.

## Questions to defend in the code

| Lead's question | Required explanation | Source |
| --- | --- | --- |
| When is a command acknowledged? | PostgreSQL commits command identity and configuration before 202. A conflicting retry returns 409. It does not acknowledge an in-memory queue as durable. | `kairos_api/investigations/repository.py`, `routes.py` |
| What if a worker dies during inference? | Intent exists before dispatch. Uncaptured inference remains unknown and is not automatically repeated. A captured response can continue without another dispatch. This sacrifices automatic completion under uncertainty. | `worker.py`, `repository.py` |
| Why database time and fencing? | One clock governs leases/deadlines. An old owner/token cannot authorize new writes after cancellation or reclaim. Explain which transaction performs the check. | `repository.py` |
| Are database and artifact writes one transaction? | No. The blob is fsynced before its database reference commits. A crash can leave an orphan blob; a committed reference should point to durable data. Hash verification detects mismatches, not malicious administrator rewrites. | `kairos_api/model_runtime.py`, investigation repository |
| Why no Go ingestion service? | One active investigation has no measured ingestion bottleneck. Another database/service adds failure boundaries. Legacy ingest has unresolved request-receipt/drop semantics. | `docs/LEGACY_REUSE_REVIEW.md` |
| Can an agent run arbitrary code on the host? | No arbitrary shell tool; registered checks run disposable Docker copies with resource limits, non-root identity and no runtime network/credentials/socket. The trusted host worker still controls Docker. | `contracts.py`, `patches.py`, `sandbox.py` |
| Are hidden tests secure from hostile candidate Python? | Not proven. Tests are outside model tools/source, but candidate Python shares the verifier container/process environment. Test-runner forgery resistance is not established. | `sandbox.py`, `docs/BUILD_003.md` |
| What is replay versus fork? | Replay reads captured evidence and executes nothing. Fork creates a fresh case run with parent lineage; it does not resume arbitrary historical model state. | `routes.py`, `worker.py` |
| Where is tenant authority established? | Validated OIDC/server session plus explicit database membership. Browser-supplied tenant/role values do not grant access. Publication requires admin authority. One issuer is supported. | `kairos_api/identity.py`, app dependencies |
| How do you justify the model result? | Original six-case study remains separate. Build004 qualified eighteen cases before model execution, used six for development and locked twelve for one evaluation of three strategies. All36 attempts earned zero verified repairs; infrastructure failures remain included. Public training contamination and human localization limit interpretation. | cases, evaluation lock and attempts ledger |
| What proves frontend depth? | Real private command flows, public evidence inspection, responsive layout, keyboard selection and honest errors. Build004 adds stale-response and uncertain-command regressions, private evidence inspection, visible polling with backoff, and isolated browser journeys. Real OIDC/tenant browser journeys have separate receipts. | investigation components, browser acceptance |
| What would change for many customers? | Define demand, isolation and fairness goals first. Then partition execution capacity, quotas and queues, strengthen sandbox/verifier trust, and measure latency/cost. Current single global slot is deliberate, not a scalable-service claim. | architecture and build report |

## Executed checks and boundaries

- Backend: 213 passed, two opt-in skips and two dependency warnings in the full run. Both real provider/container opt-in checks passed separately. These are separate invocations.
- Frontend: seven client/boundary tests, eleven isolated browser journeys and three real OIDC journeys passed. Actual production public inspection covered saved evidence, comparison costs, downloads, keyboard selection, errors and 390px layouts. Final lint/types/build receipts are listed in the release report.
- Two real SIGKILL drills recovered with zero additional model dispatches. The intent drill dies before HTTP send; lease expiry is explicitly injected after process death. This does not prove every failure interleaving or exactly-once external inference.
- Consistent database/artifact restoration passed for 109 investigations, 1,145 distinct objects and 1,546 references. This is same-host recovery, not offsite disaster recovery or a production recovery-time guarantee.
- All eighteen new cases reproduced baseline failure and reference success before model execution. The preserved build003 model repair reproduced with 110 tests and one skip. Reference fixes never count as model outcomes.
- Non-root API/web image smoke and dependency audits passed. Read the capacity report for every run, including the original failed soak. Fixture traffic measures HTTP/PostgreSQL control-plane work, not inference or OIDC throughput.
- Lenovo inference, hosted CI, public HTTPS deployment, adversarial test-forgery resistance and outside-user adoption remain unverified. An unavailable historical verifier image and context-overflow records remain infrastructure failures in the study; do not relabel them as evaluated model failures.

## Personal ownership gate — not yet assessed

Without reading this guide, explain the browser-to-worker-to-database path, the uncertain-dispatch tradeoff, artifact commit ordering and the results of both studies. Find the relevant code and a test for each invariant. Then fix an unfamiliar defect, run an appropriate test and explain the tradeoff. A mock defense and coding/debugging session is required before claiming this gate passed.

AI-assisted implementation does not invalidate the project. Personal ownership requires understanding, truthful attribution and the ability to change and debug it. More features cannot substitute for that demonstration.

## Build004 interview demonstration (five minutes)

1. **0:00–1:00:** Open the strongest earned published repair. Explain its source revision, reproduced failure, actual model patch and independent check. A reference repair is never a model result.
2. **1:00–2:00:** Inspect context selection, omitted regions and the next model action. Compare calls, tokens, elapsed time and failed outcomes across frozen strategies. Distinguish the original six-case study from the 18-case qualification and twelve-case evaluation.
3. **2:00–3:00:** Sign in, queue a private investigation, cancel it, fork it and replay the saved steps. Explain the stable command identity, durable receipt, tenant membership and admin publication boundary. A repeated uncertain create uses the same identity.
4. **3:00–4:00:** Explain one real crash receipt: a pending dispatch stays unknown; a captured result resumes without another model call. Find database-clock lease checks and the fencing token in the repository. Explain artifact fsync before database references commit.
5. **4:00–5:00:** Open capacity evidence. State which runs passed and which failed. Show the outage report, benchmark corrections and measured limits. Explain what a future release would need before making a stronger claim.

Do not memorize the answers. Trace one browser request in code, find one invariant test and debug an unfamiliar defect without this guide. This personal mock defense remains unassessed until the candidate performs it.
