# Kairos delivery decisions

Updated 2026-10-13. This is the build005 decision log. Earlier choices remain in [ARCHITECTURE.md](ARCHITECTURE.md) and [the planning log](docs/planning/DECISIONS.md). Frozen build003/build004 source and results remain preserved.

## Fixed scope and acceptance

The release must work from a clean source snapshot, expose genuine investigations through the website, reproduce the earned Django patch and connect every résumé claim to a receipt. The target is local development on the existing Mac: zero API spend, no hardware purchase and no public hosting. Lenovo inference is optional. Existing data, credentials and historical image tags must survive delivery.

Software acceptance and model performance are separate. A working website does not improve the repair score; a failed repair study does not excuse broken delivery. The newer evaluation remains **0/36 verified repairs**. Personal ownership must still be demonstrated through explanation and debugging.

## D42 — One bounded entry point

**Issue:** Manual setup assumed an already prepared machine and knowledge of several scripts.

**Solution:** Add `python3 -m scripts.reviewer demo|fullstack|repair|check|stop`. Demo installs locked website dependencies and needs no Docker, database or model. Full-stack provisions separate services. Repair prepares pinned source and a reviewed verifier. Check records actual exit statuses. Stop preserves data.

**Reason:** A reviewer should inspect useful evidence before preparing identity or inference. Separate modes prevent surprise computation and keep the student's existing hardware sufficient.

**Evidence:** [Fresh acceptance](evidence/build005/acceptance.json), [reviewer guide](docs/REVIEWER_005.md) and [repeatability](evidence/build005/setup-repeatability.json). Node 24 is checked explicitly; Python 3.12 or newer is required. Acceptance ran on macOS with Node 24.19.0 and Python 3.14.2.

## D43 — Explicit recorded authority

**Issue:** Without services, a reviewer could see unavailable records; an automatic fixture fallback could fabricate execution or authentication.

**Solution:** Add `KAIROS_EVIDENCE_MODE=live|recorded`, defaulting to live. Recorded mode serves 48 genuine published build003/build004 records, reuses the inspector and downloads, states “Recorded investigation,” and disables login/private mutations. Live outages remain errors. Dynamic rendering honors the runtime mode.

**Reason:** Saved inspection is valuable when its origin and authority are clear. It must never masquerade as active progress or invent a passing repair.

**Evidence:** [Published package](evidence/build005/published-package.json), eleven recorded-integrity tests, four recorded browser journeys and recorded-image checks in [Docker smoke](evidence/build005/docker-smoke.json).

## D44 — Original bytes and complete validation

**Issue:** Reserializing parsed JSON can change `1.0` and invalidate captured digests. An identifier alone does not validate a package.

**Solution:** Preserve original bytes. Validate hashes, sizes, schemas, IDs, ordered steps, counters, references and pinned case/configuration snapshots. Reject traversal, symlink escapes, missing objects and corruption. Recheck selected evidence on reads.

**Reason:** Downloads must contain the artifact the capture references. Schema equality cannot replace byte integrity, and unavailable evidence must not be replaced by a plausible example.

**Evidence:** The package has 683 blobs. Loader regressions cover original downloads, post-initialization mutation, invalid IDs, missing references, unsafe paths and invalid ordering/counters. Hashes prove consistency relative to the trusted manifest, not signed or administrator-proof history.

## D45 — Owned services and private credentials

**Issue:** Inherited variables, occupied ports and reused process IDs could connect acceptance to the original installation or stop another project.

**Solution:** Keep state under `.runtime/reviewer005/`, clear inherited database/Kairos settings, generate private credentials and use PostgreSQL 55434, Keycloak 8090, API 8310 and website 3310. Match process identity and Docker owner labels before reuse or shutdown. Refuse conflicts; preserve volumes.

**Reason:** Repeatability includes safe repeated setup and shutdown. A familiar name, port or PID is insufficient proof of ownership.

**Evidence:** Private-state and real OIDC entries in [acceptance](evidence/build005/acceptance.json), reviewer-runtime regressions and [repeat setup](evidence/build005/setup-repeatability.json). Repeated setup retained 48 archive records, left zero active commands after cleanup and made zero interactive model calls. Credentials and sessions are excluded from publication.

