# Resume claims and their evidence

Every bullet below is backed by a file in this repository. The "limit" column is what an interviewer will
probe; say it before they ask.

## The one-line project summary

> Kairos: a full-stack AI code-repair platform. It reproduces real GitHub bugs in sandboxed Docker, has an LLM
> propose patches through a journaled agent loop, and accepts a patch only when the project's own hidden tests
> pass. Free hosted Nemotron 3 Ultra fixed 3 of 7 never-seen SWE-bench Verified Django bugs.

## Resume bullets

### AI engineer / applied ML

| Bullet | Evidence | Limit |
| --- | --- | --- |
| Built an agentic code-repair loop (search, read, run reproduction, SEARCH/REPLACE edit, self-test) that fixed **3 of 7 unseen SWE-bench Verified bugs** and **4 of 5 development bugs**, scored by hidden tests in pinned Docker. | `evidence/benchmark025/` (captures, receipts, `scores.json`, hash manifest); `/benchmark` page | 12 cases total; public 2020 fixes may be in model pretraining; oracle code regions provided |
| Diagnosed that a 4-bit 14B model on a free T4 (3,539-token budget, 8 calls) capped repair at **0-2 of 5**; same harness with a hosted 550B model reached **4 of 5** at $0 cost. | `evidence/benchmark025/qwen14b-run*/`, `nemotron-ultra-dev/`; `docs/REPAIR_REDESIGN_025.md` | Model comparison on 5 inspected cases; not a controlled ablation of size alone |
| Found and fixed harness failure modes with replayed captures: 6 of 9 reproduction scripts crashing on Django setup, a fail-before/pass-after self-test rule, unparsed action formats. | `docs/REPAIR_REDESIGN_025.md` addenda 6-7; `tests/test_repair_loop025.py` | Development-set engineering; frozen validation and locked holdout not yet run |
| Kept benchmark separation: development / frozen validation / locked holdout; model chosen on development, then one untuned run on fresh cases; protected cases refused by the CLI. | `scripts/localization_dev024.py`, `scripts/repair_case.py` (`pick`), `tests/test_repair_case.py` | |
| Fine-tuned Qwen2.5-Coder-14B with QLoRA on free Colab/Kaggle GPUs with resumable checkpoints; reported the negative result (0/20 unseen for base and adapter). | `README.md` (unseen023), `evidence/closeout020/` | Adapter did not generalize; reported as a negative result |

### Software engineer (backend / full stack)

| Bullet | Evidence | Limit |
| --- | --- | --- |
| Built a Next.js/TypeScript, FastAPI and PostgreSQL platform with a durable job worker: command receipts committed before HTTP 202, database-clock leases, fencing of stale workers, and recovery that never repeats an uncertain model call. | `ARCHITECTURE.md`, `kairos_api/investigations/worker.py`, `DECISIONS.md` | Single-region local deployment |
| Load-tested the control plane: **435,270 HTTP requests over ~42 minutes, zero unexpected errors; 275 ms acknowledgement p95, 17 ms read p95**. | `evidence/build004/capacity-summary-final.json`, `docs/CAPACITY_004.md` | Local closed-loop clients, not production traffic; inference excluded |
| Shipped **1,449 automated backend tests** plus Playwright browser journeys (recorded, fault-injection and real OIDC login). | `tests/`, `dashboard/e2e/`, `evidence/build007/checks/` | Counts from local runs; CI coverage varies by suite |
| Added OIDC login (Keycloak), tenant-scoped private-by-default records, integrity-checked downloads, and a tested database/artifact backup and restore (122 investigations). | `docs/IDENTITY_BOUNDARY.md`, `evidence/closeout023/restoration.json` | Same-host recovery, not disaster recovery |
| Closed a critical Next.js advisory (unauthenticated RCE, GHSA-2464-fhr4-w9xw) by upgrading 16.4.0 to 16.4.2 with build and browser checks. | `dashboard/package.json`, `npm audit` | |

### Forward-deployed engineer

| Bullet | Evidence | Limit |
| --- | --- | --- |
| Delivered a one-command workflow a user runs on any qualified real bug: download the pinned dataset, qualify the bug in Docker, repair with a free hosted model, score independently, print the patch. | `scripts/repair_case.py`, `scripts/hosted_repair.py`, `infra/sandbox/python-in-docker.sh` | Needs Docker; Django 3.0-3.2 cases in the pinned image |
| Ran model-written code safely: no network, capped CPU, memory and processes, only the candidate tree mounted; credentials kept in a private file and never logged. | `infra/sandbox/python-in-docker.sh`, `scripts/hosted_repair.py` | Container isolation, not a VM boundary |
| Moved a stalled project from manual Colab uploads per run to fully scripted terminal runs on free providers, after researching free inference and GPU options. | `scripts/hosted_repair.py`, `docs/REPAIR_REDESIGN_025.md` | Free-tier rate limits and model availability change |
| Built a reviewer website anyone can open without an account: per-case results, the exact passing patch, and the limits next to each claim. | `dashboard/app/benchmark/`, `dashboard/e2e/benchmark025.spec.ts` | Live repair runs locally, not on the public site |

## Questions to expect, and short answers

- **Why trust 3 of 7?** The patch is re-applied to a clean checkout and judged by tests the model never sees.
  The model was fixed before the fresh run and got one attempt with no tuning.
- **Could the model have memorised the fixes?** Possibly; these are public 2020 Django fixes. That is why the
  frozen validation and locked holdout sets exist and are still untouched.
- **What failed?** The 14B model on a free T4 (0-2 of 5), a QLoRA adapter that did not generalise (0/20), and
  several harness bugs found from receipts. Each is recorded with its evidence.
