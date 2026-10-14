# Kairos build006 follow-up report

Updated 2026-10-13. Build006 corrects a reproduced investigation-harness defect and packages every new repair attempt for inspection. The recorded package contains 76 investigations and 965 original artifact blobs: the original 48 records are retained, and 28 new captures are added. Fresh repair validation remains **0/10**. Local software acceptance passed. The separate manifest, publication index and seal bind this release; verify them with `python3 -m scripts.package_release006 --verify`. Model effectiveness remains a separate failed outcome.

## What changed, and why

The failure audit found that v4 supplied initial original source only before tool observations existed. After the first search, the source disappeared from model context. The action schema then removed `propose_patch` when no visible source references remained. This affected **55 of 66 loop dispatches** in the frozen build004 evaluation. All 60 searches returned no matches; 36 repeated an identical query. These are captured harness failures, not inferred model intentions. The audit does not establish how many repairs an unaffected model would have achieved.

V5 preserves initial source independently of rolling tool history. Context keeps the issue, remaining budgets, latest check result and original source regions. Exact-fragment edits use short source handles bound to captured source digests and bounds. The sandbox mechanically creates patches only after verifying the original source, approved paths, fragment uniqueness, edit size and syntax. Rejected edits do not consume an applied-patch slot. Accepted patches receive immediate registered checks; a failed check reaches the next model call when budgets remain.

Generation settings are captured in the durable configuration. Old versions and outcomes remain intact. V6 is a separate reasoning profile using the same Qwen3 weights with 8,192 context tokens, 2,048 maximum output tokens, temperature 0.6, top_p 0.95, presence penalty 0.5 and thinking enabled. It retains the loop ceiling of six model calls, two applied patches, two checks and 600 seconds. V6 results are development evidence, not a rerun or replacement of frozen v5 validation.

The readable inspector displays retained original source and selected source blocks separately from model prose, candidate patches and independent checks. The `/follow-up` page provides the audit, profile results, per-attempt links and downloads. The homepage leads with an earned development demonstration; `/study` retains the earlier 0/36 comparison. Recorded mode requires no login, database or inference and performs no execution.

## Complete new attempt ledger

| Cohort | Attempts | Verified attempts | Captured calls | Check runs | Captured tokens | Recorded elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Coder v5 development | 6 | 2 | 9 | 7 | 15,721 | 189.070 |
| Qwen3 v5 development | 6 | 2 | 11 | 8 | 22,037 | 143.285 |
| Qwen3 thinking v6 development | 6 | 2 | 8 | 5 | 16,673 | 505.494 |
| Frozen baseline-v5 validation | 5 | 0 | 5 | 3 | 7,486 | 156.492 |
| Frozen loop-v5 validation | 5 | 0 | 18 | 6 | 31,696 | 256.849 |

All six verified development attempts cover **one distinct case**, `django__django-11066`. Its public issue explicitly proposes passing `using=db` when saving the content type. Entry files were human-localized. The demonstration shows that the captured model proposal passed independent checks in the declared environment; it does not demonstrate novel diagnosis, representative repair competence or a loop advantage.

V6 development contains two verified attempts, two failed-check attempts, one invalid response and one unknown dispatch. The Requests baseline corrected the target binary-payload regression but failed an existing bytes-parameter test, so the overall repair is unsuccessful. A truncated reasoning response is not a valid patch. An uncertain dispatch is not retried and its unavailable consumption is not counted as zero. Token totals include captured usage only. Elapsed totals describe recorded attempts, not a benchmark of concurrent service throughput.

## Fresh qualification and frozen validation

The planned qualification target was six cases. Five qualified: two Django, two pytest and one Requests. The remaining Requests regression did not reproduce on Python 3; the historical defect requires Python 2. The target shortfall is retained, and the case was not replaced based on model results. Missing `toml` was resolved in a separate reviewed pytest image under a new identity; prior failed qualification/setup receipts remain available.

Baseline regression failure and maintainer reference success qualified cases before model execution. Reference patches and hidden verification stayed outside model tools. The five-case validation cohort was locked before execution and evaluated once with the selected v5 profile.

| Case | Baseline-v5 | Loop-v5 |
| --- | --- | --- |
| `django__django-11133` | Failed checks | Failed checks |
| `django__django-11141` | Invalid patch | Invalid patch |
| `psf__requests-2317` | Failed checks | Failed checks |
| `pytest-dev__pytest-7324` | Failed checks | Failed checks |
| `pytest-dev__pytest-7432` | Invalid patch | Invalid response |

Both strategies verified zero cases. Loop-v5 used 18 calls and six checks, compared with five calls and three checks for baseline-v5. This cohort provides no earned repair improvement from the loop. It is a small curated sample with possible public-training contamination and explicitly scoped tests; it is not a SWE-bench leaderboard result. No validation cases were relabeled, replaced or used for retuning after their outcomes.

## Acceptance and preservation