## D46 — Artifacts before committed references

**Issue:** Import could acknowledge database references before artifact bytes were durable; another import could overwrite historical records.

**Solution:** Fsync exact artifact writes before committing references. Repeated setup verifies existing records, steps and artifacts instead of replacing them. Published history occupies a separate archive workspace.

**Reason:** A saved record should not claim a durable object until its bytes exist. Strict repeated imports preserve identities/timestamps and reject conflicting contents.

**Evidence:** Reviewer-evidence regressions, fresh full-stack acceptance and unchanged archive counts after repeat setup. Local fsync does not establish offsite recovery or immunity to privileged rewrites.

## D47 — Explicit Python package and interpreter

**Issue:** Browser helpers could run an interpreter without backend dependencies. An installed `scripts` package could shadow this repository's entry point.

**Solution:** CI consistently installs backend dependencies into `.venv`. Browser helpers receive `KAIROS_TEST_PYTHON`; reviewer checks use their own private virtual environment. Add `scripts/__init__.py` so module resolution selects this repository.

**Reason:** A developer shell must not hide a clean-checkout installation failure.

**Evidence:** Fresh locked installation and 229 passing backend tests, with six explicit skips. The CI definition is corrected; no hosted CI run is claimed.

## D48 — Rebuild under a new verifier identity

**Issue:** A clean checkout cannot depend on historical local Docker layers. Rebuilding a recipe does not reproduce its old image digest.

**Solution:** Download and validate the pinned Django revision, apply the original captured model patch and build the reviewed recipe under `kairos-investigation-django:build005-reviewer`. Report both image identities and preserve historical tags.

**Reason:** Independently reproduce saved patch behavior while disclosing the environment difference. Never count the maintainer reference as the agent result.

**Evidence:** [Fresh reproduction](evidence/build005/repair-reproduction.json): 110 tests, one skip, outcome reproduced, `environment_changed: true`. No model or database call occurred.

## D49 — Lossless raw distribution

**Issue:** A 163,309,413-byte capacity log is too large for an ordinary repository file; deleting it would lose failure evidence.

**Solution:** Compress seven raw files in `historical-raw.tar.gz`, retain original paths/sizes/hashes in an index and compare extracted bytes against originals. Leave original local files and frozen manifests untouched.

**Reason:** Compression changes distribution size without changing measurements. Aggregates remain convenient while exact failed and successful runs remain recoverable.

**Evidence:** [Archive index](evidence/build005/historical-raw-index.json): 280,334,843 original bytes in a 9,586,236-byte archive, seven verified members.

## D50 — Separate delivery from evaluated history

**Issue:** The modified working tree could appear to be the source evaluated in build004.

**Solution:** Verify the original inventory and archive 212 source files before delivery changes. Retain 386 evidence fingerprints. Give build005 its own manifest and sanitized publication snapshot, excluding credentials, sessions, dependencies, databases and model weights.

**Reason:** Historical claims require historical source. Packaging improvements must not rewrite prior outcomes or suggest external publication already happened.

**Evidence:** [Build004 preservation](evidence/build005/build004-preservation.json), source archive, delivery manifest and publication index. The prepared snapshot remains subject to review before external publication.

## D51 — Check actual container completeness

**Issue:** A source-tree website could work while its image omitted recorded evidence.

**Solution:** Include only curated website evidence in the Docker context/runtime stage. Build new build005 API/web tags and smoke-test live behavior, disconnected API, original downloads and recorded private closure.

**Reason:** Source-tree success does not prove the distributed image carries the product it promises.

**Evidence:** All 21 [Docker checks](evidence/build005/docker-smoke.json) passed; API UID 10001 and web UID 1000. Temporary smoke containers/schema were removed. TLS, public hosting and hostile test-forgery resistance were not exercised.

## D52 — Finish without retuning frozen outcomes

**Issue:** Better model scores could become an endless prerequisite for presenting sound software. Repeating expensive experiments after packaging-only changes would add heat without answering a new execution question.

**Solution:** Freeze strategies, retain every outcome and reuse completed capacity/recovery/restore receipts. Rerun affected delivery checks. Keep inference off during acceptance and serialize heavy builds.

