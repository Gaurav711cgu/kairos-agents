# Kairos production readiness tracker

Updated: 22 October 2026 (cycle 2: fullstack acceptance). Status values: VERIFIED (executed evidence this session),
HISTORICAL (receipt from an earlier session, not rerun), MOCK-VERIFIED (exercised with stubs only),
OPEN (permitted work remaining), BLOCKED (approval or infrastructure required).

| # | Requirement | Owner | Status | Evidence | Remaining work | Blocker | Next action |
|---|---|---|---|---|---|---|---|
| 1 | Clean installation and reproducible deployment | C | VERIFIED (with user fixes) | `evidence/acceptance024`: fresh clone of eda2565, fresh reviewer venv/node_modules from locks, `reviewer check --fullstack` passed | Commit the user's uncommitted e2e JSON-import and codesage fixes; committed HEAD alone fails recorded-browser (Node 24) and 5 codesage tests | User owns those changes | User commits their fixes |
| 2 | Authentication, authorization, tenant isolation | A | VERIFIED | acceptance024: real Keycloak OIDC browser 4/4; backend 1257 passed, 29 skipped on real PostgreSQL | none | none | none |
| 3 | Complete frontend/backend user journey | C | VERIFIED | acceptance024: recorded 16/16, fixture 11/11, live OIDC 4/4; lint, types, build pass | none (pending the user-fix commit above) | none | none |
| 4 | Real supported inference backend integrated | B | MOCK-VERIFIED | `scripts/f024_colab.py` + `tests/test_f024_gpu_mock.py` (14), `tests/test_f024_colab.py`; worker path serves Qwen3-1.7B via llama.cpp (historical) | Execute the 14B runner on a GPU | Colab GPU needs approval | Approve pilot turn one |
| 5 | Model-generated patch flows through source-bound editing, sandbox validation, independent scoring | B/C | MOCK-VERIFIED | Two-turn mock dry run on the real pilot package; `tests/test_f024_score.py`; pilot cases qualified (`evidence/localization024/f024-pilot/qualification-v4.json`) | Real captures, then Docker scoring | Pilot turn one | Approve pilot turn one |
| 6 | At least one genuine model-generated repair passes independent regression without leakage | B/C | BLOCKED | Historical 0/20 (unseen023) | Pilot, then a larger F024 if the pilot works | GPU approval | Approve pilot turn one |
| 7 | Failure cases, unsupported edits, rejected patches, exhausted budgets handled safely | A | VERIFIED | `tests/test_e2e_worker024.py` (12: budgets, unknown dispatch, duplicate-candidate stop, two identical rejections), feedback/validator tests, scope-limit classification | none | none | none |
| 8 | Worker crash recovery, timeouts, resource limits | A | VERIFIED | Recovery and deadline tests (`_run` and `run_once`: timeout before dispatch, 0 calls); Docker+PostgreSQL integration 9/9 this session; sandbox limits (network none, read-only, cap-drop, memory/pids) | A model-call timeout is classified `unknown_dispatch` by design; real-PostgreSQL deadline mapping is covered only by the general suite | none | none |
| 9 | Critical security and reliability checks | C/A | VERIFIED (static) | `docs/SECURITY_TRIAGE_024.md`: 17 `ruff S` findings, 0 REAL (SQL fragments are literals with bound values; subprocess argv lists without a shell); lead spot-checked the SQL findings | Dependency vulnerability audit (pip-audit/npm audit need network) | network audit needs approval | Optional approval |
| 10 | CI and deployment smoke tests | C | **BLOCKED (pre-existing CI failure)** | Local parity: repair010, retrieval011, loop012 and evaluation013 snapshot verifiers pass; null and planted calibration pass. `verify_measurement014` FAILS on clean extracts of both 85525fe and c357e1b: 18 unsealed added files and 8 changed sealed files from the pre-session codesage/swebench/hosting commits. Postgres, Keycloak, Playwright and acceptance007 steps need Docker or downloads | Declare a new chained seal layer (new manifest, verifier and workflow step) or revise the gate | Changes frozen evidence/CI controls; needs approval | Approve a reseal design |
| 11 | Logs, receipts, histories inspectable and reproducible | C | VERIFIED | `scripts/verify_evidence024.py`: 117 files, 0 problems; hash-bound manifests per checkpoint | none | none | none |
| 12 | Production inference availability, hardware, operating cost | B/Lead | PARTIAL | Free Colab T4 14.6 GiB, historical peak 14.42 GiB at at most 3539 tokens, mean 33.8 s per generation; the Mac cannot run the 4-bit CUDA profile; local worker path is a 1.7B model, which is a different model | Measured cost and latency of a sustained production backend | No production GPU host chosen; needs a spend decision | Owner decision after the pilot |
| 13 | Limitations and measured repair reliability documented | Lead | VERIFIED (current state) | `docs/KAIROS_STATUS_024.md`, `docs/REPAIR_ROADMAP_024.md`, `docs/F024_PILOT_MANIFEST.md` | Update with pilot results | Pilot | After the pilot |
| 14 | No unresolved critical production blocker | Lead | NOT MET | Rows 1, 4, 5, 6, 12 blocked | see above | approvals | see above |

**Honest verdict:** not releasable as an AI repair product. Repair capability is unproven
(0/20 historical, 0 new generations). The infrastructure is engineering-complete for the
approval-gated pilot.
