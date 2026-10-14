# Kairos build005 delivery report

Updated 2026-10-13. The reviewer release makes Kairos runnable from a clean source snapshot and inspectable without live inference. Fresh full-stack acceptance, recorded inspection, repair reproduction and affected image checks passed. Model results remain unchanged and visible.

## Delivered behavior

`python3 -m scripts.reviewer demo|fullstack|repair|check|stop` is the documented entry point. Demo installs locked website dependencies and serves genuine captures without Docker, database, identity or model. Fullstack creates a separate local PostgreSQL/Keycloak/API/website installation with private generated credentials and preserved volumes. Repair prepares pinned source and applies the saved model patch in a disposable verifier. Check records actual outcomes. Stop verifies ownership before touching resources.

The website selects explicit live or recorded authority. Recorded mode states its origin, validates evidence and disables login/private execution. It retains readable timeline, source/context inspection, before/after patch, checks, comparisons and original downloads. Live errors remain errors; no automatic fallback fabricates saved results.

The review path is problem, proposed change, independent checks, engineering decisions and evidence. The package contains 48 genuine published records and 683 original blobs. It shows the original Django success and complete newer 36-attempt comparison, including failures, infrastructure outcomes and incomplete timing.

## Fresh acceptance

The curated source snapshot began without runtime, environment files, installed dependencies or a virtual environment. Acceptance used Node 24.19.0/Python 3.14.2 on macOS. The entry point requires Node 24/npm and Python 3.12 or newer; fullstack/repair require Docker. Initial dependency/source preparation requires network access; isolated verification has no runtime network.

| Check | Observed result | Receipt |
|---|---|---|
| Locked install/aggregate fullstack acceptance | Passed from clean snapshot | [acceptance.json](../evidence/build005/acceptance.json) |
| Active backend | 229 passed, six skipped, zero failures | Acceptance backend entry/test log |
| Boundary/client/recorded integrity | Four/three/eleven tests passed | Acceptance frontend entries |
| Lint/types/production builds | Passed in recorded/live modes | Acceptance frontend/build entries |
| Recorded browser | Four journeys passed: genuine evidence, cost/incomplete timing, private closure, keyboard/390 px/errors | Acceptance recorded-browser entry |
| Actual OIDC browser | Four journeys passed: login/logout/commands/publication, retries/conflicts/pagination, viewer denials, tenant isolation | Acceptance live-browser entry |
| Repeated setup |48 archive records retained; zero active commands after cleanup; zero interactive model calls | [setup-repeatability.json](../evidence/build005/setup-repeatability.json) |
| Fresh saved repair |110 tests, one skip; outcome reproduced | [repair-reproduction.json](../evidence/build005/repair-reproduction.json) |
| Existing fixture browser regression | Eleven journeys passed again | [legacy-browser-tests.txt](../evidence/build005/legacy-browser-tests.txt) |
| Packaging failure checks | Five passed, including corrupt/traversing/duplicate archive rejection | [packaging-negative-checks.json](../evidence/build005/packaging-negative-checks.json) |
| Original installation and scoped shutdown | Original database 109/object 1,145 counts preserved; owned volumes retained | [original-preservation.json](../evidence/build005/original-preservation.json), [scoped-shutdown.json](../evidence/build005/scoped-shutdown.json) |
| Actual API/web containers | All 21 checks passed; API UID 10001/web UID 1000 | [docker-smoke.json](../evidence/build005/docker-smoke.json) |

Six backend skips are explicit opt-ins: four checks for the old local identity installation, one actual model-schema probe and one real Docker-isolation probe. New actual OIDC journeys passed separately. Build004 retains separately passing model/isolation probes. Inactive prototypes are outside the active suite. No inference ran during delivery acceptance.

The separate repair used source revision `e7fd69d051eaa67cb17f172a39b57253e9cb831a` and the recorded model patch. Source and verification digests matched. The rebuilt image differs from the historical image; its receipt reports `environment_changed: true`. This proves saved patch behavior in the declared new environment, not identical historical image bytes or a fresh model attempt.

The final sanitized source snapshot also installed and launched successfully with Docker off. Its four recorded browser journeys passed again; build-generated type paths were pinned and source fingerprints remained stable. Packaging failure and correction are retained in `packaging-reseal.json`; the final external seal binds archive, index and manifest bytes.

The final checklist/inventory is [final-checks.json](../evidence/build005/final-checks.json). Public screenshots and sanitized logs live under `evidence/build005/`; credentials, sessions and authentication captures are excluded.

## Preservation and distribution

Before delivery changes, 212 build004 source files and 386 evidence fingerprints were verified. Source was archived separately; historical evidence/manifests remain unchanged. [Preservation receipt](../evidence/build005/build004-preservation.json) records provenance and archive size/hash.

Seven raw files totaling 280,334,843 bytes are distributed losslessly in a 9,586,236-byte archive. The [raw index](../evidence/build005/historical-raw-index.json) retains original paths/sizes/SHA-256. Extracted bytes matched originals; original local files remain intact. Compression does not replace failure evidence with an aggregate.

`scripts/verify_delivery005.py` verifies manifests and archive contents; add `--bundle` to include the prepared publication archive. Five negative packaging checks passed.

The publication snapshot excludes credentials, runtime, sessions, dependencies, databases and model weights. Delivery files have a separate manifest. Hashes establish consistency relative to the manifest, not signed provenance or privileged-rewrite resistance. Snapshot/description are prepared for review; no GitHub push, public hosting or hosted CI run is claimed.

## Earned claims retained

Build004 measured **435,270 local control-plane requests over 42 minutes**, zero unexpected errors and zero HTTP 429 responses and ten-client soak acknowledgement p95 **275.19 ms**. Actual HTTP/PostgreSQL traffic used isolated fixture identity/tasks. It did not measure inference/OIDC throughput, production scale or dedicated-host saturation. Failed and interrupted runs remain visible.

Prior real SIGKILL drills resumed captured work or preserved uncertain dispatch without another model call. Prior fresh local restore checked 109 investigations, 1,145 objects and 1,546 references. These experiments retain their original receipts; packaging did not alter their execution modules or rerun them.

Build003 earned two verified attempts on one distinct Django case, solved by both single call and loop. The newer frozen study remains **0/36 verified evaluation repairs**, across twelve cases/three strategies; all 78 development/evaluation attempts remain recorded. Public cases may be contaminated; source regions were manually localized. Unknown interrupted usage is not zero. No broad-repair or loop-superiority claim follows.

## Handoff

Start `python3 -m scripts.reviewer demo`. Stop it, then run `python3 -m scripts.reviewer check --fullstack` and `python3 -m scripts.reviewer repair`. Finish `python3 -m scripts.reviewer stop`. Reviewer ports are 55434/8090/8310/3310. No Lenovo, model weights, API key or hardware purchase is needed.

Use [reviewer instructions](REVIEWER_005.md), [claim map](CLAIMS_005.md), [five-minute demonstration](DEMO_005.md) and [decisions](../DECISIONS.md). Personal ownership still requires explaining/debugging the implementation. Production deployment, outside adoption and model research remain separate milestones, not unfinished local-delivery requirements.