**Reason:** Delivery changes access, reproduction and distribution; it does not change the model's earned score. No new machine or paid service is required for this milestone.

**Evidence:** Build004 retains 435,270 local requests with zero unexpected errors and soak acknowledgement p95 275.19 ms, plus the failed original soak and all 78 model attempts. Evaluation remains 0/36; build003 successes cover one distinct Django case. No production-scale or loop-superiority claim follows.

## D53 — Verify the complete handoff

**Issue:** New packaging could pass its own focused checks while breaking existing browser behavior or distributing a corrupt archive.

**Solution:** Rerun all eleven existing fixture browser journeys and verify source/evidence manifests plus every compressed archive member. Add negative checks for corruption, traversal and duplicate archive members. Keep `--bundle` optional until the publication archive is prepared.

**Reason:** The handoff needs both regression coverage and independently checked distribution bytes. A prepared archive must not be called an external publication.

**Evidence:** [Legacy browser checks](evidence/build005/legacy-browser-tests.txt), [five packaging negative checks](evidence/build005/packaging-negative-checks.json), [original preservation](evidence/build005/original-preservation.json) and [scoped shutdown](evidence/build005/scoped-shutdown.json). `scripts/verify_delivery005.py` verifies the delivery; `--bundle` additionally checks the prepared archive. Original database/object counts and build003/build004 evidence remained unchanged.

## D54 — Keep reviewer builds source-stable

**Issue:** The first archive seal rejected `dashboard/tsconfig.json` after Next.js added generated reviewer type paths during a clean build. The failed inventory is retained separately.

**Solution:** Register `.next-reviewer005/types/**/*.ts` and `.next-reviewer005/dev/types/**/*.ts` in the source configuration before sealing. Rebuild, type-check and compare the complete source inventory again.

**Reason:** A documented setup command should not silently change the source fingerprint of its own release. Generated build outputs remain ignored; the configuration that names them is explicit.

**Evidence:** `evidence/build005/packaging-reseal.json`, the retained first manifest/index, a passing source-stability rebuild and final archive verification. No inference or backend execution semantics changed.

## D55 — Bind the external seal to the current manifest

**Issue:** The external receipt recorded the manifest fingerprint; bundle verification also needs to compare the current manifest bytes to that fingerprint.

**Solution:** Verify archive, index and current manifest against the external receipt before checking members. An isolated regression accepts the valid seal and rejects an altered manifest.

**Reason:** A recorded fingerprint must be enforced. This is consistency relative to trusted local receipts, not a signature or privileged-rewrite guarantee.

**Evidence:** `evidence/build005/manifest-binding-check.json` and final `python3 -m scripts.verify_delivery005 --bundle`.

## Review entry points

Read [the final report](docs/FINAL_REPORT_005.md), [claim map](docs/CLAIMS_005.md), [five-minute demonstration](docs/DEMO_005.md) and compact [working brain](BRAIN.md). Earlier evidence is preserved, not replaced by this decision log.

## D56 — Repair the source-authority defect in a new version

The frozen v4 loop discarded initial source after its first tool result. Audit found 55 of 66 model dispatches could not propose patches because source references were absent from the action schema. All 60 searches were empty; 36 were repeated queries. Preserve that 0/36 study. V5 persists original source independently, uses issue-symbol source localization and server-bound compact exact-text edits, checks patches immediately, and caps retrieval before requiring a patch or an explicit final result. Hashes, scope, overlaps, syntax and patch budgets remain enforced. `evidence/build006/failure-audit.json` and new v5 regressions provide the evidence. No reference repair is given to the model.

## D57 — Qualify actual regressions before inference

Fresh qualification identified a missing `toml` dependency in the historical pytest image. A separate reviewed image adds pinned `toml==0.10.2`; old tags and failed checks remain preserved. Requalification reuses only source trees whose frozen hashes match. Candidate ordering stays fixed before model execution. Five cases qualify across three repositories. The remaining Requests case reproduces on Python 2, not the available Python 3 verifier, so the target of six is explicitly unmet. Freeze and attempt all five qualified cases; do not substitute cases by model outcome.

## D58 — Use MiroFish as a workflow reference