| Area | Actual build006 result | Receipt |
| --- | --- | --- |
| Backend on real PostgreSQL | 291 passed, six explicit opt-in skips; two dependency deprecation warnings | `final-checks.json`, `backend.xml` |
| Frontend | 18 unit tests; lint, types and production build passed | Individual check receipts and clean-checkout aggregate |
| Recorded browser | Six journeys passed, including source/context, comparison/filter, downloads, errors, keyboard and 390px | `clean-recorded-browser.json`; screenshots |
| Real identity browser | Four journeys passed: login/logout, roles, tenant isolation, durable retries, pagination and scoped commands | `live-browser-summary.json` |
| Built images and isolation | 21 API/web smoke checks and one real sandbox opt-in test passed | `docker-smoke.json`, `container-isolation.xml` |
| Recovery and restoration | Two actual SIGKILL fixture drills, zero redispatch; 82 investigations and 928 distinct referenced objects restored | `crash-recovery.json`, `restore-with-blobs.json` |
| Clean source | Locked installation and documented recorded-only command passed; 192 backend passed/107 explicit skips without database | `clean-checkout-acceptance.json`, `clean-checkout-summary.json` |
| Reproduction | Fresh pinned Django10914 source and saved patch: 110 tests, one skip; image difference disclosed | `repair-reproduction.json` |
| Dependency advisories | Zero known npm and pinned Python advisories at this check | `npm-audit.json`, `python-audit.json` |
| Preservation | Original 48 records/683 blobs byte-identical; 448 historical evidence files match build005 archive | `package-validation.json`, `historical-preservation.json` |
| Distribution | Separate sanitized manifest/index/archive; exact verification required | `manifest.json`, `publication-index.json`, `publication-receipt.json` |

Docker Desktop and the owned inference server were confirmed off after the user reported host heat. The reasoning pilot finished before shutdown. No volume or image was deleted, and no interrupted/unknown dispatch was automatically retried. Required container checks finished, owned containers were stopped, and Docker Desktop was shut down. The reviewer website needs neither Docker nor inference. No new inference ran during acceptance.

Build004's capacity, crash-recovery and restoration evidence is reused with its original scope. It measured 435,270 local control-plane requests over 42 minutes, zero unexpected errors and ten-client acknowledgement p95 275.19 ms. The original failed soak remains preserved. Build005 reproduced the original Django10914 saved repair against 110 tests with one skip in an explicitly rebuilt environment. These claims identify their original release; they are not new build006 experiments. The frozen build004 repair comparison remains 0/36, and all 78 development/evaluation attempts remain retained.

## Review of MiroFish

[MiroFish](https://github.com/666ghj/MiroFish) was inspected at commit `7657031ac01184afe2cb220f5ee3545573b5e843`. Its product simulates social/scenario agents from seed material and produces reports; it does not supply repository repair or an independent source-patch verifier. The useful contribution is a staged inspection path with evidence connected to outcomes. Kairos retains typed tool captures, PostgreSQL durability and local pinned inference. No code, prompts, assets or branding were copied, and no MiroFish dependencies ran. See [the review](MIROFISH_REVIEW_006.md).

## Evidence map and claim limits

- [Failure audit](../evidence/build006/failure-audit.json): exact captured dispatch/action counts and the source-retention diagnosis.
- [Qualification](../evidence/build006/qualification-toml-reuse/qualification.json), [validation lock](../evidence/build006/validation-lock.json) and [validation summary](../evidence/build006/validation/summary.json): cases, exclusions, configuration/source snapshots and every fresh outcome.
- Development summaries: [Coder v5](../evidence/build006/pilot-coder-r1/summary.json), [Qwen3 v5](../evidence/build006/pilot-qwen3-r1/summary.json), [Qwen3 thinking v6](../evidence/build006/pilot-thinking-r2/summary.json).
- [Presentation receipt](../evidence/build006/presentation.json), [public aggregate](../dashboard/public/follow-up/results.json) and [heat/shutdown receipt](../evidence/build006/heat-shutdown.json).
- [Reviewer guide](REVIEWER_006.md), [preserved build005 report](FINAL_REPORT_005.md), [decisions](../DECISIONS.md) and [working brain](../BRAIN.md).

The justified new claim is a reproduced context/action defect, a source-bound protocol correction and inspectable outcomes. Broad repair effectiveness, loop superiority, production scale, customer adoption and model research remain unearned. Hashes establish consistency against the trusted manifest, not signed provenance or immunity to privileged history rewrites. Candidate Python shares the verifier environment; adversarial test-forgery resistance remains unproven. The software release is complete against its declared local acceptance criteria. The AI repair target is not met. The separate architecture review records this distinction and the security/adoption/ownership limits.


## Final review and handoff

Read [the architecture assessment](ARCHITECTURE_REVIEW_006.md), [claims and résumé bullets](CLAIMS_006.md), [five-minute demo](DEMO_006.md) and [reviewer guide](REVIEWER_006.md). The assessment supports a strong early-career SDE/AI infrastructure discussion, with a failed broad-repair claim. No outside adoption, public hosting or personal code ownership is inferred.

Acceptance failures remain under `evidence/build006/acceptance-failures/`: a pre-completion packaging invocation, strict negative-test message matching, a browser accessible-name selector and a unit-test/live-port collision. Corrected runs have their own receipts. Environment/test failures are not counted as model repairs or silently removed. Full PostgreSQL and clean recorded-only invocations remain separate; their test counts must not be combined into a fictional single run.