The inspected MiroFish repository offers useful staged interaction, evidence-linked reports and separation of real tool results from generated prose. Keep those ideas in Kairos's readable inspector and follow-up report. Preserve PostgreSQL durability and local inference. Do not introduce cloud memory or swarm simulation as a supposed repair fix. No MiroFish code or assets were copied. See `docs/MIROFISH_REVIEW_006.md` for commit, files, tradeoffs and scope.

## D59 — Keep the reasoning pilot separate from frozen validation

The v5 validation cohort finished with zero verified repairs in ten attempts. Preserve its configuration and outcomes. The separate v6 development experiment uses the same pinned Qwen3 weights with an 8,192-token context, 2,048-token output limit and thinking enabled. Each strategy verified Django11066; other attempts failed checks or response validation, and one loop dispatch remains unknown after a timeout. These results do not establish a broader repair rate or a loop advantage. The larger context and output budget address truncated reasoning; they do not justify relabeling development success as validation success.

## D60 — Stop idle Docker and inference to respect host limits

The user reported that Docker was making the Mac unresponsive. Inspection confirmed that the bounded reasoning pilot had already exited and its owned model server was gone. `docker desktop stop` reported that Docker Desktop was not running. Keep both off for documentation and captured-evidence packaging. Start Docker only when a required container check needs it, keep heavy work sequential, and stop it immediately afterward. Preserve volumes, images and all captures. No unknown model dispatch will be retried automatically. Evidence: `evidence/build006/heat-shutdown.json`.

## D61 — Verify presentation against the published cohort

Review found that the home-page boundary text still described twelve cases, the frozen-comparison filter omitted build006, and the featured development case lacked a valid same-profile peer link. Correct the cohort text, extend the filter and pair development attempts only when task digest, model-profile digest and protocol version match. Show development failure counts and the unknown-dispatch usage caveat. Add a recorded browser journey for these behaviors, the captured source regions and original downloads. The initial local test run was denied loopback access by the execution sandbox; its environment failure is distinct from the successful 52-test rerun with local access. Tests are evidence against the plan, not a guarantee that the plan predicted every defect.

## D62 — Reject incompatible inference settings before dispatch

A v6 job can require 8,192 context tokens while the default runtime profile supplies 4,096. New v5/v6 dispatches now compare the registered protocol with the pinned manifest and llama.cpp's read-only server properties: model identity, context size and one slot. A mismatch fails before inference. Historical v1–v4 behavior and captured studies remain unchanged; mock transports test this boundary without restarting inference during release acceptance. The pinned llama.cpp b11552 server API documents `GET /props` and its context/slot fields. This checks a trusted local server's declarations, not remote weight attestation.

## D63 — Preserve verifier feedback scope and isolate release tests

Hidden verification files and reference repairs remain outside source tools. Check diagnostics are deliberately visible to the loop and can disclose assertions; this is feedback-driven verification, not a blind final holdout. Keep that limit explicit in the final assessment. A reviewer unit test assumed port 3310 was free while actual OIDC acceptance already occupied it. Isolate that unit's command-failure prerequisite; retain the independent real-socket port-preservation test and all production port checks. The failed run is preserved separately from the passing rerun. New repair reproduction uses a build006 image tag so historical build005 images are not overwritten.

## D64 — Finish the tested release without rewriting model outcomes

The final gate combines actual source-scoped acceptance: 291 backend passes with six explicit opt-in skips, six recorded and four real OIDC browser journeys, image/isolation checks, recovery, restoration and a clean-source recorded-only entry point. Keep the clean database-free invocation separate: 190 passed and 107 intentional skips. Preserve all failed acceptance receipts and historical evidence. Package all 76 records/965 blobs, scan known private values, bind the source and archive with separate build006 manifests, and verify exact extraction. Stop Docker after required checks and leave the recorded website available without inference. The architecture assessment passes scoped infrastructure while failing broad repair effectiveness; a missed AI target is neither hidden nor solved by a new feature cycle.

## D65 — Treat overload as bounded admission and explicit failure

Map each active workflow to its enforced resource limit, response and recovery rule. Keep the existing eight-connection/32-waiter/five-second investigation pool, global queue24, tenant limit6 and one execution slot. Do not introduce new services or raise all limits as an assumed scaling fix. The overload workflow document distinguishes tested backpressure from unmeasured ingress, database timeout and distributed-deployment policies. Reuse measured local capacity because this documentation change does not alter execution; any future concurrency/pool change requires relevant new load evidence.

## D66 — Verify preserved raw files without republishing them

The clean archive passed verification, but the original installation also retains an oversized raw capacity log. The first main-folder verification correctly refused to publish that file. Add a narrow exception for the historical build004 raw paths listed in the lossless archive index: compare each original raw file's exact size/hash, then exclude that verified duplicate from publication inventory. Unindexed or changed files still fail. Preserve the initial build006 seal privately, add two focused regressions, rerun clean recorded acceptance and reseal the corrected package. No application, model or database execution behavior changed; no load or model experiment is repeated.

## D67 — Move schema changes out of application startup

Build007 introduces ordered, checksummed SQL migrations for all six active schema modules. API and worker initialization verify the applied head and durability without DDL or data backfills. A validated build006 catalog can be adopted without recreating its tables; unknown catalogs fail before ledger creation. One dedicated advisory lock serializes migrators. Two-second lock waits and sixty-second statements apply before catalog inspection as well as within migration transactions. A held-lock regression exposed the initial missing preflight timeout; its interrupted receipt is preserved, and the focused rerun passed. Configuration expansion and validation use separate revisions. Runtime database credentials have DML privileges and read-only ledger access; setup uses a separate owner credential.

## D68 — Separate machine locations from experiment identity

The active study CLI derives its checkout root and accepts explicit model cache, dataset, case root and private environment paths. Existing verified weights are read without copying them. Public experiment manifests contain logical paths and hashes; resolved paths and credentials stay in ignored mode0600 state. Updated build006 compatibility scripts no longer assume a named Desktop checkout, while their original bytes remain in the sealed historical archive. Filesystem relocation support does not imply Windows binary support.

## D69 — Spend checks on changed candidates

V7 replaces copied old fragments with server-bound source handles and inclusive original line ranges. Rendering verifies the captured digest and bounds before constructing a candidate, preserving historical v1–v6 semantics. Repeated checked digests return the captured verifier result without consuming another applied candidate or check. Two identical invalid proposals stop with an explicit reason. Complete assertion and source-frame excerpts retain original byte offsets, rather than arbitrary first/last output lines. Explicit issue function names precede indirect usage; bounded direct same-file callees are included where possible. No model prose is used to summarize verifier truth.

## D70 — Distinguish unused preflight candidates from model attempts

The first build007 selection mistakenly excluded every prepared build006 case, exhausting pytest without qualification. Preserve that initial selection receipt. Before any new case inference or qualification, correct exclusion logic to distinguish actual attempted cases from unused preflight candidates. Previously designated build003/build004 cases and actual build006 attempts remain excluded. Unused preflight candidates are explicitly requalified in instance-ID order. Under the fixed five-candidate-per-repository limit, two Django and three pytest cases qualified. Scope and baseline/reference exclusions remain visible; do not add candidates to recover the missing sixth case or select by model outcome.

## D71 — Make user goals observable

The website now provides a first-investigation walkthrough: choose a record, inspect original source and candidate, read independent checks, compare cost and download exact evidence. Live execution is described separately with its authentication, registered-case, worker and inference prerequisites. Cancellation, retries, forks, replay and publication have explicit boundaries. Browser journeys assert the observed outcome of each interaction. A usable inspector and an effective repair are separate user results.

## D72 — Keep third-party review inside the agreed constraints

The user requested Vibers and Vibe Code Auditor. Vibers requires external collaborator access and paid review; the fixed zero-spend/local-only release does not authorize that setup. Apply its spec-based human-review checklist locally and record the seven-dimension Vibe Code Auditor assessment. No outside reviewer, GitHub collaborator, service notification or paid review is claimed.

## D73 — Make mechanical indentation an explicit model action

The initial substantive v7 profile comparison produced zero verified Qwen3 attempts and one verified Coder attempt. Several captured proposals contained the correct replacement statement but omitted original Python indentation. Add an explicit `indentation=preserve` option: the model writes relative source text, and the renderer restores the exact common whitespace prefix from the captured original range. Verbatim remains the default for historical captures. The renderer neither chooses a semantic repair nor fixes invalid syntax; relative first-line indentation must be zero, and the resulting candidate still passes independent verification. Preserve original model bytes and report this construction policy. Also retain rejected edits beside the error so the next stateless call can inspect its own failed proposal. Initial infrastructure receipts are r1, initial model-profile comparison is r2, and r3/r4 are the two permitted follow-up protocol revisions. No validation outcome informed these changes.

## D74 — Require the selected edit mode in the captured schema

The first indentation revision was optional, and captured Coder responses omitted it. Preserve these unsuccessful development attempts. The final permitted revision requires `indentation=preserve` in the model JSON schema and captures that mode in context; the worker rejects actions outside the captured mode. Older captured v7 contexts without that field retain verbatim parsing. This is a format contract for original-source whitespace, not selection or correction of a repair. Freeze after this revision; do not tune on the five qualified evaluation cases.

## D75 — Freeze the best observed protocol, not the newest prototype

The two permitted indentation prototypes earned no development repairs and increased invalid-response failures. Select the actual Coder initial protocol with one verified development attempt over the alternatives with zero. Restore its four execution modules byte-for-byte from captured source; retain every rejected revision, model response and development test snapshot. Evaluation now uses the selected line-handle protocol once on all five qualified cases. No extra model, case replacement or post-evaluation tuning is introduced. Prototype indentation behavior is outside the active release.

## D76 — Keep schema-owner credentials out of runtime environments

Reviewer setup generates a restricted runtime role and keeps migration/test owner URLs in a separate private migration environment file. API and website processes receive only runtime credentials; acceptance setup explicitly requests owner credentials for isolated schema fixtures. This closes accidental environment exposure without suggesting that same-user desktop processes provide adversarial credential isolation. Real OIDC journeys and a restricted-role startup test independently verify the active database boundary.


## D77 — Keep optional free-provider inference separate from the frozen release

The user authorized a separate free Gemini API pilot on 2026-10-13 after the local v7 evaluation failed. Build007 attempts, source freeze and selected profile remain unchanged. The optional provider must use only public development-case inputs, a private explicit environment file, bounded calls and durable dispatch capture. Quota exhaustion is a stop condition; no paid or silent provider fallback is allowed. Google documents free-tier content use for product improvement. A provider pilot is a new experiment, not a replacement for the failed locked evaluation.

## D78 — Update the current-study browser contract while preserving historical inspection

The first recorded-browser run passed seven journeys and failed one homepage assertion that still expected build006 copy. The homepage now leads with build007; its scope text must name five locked Python cases. Update that assertion and still visit the historical build006 investigation directly to verify preserved patch, context and downloads. A corrected assertion does not manufacture a new repair result.


## D79 — Preserve evaluation source while fixing delivery defects after review

Independent local review found an undefined v7 variable in the legacy v4 context-exhaustion branch and a study command that overwrote elapsed time when inspecting terminal attempts. Remove the misplaced branch and preserve each original measurement byte-for-byte; missing historical elapsed time is unavailable, not near-zero. Focused regressions cover both behaviors. The frozen build007 source snapshots and validation lock are unchanged. Delivery source hashes may differ and are recorded separately; evaluation refuses changed source and must not be rerun or relabeled under the old freeze. These fixes do not change the reported outcomes.


## D80 — Install the complete acceptance environment independently of the API image

The clean reviewer environment exposed NumPy and SciPy missing during collection of legacy statistical/replay tests. The authoritative inventory intentionally includes those preserved modules. Add requirements-reviewer.lock with the existing tested NumPy 2.5.3 and SciPy 1.18.1 pins plus the API lock; reviewer and CI install that environment consistently. Its receipt binds both lock files. Keep the API image on its smaller runtime lock. The failed clean collection remains evidence; a development virtual environment must not mask missing declared dependencies.


## D81 — Preserve the previous reviewer image when reproducing a historical repair

The current reviewer repair command builds under build007-reviewer instead of overwriting build006-reviewer. The frozen patch and original source hashes are unchanged; a new built image is disclosed as a separate environment identity. Reproduction checks the saved patch without new inference.


## D82 — Bind resumable operation semantics and bound runtime SQL waits

Review found legacy backfill identities hashed only their names. New v2 operation identities bind explicit specifications and the source of transformation functions and their canonical hashing/input-snapshot dependencies. Existing v1 receipts and updated values remain untouched. Completed v2 operations reject changed semantics under the same identity; future semantic changes need a new version. Missing-value-only batches remain 200.

Restricted reviewer runtime connections now inherit a two-second lock timeout, 15-second statement timeout and 30-second idle-transaction timeout from their dedicated role. Provisioning owns these settings; runtime startup performs no DDL. Migration connections retain their separate two-second/60-second limits. A held runtime advisory-lock drill must prove explicit failure, rollback and recovery with the original request identity. The historical capacity receipt retains its original configuration and scope.

## D83 — Preserve API setup errors and fix model-specific compatibility

The authorized free API pilot first rejected a dotted authorization key due to an unnecessarily restrictive local validator; bounded ASCII authorization-key support fixes that error. The first HTTP request then returned 400 because MINIMAL thinking is unsupported by Gemini 3.8 Flash. V2 changes only the documented thinking level to LOW and uses a new durable dispatch ledger. Preserve v1 bytes; this known pre-inference rejection is not a model repair attempt. No uncertain request is retried. Billing remains disabled by the user's confirmation, and quota/unknown outcomes stop execution.


## D84 — Run failure fixtures through the same reviewer acceptance entry point

The shared inventory includes browser fixtures for delayed reads, uncertain submissions and polling failures, but the reviewer command previously invoked only recorded and real-OIDC journeys. Add the isolated fixture phase to both recorded and full-stack acceptance, select the reviewer interpreter explicitly and use a separate Next build directory. Refuse occupied fixture ports and disable Playwright service reuse. Genuine current and historical public captures populate the fixture API; synthetic identity remains labeled test-only. This phase tests interaction faults and never counts as model inference.


## D85 — Initial documentation-only scope (expanded by D86–D88)

The user requested a professional README, architectural documentation and confirmation of the visitor's actual DOM workflow after closing build007 development. Lead with the product, measured local results and a five-minute reviewer path. Link every numerical claim to its original receipt and keep fresh 0/10 repair effectiveness visible. Document the active Python/Next.js/PostgreSQL/local-artifact path; do not present historical Go ingestion or aspirational object storage as active architecture.

Preserve build007 source/archive/index/seal bytes. A documentation overlay records the revised README, showcase guides, compact context pointers and current DOM/download observations. The small verify_showcase008 command checks both the original archive and permitted presentation deltas; API, frontend, workers, cases and model configurations remain unchanged. This avoids relabeling historical tests as new executions or making the old seal appear to cover newer prose. No heavy acceptance, Docker, inference or API pilot is rerun for documentation.

The current browser DOM confirms ten visitor checks and actual evidence/patch downloads. Recorded mode permits inspection and closes private execution/sign-in. Actual-OIDC behavior retains its separate four passing build007 journeys. The visitor obtains inspectable evidence; a fresh repair still requires an operating worker/model and successful independent checks.


## D86 — Describe the current experience without implying missing capabilities

The global “No live execution” slogan described reviewer mode but read as a product limitation. Replace it with “Evidence viewer · Original investigation captures,” retain a consistent Workbench destination, and provide an actionable live-setup path. Lead the homepage with the product and earned development repair; retain the full fresh 0/10 comparison below it. Capacity leads with the successful 435,270-request repeat while keeping the initial failed run. The first-review guide and homepage now open the same development case. Original outcome labels and captured bytes are unchanged. Microsoft HAX and primary agent-engineering research support explaining capabilities at the point of use; applied findings are in docs/showcase/RESEARCH.md.

The user expanded the earlier documentation-only scope to website copy and usable live execution. This supersedes D85’s no-source-change boundary for the explicitly declared presentation/bootstrap delta. The sealed build007 archive remains intact.

## D87 — Make live execution an explicit, owned reviewer option

The real worker had generated historical studies, but the reviewer entry point started only authenticated services. Add fullstack --with-inference with an explicit prepared model cache. Validate hashes, prepared source, platform and storage before Docker; bind the same profile to API and worker, and use existing pinned weights. Default setup remains lightweight and inference off. A 900-second session deadline bounds local resource use, and shutdown preserves data. This connects existing implementation instead of introducing another agent framework or paid provider.

The browser submitted one exposed Django development case. Actual local inference produced a patch in two calls and registered checks passed all four tests. Progress, context inspection, downloads, replay and logout passed. This is a distinct interactive demonstration and does not change the locked study’s 0/10 result.

## D88 — Close startup failure and conflicting reuse paths before release

Independent review found model ownership-receipt creation outside the startup cleanup region. Move it inside cleanup handling and close the log on process-creation failure. A receipt-write failure now terminates the unreturned model. Repeated live setup compares the pinned profile and resolved cache/case paths before reusing a session. Matching setup keeps its original deadline; conflicting setup fails explicitly. These focused cleanup/configuration changes do not alter model prompts or repair evaluation. Frozen source remains archived and is never relabeled as the new delivery.


## D89 — Make acceptance repeatable after browser fixtures

The first revised mobile fixture still expected the old negative capacity headline. Update it to assert the earned headline and independently assert that the initial failed run remains visible. A repeat then found ESLint scanning generated .next-fixture007 output because only earlier build-directory names were excluded. Ignore all .next* generated output directories while retaining normal source lint rules. This makes repeated acceptance independent of prior fixture builds. The failed invocation remains documented; it is not counted as a passing software gate.

The live browser acceptance now writes its success receipt after the final logout assertion. Its original complete browser run passed; subsequent receipt-order changes prevent a future failed logout from leaving a success marker.


## D90 — Attempt cleanup independently when metadata is damaged

A damaged process-state file cannot authorize signals, but it should not prevent cleanup of containers whose exact names and labels independently establish ownership. Validate the runtime owner first, skip unverified processes, attempt each owned resource and report failures afterward. Initial/final supervisor receipt writes and signal restoration also cannot skip teardown. Focused fault tests cover corrupt state, metadata write failures, invalid PIDs, changed labels and conflicting live settings. Stored volumes remain preserved.

LinkedIn handoff is a reviewed runnable repository release. A localhost site is not a public demo URL. Prepare the sanitized snapshot and a scoped post; external repository publication and hosting require their existing separate authorization.


## D91 — Test private-state validation in a real Git checkout

The private-state checker used git check-ignore --quiet with two pathnames, which Git rejects with exit128. Clean extracted snapshots without .git did not exercise this branch. Check each credential/environment pathname independently and add a real disposable Git regression covering both ignored and partially ignored files. The existing .runtime/ exclusion was already correct; no runtime files were tracked. This fixes the checker without weakening the privacy gate.

## D92 — Correct hosted test assumptions without relabeling local acceptance

The first hosted PR run failed after local acceptance. A legacy Go integration fixture used an absolute laptop binary path; both hosted jobs execute that fixture but neither installed the declared Go toolchain. Build the checkout-derived Go source into a pytest temporary directory, isolate its database and port, and terminate only its own child. Install the toolchain specified by ingest/go.mod in both jobs. A missing toolchain or failed build remains a failure, not a new skip.

The pool test assumed consecutive checkouts return the same PostgreSQL PID. The configured eight-connection pool may grow asynchronously and rotate FIFO connections. Warm all eight slots, verify subsequent requests reuse that bounded PID set without opening more connections, then change an actual queued row inside a failed transaction and confirm rollback. This tests the intended contract instead of constraining valid scheduling. The isolated native PostgreSQL18 suite passed 428 tests with six explicit skips; Docker and inference stayed off.

The website job hid its backend failure in a private runtime log. Print bounded failure tails after redacting known generated credentials, database URLs, tokens and authorization codes. Keep private files and complete logs outside publication. New diagnostic tests cover credential redaction, output bounds and escaped paths.

Preserve build007 and showcase008 manifests, source archives, original results and acceptance receipts byte-for-byte. Declare the CI correction under evidence/ci009 and use scripts.verify_ci009 for the current source. The original008 command continues to verify its extracted historical snapshot. Hosted GitHub checks are a separate acceptance scope; do not retroactively label the earlier Mac evidence as a successful Linux run.
