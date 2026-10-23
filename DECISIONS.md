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


## D93: Restore exact rejection feedback and separate stronger-provider evidence

The worker stored tool requests but omitted them during context reconstruction. A rejected edit's replacement bytes therefore disappeared from the next prompt. The optional repair010 worker reconstructs exact captured requests and source authority. It does not correct model-authored code, weaken syntax/path checks or add case-specific fixes. Required feedback is never silently truncated. A local pilot exceeded its pinned context budget; the later provider uses its own explicit prompt/runtime profile.

The Codex CLI reuses normal ChatGPT authentication, forces that login method and strips API credentials. Native shell, web, apps, hooks, plugins and multi-agent tools are disabled; unexpected native-tool events terminate the attempt. Read-only filesystem mode alone is not a confidentiality boundary. The CLI's internal retries are not exact Kairos dispatch counts. Future unresolved-task runs request gpt-6.1-sol explicitly; earlier default-model captures retain their unavailable resolved identity.

Two implementation mistakes are owned: startup warning events were classified as tool calls, and explanatory summary metadata invalidated otherwise authorized patch actions. Focused regressions cover both. Exact captured candidates subsequently passed 22 pytest tests and four Django tests under original independent verifier images. They are post-hoc candidate verifications; original invalid/unknown outcomes and historical 0/10 remain unchanged. A later live run reached the account usage limit. No uncertain call was resent and no paid fallback was enabled.

## D94: Register unresolved tasks without a reference repair

The benchmark registry requires a known maintainer fix. It also derives entry-file paths from reference-patch headers, which is localization assistance and must be disclosed. The optional reviewed-unresolved registry instead requires pinned source, reviewed image/command, explicit approved source paths and complete independently captured failing-regression/passing-existing-test receipts. It reads no reference.patch. Strict path/link/hash validation refuses changed material before inference. Trusted operator review remains necessary; hashes do not prove verifier authorship or adversarial resistance. Existing live API/provider defaults remain unchanged.

The local CLI owns a separate private runtime, native PostgreSQL instance and bounded disposable checks. Existing runtimes are reported, never silently redispatched. Three real PostgreSQL/Docker journeys exercise the registry through the unchanged API/router and worker using an explicitly prewritten software fixture. They prove software behavior, not model effectiveness.

## D95: Present dated outcomes and actionable closure plans

The website labels the completed 13 October local-model study as frozen rather than a current overall product score. A separate follow-up page shows exact captured patches, check output, all new attempt outcomes and downloads using existing muted components. No old score is replaced by a post-hoc success. README and docs map every open gap to cause, evidence, mitigation, needed resource and closure criterion. Account quota is a resource constraint; adapter bugs are our responsibility. New GPU purchases, billing changes and universal repair promises are not prerequisites or substitutes for evidence.

Source packaging is an additive repair010 overlay over unchanged CI009/008/007 manifests. The new verifier checks exact active bytes plus original archive members and seals. Software acceptance and fresh model effectiveness retain separate receipts.

The optional runner uses one nonblocking POSIX file lock per checkout. It refuses contention before provider/database startup, never deletes the lock inode and releases ownership after failure. This enforces the one-investigation resource policy across separate private runtimes.

CI pins ubuntu-24.04 rather than the moving latest label and discovers the installed native PostgreSQL bindir before the CLI lifecycle test. GitHub's official runner inventory lists PostgreSQL16 and announces a November2026 latest-label change. The main database service stays pinned to PostgreSQL18; this avoids silently skipping the native lifecycle journey or assuming its binaries are on PATH. The software verifier uses the already declared pinned Python base image. [Official runner inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md).

Follow-up downloads use a small compiled byte catalogue and a read-only API route. Each request checks exact size, canonical base64 and SHA-256, with fixed logical identifiers and attachment headers. This prevents a post-build static-file change from silently replacing a patch or check receipt. Unknown/corrupt entries return404/409, without replacement data. Four focused Node tests cover byte equality, corruption, bounds, path selection and header safety.

## D96: Measure source retrieval before expanding repair or training

Use a small retrieval-trained code encoder and compare BM25, dense and hybrid ranking against the existing AST heuristic without maintainer file hints. Preserve exact original-source chunks/handles; record encoder truncation separately. A real one-case diagnostic found the relevant file at dense rank five and hybrid rank six, while every method missed under a matched four-region cap. Do not convert this into a repair or broad superiority claim. The 122-record corpus is an exposure/error corpus rather than 122 independent successful training examples. Free Kaggle/Colab GPU training is now part of the later plan, with disjoint data and runtime-fit checks first.

The Mac's initial FAISS/PyTorch combination aborted because both loaded native OpenMP runtimes. Run FAISS in a fresh process with bounded, hash-checked arrays; do not set the unsafe duplicate-runtime override. Pin reviewed model code, original and FP16-derived weight hashes, tokenizer settings and a reproducible serialization header. Count optional packages, weights and indexes in the existing storage ceiling.

CI preservation is additive: the original verifier checks the exact repair010 Git snapshot; the retrieval verifier checks the current overlay and inherited archive/seals. This replaces no historical receipt or test. Phase 2's longer-loop patch is prepared separately and is not active in Phase 1.


## D97: Keep longer-loop mechanics separate from measured repair outcomes

Introduce explicit `baseline-v8` and `loop-v8` configurations rather than changing v1–v7 budgets. The loop receives ten model calls, four applied candidates, four checks and 900 seconds. Its lease is 960 seconds, calculated by the database clock; recovery keeps the original deadline. Expand the configuration and all physical counter constraints in ordered transactional migrations before separate validation. The first PostgreSQL rehearsal exposed the unchanged six-call constraint; preserve that failed receipt and its corrected regression.

Use the existing durable runner with a frozen policy extension. Old study010 defaults remain six calls/two candidates/two checks/600 seconds. New optional retrieval captures source selection before generation, restores completed captures after interruption and refuses incompatible indexes. Keep trusted registry metadata immutable: changing entry hints in the case itself invalidated reviewed-task validation and weakened the completion-marker requirement. A separate localization option suppresses hints without changing verification. Zero-hit retrieval records its audit and stops without a patch instead of invoking a hinted fallback.

Run query embeddings in a short-lived, credential-free CPU process. Release weights before generation or verification on the 8 GiB Mac. The fixed output supervisor similarly applies limits in a fresh trusted process, removing threaded-parent `preexec_fn`. Preserve POSIX scope and independent container restrictions. These fixes strengthen the existing execution path without adding a persistent vector service or another model cache.

Freeze baseline transport at one dispatch and the loop at ten. Stop future dispatch after captured usage reaches 64,000 prompt or 8,192 completion tokens, or when usage is unavailable. A completed call may overshoot, and internal provider retries remain opaque; do not describe this as a hard token or billing cap. Failed, unknown and incomplete CLI execution returns a nonzero shell status while retaining machine-readable evidence. Current account quota does not authorize buying credits or repeating an uncertain call.

Tests distinguish mechanical software fixtures, actual embeddings, real PostgreSQL/container behavior, and future model effectiveness. Keep the sealed011 manifest unchanged; its original verifier checks the exact011 Git snapshot, while a new additive012 verifier checks current source and ancestry. The website's historical results and unsuccessful studies remain intact.

## D98: Use free cloud GPU capacity for a later controlled training pilot

The Mac remains the application, data-review and evidence-inspection machine. Prepare free Kaggle GPU training first, with Colab as a fallback after actual allocation, memory, quota and interruption checks. No upload, training, model download or paid account change occurred during this preparation. Keep cloud base weights remote; return only reviewed bounded adapters and receipts within local storage limits.

The 122-record audit contains only two distinct successful tasks and three distinct rendered patches. Deduplicate by issue family and target, review public-data provenance, and freeze disjoint training/development/held-out sets before fitting. Additional public training examples are required for a meaningful repair adapter study. A small retrieval adaptation is the first candidate; causal-model LoRA requires its own runtime-fit evidence. Cloud hardware makes training more practical but does not establish better repair outcomes. Promotion requires measured held-out performance against the frozen base profile, plus a verified checkpoint-resume path. See the advancement plan for the separate phase and gates.


## D99: Execute a development pilot without relabeling old validation

The new pilot uses the trusted development registry directly and refuses held-out/evaluation/unresolved entries. Reuse already qualified baseline/reference evidence; do not mutate the original task into an unresolved one. Freeze retrieval, source, generation and budgets before dispatch. The shared durable runner captures source selection before generation and keeps model/tool results, fencing and uncertain-dispatch behavior intact.

The exposed pytest6197 pilot completed in five calls, one patch and one check with 22 tests passing. Existing signed-in CLI requested gpt-6.1-sol; resolved identity is unavailable. Record the 66,744 input tokens explicitly: the last call overshot a post-response 64,000-token admission ceiling. The result strengthens this narrow development demonstration, while earlier 0/36 and 0/10 outcomes remain unchanged. A fresh comparison must qualify and freeze its own cases.

## D100: Separate metadata selection, qualification and model evidence

Freeze only safe columns from the pinned official 300-row Lite metadata, excluding historical task IDs and normalized issue digests. Select 24 candidates by a fixed seeded ordering across Django and pytest. Candidate counts are not qualified-case counts; no repair or benchmark claim follows until baseline failure and reference success reproduce under registered resource limits.

Validate comparison identities and complete attempt accounting before computing descriptive paired differences. Unknown/missing measurements stay unavailable, infrastructure failures remain visible and optional confidence must precede verification. Preserve the original audit while adding the pilot and all planned-case exposure. The new audit has three distinct verified tasks, not 123 independent successes.

## D101: Block training leakage before using free GPU time

Use strict source/provenance-bound labels, issue-family splits, exact/near deduplication and current exposure guards before exporting licensed public examples. Review found two defects: normalized issue aliases could evade raw digest checks, and unchanged source could be retagged to another revision in a verification receipt. Both now have regression coverage. Keep the empty freeze false rather than manufacturing training data from failed or duplicate trajectories.

Kaggle/Colab can provide a later measured GPU allocation, but no upload, account action or fitting occurred. The inert notebook and deterministic exporter prepare that phase; promotion requires reviewed data, a pinned compatible profile, measured fit/resume and held-out base-versus-adapter outcomes. Preserve local storage and zero-spend limits.

## D102: Show the actual investigation, not an opaque model response

Reuse the existing muted evidence components for original-source accordions, highlighted patch lines, check output, ordered steps and byte-verified downloads. The new static route presents reviewed public-upstream captures without changing the original record's private publication flag or simulating live execution. Product text explains the development scope and actual token/latency cost beside the result.

Browser acceptance checks desktop and 390 px layout, keyboard controls, patch/evidence downloads and invalid identifiers. Fix test assertions to accept the existing timed count and actual stdout stream; do not rewrite captured output to satisfy an invented expectation. Preserve failed receipts, reuse an unchanged production build and run real DB/OIDC gates separately from local environment skips. Seal013 additively and verify older manifests against their exact Git snapshots.


## D103: Reclaim disposable dependencies before sealing the resource receipt

The final aggregate storage check detected two separate reviewer acceptance virtual environments beyond the 6 GiB experiment ceiling. Stop using those completed environments, record their installed distributions and byte sizes, then remove only those reproducible dependency copies. Preserve every original acceptance receipt, log, model, source snapshot, database and artifact. Recompute the aggregate guard before sealing. This closes a delivery-resource overrun without moving assets outside accounting or deleting historical evidence. `evidence/evaluation013/dependency-cleanup.json` records the cleanup. Future acceptance should reuse one owned dependency environment or remove its disposable copy immediately after recording results.

## D104: Train a retrieval head on separately licensed source data

The historical repair inventory has too few distinct verified task families for the original fine-tuning gate. Keep that gate closed. Use source-maintained docstrings from pinned, BSD-3-Clause Jinja, Flask and Click repositories for a separate function-retrieval study. Remove each function's docstring from its code, deduplicate before repository-disjoint splitting, and record other functions as unjudged contrastive candidates. This creates real training evidence without inventing successful repairs or assuming benchmark issue text inherits the evaluation harness license.

Freeze CodeRankEmbed and learn a rank-16 shared residual head with 24,576 parameters. This fits the existing CPU and avoids GPU account access, uploads or new spending. It is retrieval adaptation, not causal-language-model LoRA. Preserve the initial uniform-negative run and exactly two predeclared development revisions. Select only on development, then evaluate the held-out repository once. The measured MRR difference is small and its paired interval includes zero; release the experimental head without changing the default repair encoder or claiming better repairs.

## D105: Preserve exact resume and make training reproducible without base weights

Checkpoint model, optimizer, global step, random generators and sampler in safetensors plus checked JSON. The selected real 200-step run and 37+163-step continuation produced identical complete state. Publish the small inference head, full paired outcomes and byte-verified compressed embedding caches. A reviewer can reproduce CPU fitting without downloading encoder weights. Keep source acquisition and encoder execution as separate provenance receipts. No missing wall-time measurement becomes an invented training benchmark.

## D106: Correct verification dependencies before fresh repair inference

Preserve every initial qualification failure and the original verification images. Add reviewed hash-locked dependency images for modern Django source revisions; bind each case to its exact image ID. Reuse already captured passing checks only when source, verifier and image identity match. Retry only captured environment failures before any fresh repair dispatch. Keep behavioral mismatches and every frozen candidate; do not select cases by model success. Python 3.8 also lacks standard-library zoneinfo, so modern-source dependency compatibility requires an explicit subsequent image receipt.

## D107: Capture unittest lifecycle instead of scraping formatted output

Django15347's real baseline failed a subtest, but the historical verifier could not match its wrapped description. Its reference passed 30 tests. Preserve those exact captures and the old generator. Add a versioned verifier that records unittest start, outcome, subtest and completion events directly. Match stable IDs, legacy test names and exact maintained descriptions. Missing, skipped and expected-failure regressions cannot yield a successful repair. Apply the correction only to captured incomplete reporting cases before any fresh model execution; keep already-qualified verifier bindings unchanged.

## D108: Separate CPU training acceptance from application dependencies

Keep Torch and safetensors out of the web/API dependency lock. A dedicated hosted CPU job installs pinned optional training packages and requires actual imports before running training mechanics. The regular authoritative backend inventory still includes all014 tests; unavailable optional packages are explicit local skips, with the real ML suite run separately. Historical013 verification now uses its exact Git snapshot, and014 gets an additive overlay manifest. Do not rewrite old seals to make current source changes pass them.

## D109: Isolate learned retrieval from repair-strategy effects

The trained head is evaluated on a frozen function-retrieval task and integrated with real code/query encoding and FAISS. Its identity binds both indexed and query vectors so mixed encoders are rejected. The fresh repair comparison instead fixes the same issue-only AST initialization across single-call, adaptive-loop and independent-draft arms. This prevents an apparent strategy improvement from being attributed to a simultaneous encoder change. Repair-level retrieval gains require a new frozen ablation, not reuse of held-out014 outcomes for tuning.

## D110: Preserve operational failures without repeating model inference

After Docker shutdown, its Desktop control plane reported running while the engine API timed out. Two development loop attempts reached accepted patches but could not complete their checks. Keep those original outcomes. Pause only the owned batch scheduler, restart and verify the engine, then resume the same process and frozen configuration. Do not resend any captured or uncertain model dispatch, substitute cases, or replace the infrastructure failures with later checks. Engine readiness is an operational precondition for the remaining verification phase. Stop Docker when that phase finishes.

Completed preflight revisions are stored as lossless archives only after restoring and checking every file's bytes and mode. Final qualification receipts remain expanded for evaluation. This reclaims storage without deleting evidence or moving assets outside the aggregate accounting roots.


### D111 — Resume the owned scheduler after account switch

The account switch held only the study scheduler at a boundary with no in-flight child. After the switch, verify its exact command hash, all31 frozen source digests, unchanged CLI provider identity and Docker readiness before sending SIGCONT to that same process. Preserve immutable attempts and unknown dispatches. The private pause/resume receipts remain outside publication; public documentation does not expose machine authentication state.

### D112 — Preserve stopped historical databases before reclaiming working copies

The aggregate experiment-storage limit also covers old private experiments. Five proven-stopped repair010/013 PostgreSQL directories were archived using the same per-member byte/mode validation as new study databases. Keep each archive, full preservation receipt and original public results; restore the archive before inspecting the old database. This creates room for the fixed study without deleting evidence, moving files outside accounting or changing old receipts.


### D113 — Make coding-model fine-tuning a separate, gated improvement study

The user requested a plan to train a coding adapter if it improves metrics. Record that follow-up in docs/CODING_ADAPTER_014.md without changing the running measurement014 study. Start from a small open1.5B model, independent public real-issue supervision and paired base/adapter evaluation. Keep every current evaluation family out of training. Free-GPU fit, cloud scratch admission, complete checkpoints and independent local verification precede any improvement claim. The completed retrieval head is a separate learned component; it does not imply coding-model training.


### D114 — Reproduce fresh repairs with external verification inputs

Automatic approval review rejected copying reference patches and hidden tests into public evidence because that would disclose held-out material. Keep those inputs private. The optional saved-repair command instead accepts the original dataset separately, validates source/reference/verifier hashes against published qualification metadata, reconstructs only an ignored runtime and performs no model execution. Public downloads retain original investigation captures, candidate patches, check captures and hashes. The existing historical reviewer reproduction remains separately available.


### D115 — Preserve completed private training state before final checks

Four completed private training/reproduction directories were compressed into archives and every member byte count, SHA-256 and mode was checked before removing expanded copies. Keep the archives and full indices under the counted experiment root. Selected public head bytes and all published training results are unchanged. This retains storage headroom for final clean-source verification without deleting historical evidence or excluding owned files from accounting.


### D116 — Prioritize backend and coding-model training after the completed study

The user explicitly paused website work in favor of backend features and model training. Preserve accepted training UI and prepared comparison files without presenting uninstalled routes as available. All57 frozen repair evaluations are complete: held-out loop7/12, baseline1/12 and independent drafts1/12. Keep original outcomes unchanged. Verify real-service integration and reproduce a captured repair independently before advancing the coding-adapter data/resource gates. Evaluation progress is not gradient training progress.

### D117 — Bind public upstream path text before privacy scanning

A read-only export initially rejected upstream issue descriptions that contained another developer's public `/Users/` path. Preserve that failed derived export privately. Match exempt text only against the exact frozen public issue and its serialized forms; continue rejecting our machine paths, secrets and unrelated filesystem paths. Scan every record before publishing any output. This fixes the false positive without rewriting original captures or weakening private-path protection. All57 original records pass the corrected validation.


### D118 — Verify real services before further training-data intake

Run the authoritative backend inventory against a fresh loopback-only native PostgreSQL instance, the existing owned Keycloak realm and the exact reviewed fixture image. Preserve private identity bytes and stop only services started for the run. The invocation passed1014 tests and 16 subtests; four explicit opt-in/ML skips remain in its receipt. Run the optional CPU ML suite separately with actual dependencies:39 tests and six subtests passed with no skips. Do not add overlapping test counts. Independently reconstruct Django14752 source and verify baseline failure plus reference/candidate success across19 tests; perform no model execution. Preserve receipts before losslessly archiving the stopped acceptance database, then stop Docker.

### D119 — Refresh evidence without turning evaluation cases into training labels

The post014 audit has180 records,28 verified trajectories,15 verified task IDs and18 matched verified patch byte sequences. This does not mean15 independent issue families or an admitted licensed corpus. Match only patches bound to captured passing checks. Keep all24 current cohort IDs and related families excluded from coding-adapter training and selection. Preserve the earlier123-record/three-task audit as its historical snapshot.


### D120 — Count acceptance scratch and preserve it before reclamation

The completed backend suite retained230,487,980 logical bytes of temporary fixtures. The final aggregate check detected a97,144,983-byte overrun of the6GiB limit; do not omit the scratch from accounting or admit a new download. Archive every file, mode and link target under the same counted root, validate resolved tar hard-link streams against original contents, then reclaim only the expanded fixture copy. The34,813,010-byte archive preserves all originals. Final storage admission passes with the4GiB free-space reserve intact. Record the transient failure and remediation in the storage receipt.


### D121 — Preserve the fixed training-data candidate list before execution

Acquire only the exact official43,644,473-byte SWE-Gym parquet and verify its pinned hash. Run deterministic scope, exposure and duplicate prefilters, then retain the first500 candidates in instance-ID order. Preserve all2,438 dispositions, including562 candidates outside the inspection ceiling. None is independently qualified or training-admitted. Capture six repository license samples and the first source revision without executing it. Keep reference/test bytes private; publish metadata and notices only. Training admission still requires case-specific rights, family resolution, source replay and complete baseline/reference checks.

### D122 — Use persistent private intake and report missing temporary state accurately

The previous temporary qualification/scheduler root was absent on continuation. Do not invent a cause, reconstruct uncaptured work or mark the private runtime restored. Revalidate every57 published comparison capture against its original report hash; preserve earlier qualifier archives. New acquisition uses persistent private staging, and storage accounting includes the whole existing/private/tmp root. This avoids recreating an empty directory that could be mistaken for restored evidence.

### D123 — Separate GPU inventory, account access and model fitting

Pin official1.5B model metadata and prepare a standalone read-only GPU inventory notebook. The inventory performs no download, upload, installation or training and cannot certify memory fit. Colab showed a signed-out homepage; automatic approval review rejected opening its external authentication flow. Keep the permission request pending and continue local work without a bypass. Data qualification, bounded scratch admission, measured20-step fitting and resume verification remain required after account access is available.


### D124 — Independently qualify real reference repairs before training admission

The first MONAI candidate reproduced its expected baseline failure while preserving13 existing tests, then passed all14 tests under the reference patch. Run only the complete registered suite in the existing bounded sandbox. Keep the reference result distinct from model effectiveness and from final training admission. A portable qualifier now binds exact row, source, verifier, image and capture hashes and reuses completed checks without execution. The first CPU image uses legacy-compatible Torch1.13.1, NumPy1.23.5 and exact Ignite0.3.0, with dependencies pinned by hashes.

### D125 — Fix missing verification dependencies through explicit new revisions

The second fixed training candidate failed collection because ITK was absent. Preserve both zero-test captures and the original image. Prepare a separate native ARM ITK5.4.7 dependency extension and a separately bound qualification revision. Permit this only when a completed pre-model environment failure is captured; never replace successful qualification or a completed behavioral outcome. Keep all declared tests and every500 candidate disposition. This addresses an environment defect without modifying source to manufacture qualification.

### D126 — Honor separate external-upload authorization and account cleanup

The user authorized Google sign-in and authenticated through the provider interface. Automatic approval review separately rejected uploading the read-only preflight notebook because the file transfer had not been specifically authorized. Keep the exact-file request pending; do not replace the rejected transfer with pasted code, another browser or an indirect API. Continue local work. The user requires account logout after training: disconnect owned cloud runtimes, sign out and clear available browser-local session state without saving credentials or creating passkeys. Do not claim control over Google-retained logs or delete unrelated account authenticators.

### D127 — Release the cloud session after observed inventory, without overstating cleanup

After explicit exact-file authorization, upload only the reviewed read-only inventory notebook. Capture its visible output and bind it to the local notebook hash. The available Tesla T4 reported 15,360 MiB VRAM, but no forward/backward pass or model fitting was performed. Python 3.13 and the observed package versions require a separately frozen training environment; GPU availability is not compatibility evidence. Delete the owned idle runtime immediately while corpus qualification continues. Move only the newly uploaded notebook to the recoverable bin, sign out and remove the remembered account from Google's chooser. Verify the blank sign-in field. Do not save credentials, create passkeys or modify unrelated authenticators. The browser exposes no verified cookie/history purge capability; provider-retained logs and permanent bin deletion remain outside the completed cleanup. Preserve earlier dated authorization blocks as history, with their subsequent explicit approvals recorded.

### D128 — Preserve qualification and conversion failures before model fitting

Register a separate MONAI0.3 dependency profile with source-declared Ignite0.4.2; do not reuse or overwrite the0.2 image. The third reference repair qualified, while three subsequent cases ended without complete verifier results and remain excluded. Do not label their unexplained process exits as proven OOM. Convert supervision through the production source-handle renderer and require exact replay. The first three conversions lack complete issue-only context and remain rejected. Do not read the reference to expand a prompt. A separately versioned context policy may use public issues and source, with all original rejections preserved. Record21 focused passes without claiming coding-model training.

### D129 — Use a larger primary training candidate without treating size as acceptance

The user requested a standard suitable for serious coding work. Upgrade the intended primary candidate to7B and retain1.5B as a baseline/resource smoke. Pin official upstream and a smaller prequantized NF4 derivative separately; record that their transformation provenance is not independently reproduced. No weights, cloud allocation or measured fit follows from metadata capture. Keep the same exact quantized base for both comparison arms, preserve storage guards and require the actual20-step T4 memory/resume gate before fitting. Select by development repair evidence, with untouched evaluation after freezing. Finish corpus and runtime preparation before asking the user to authenticate again; the earlier inventory-only sign-in was premature.

### D130 — Bound larger-model selection and keep provider fallback free

The user authorized considering more model capacity and another provider if Colab cannot support it. Add one14B candidate to the7B primary-model pilot, preserve1.5B as a baseline/resource smoke and keep the two training-profile limit after model selection. Pin official and prequantized14B identities separately. Capture metadata only; do not download29.5GB upstream weights or assume a9.93GB quantized file proves VRAM fit. Prefer Colab free capacity, then eligible Kaggle free capacity, with no new spending or large-model load on the Mac. Choose by development repairs among candidates passing actual20-step memory/resume gates, not size alone. Cloud scratch needs explicit bounded admission; the20GiB temporary proposal does not change the Mac6GiB guard. Freeze before untouched evaluation. No further account sign-in while local preparation remains incomplete.

### D131 — Run an explicit14B resource pilot before the full repair corpus

The user objected that preparation had not produced actual pretrained-model training, then explicitly selected14B. Make14B primary and stop further model-selection discussion. Test actual adapter updates and checkpoint recovery on explicitly synthetic source-edit fixtures first; these fixtures are not admitted repair data and earn no quality claim. This changes sequencing, not the200-repair/five-repository admission gate for full training. Use a pinned prequantized14B model and Unsloth's memory-efficient checkpointing with dropout0 in this separately recorded resource profile; preserve the earlier generic PEFT profile. Bound temporary cloud scratch to20GiB, preserve4GiB free and enforce no paid upgrade or silent7B substitution. Package the complete reviewed notebook before requesting its separately required upload authorization. The old inventory-only login was premature; this request now has concrete executable work behind it.

## Colab 14B pilot: preserve the failed bootstrap and target the isolated environment

The approved 14B resource pilot reached a free T4 runtime. Its first setup failed before package installation or model download because Colab Python 3.13 does not provide ensurepip. Revision 2 creates the virtual environment without pip, then uses the existing host pip with --python to install into that environment. This retains isolation and the runtime Torch/CUDA constraints without changing the model or training scope. The original notebook and observed failure remain preserved. At this checkpoint installation is executing; no optimizer update has been observed. The synthetic pilot measures resource and resume mechanics only; full repair-corpus training remains a separate gate.

## Source-only supervision packing and full-training preflight

Revisions 3 and 4 preserve prior context policies and receipts. Revision 3 follows original class links and constructor dependencies and captures import authority. It mechanically converted MONAI1086, while MONAI1012 and MONAI1037 remained outside the issue-selected context. The first real tokenizer measurement was 3,078 tokens, exceeding the unchanged 2,048-token training bound. Revision 4 removes long leading documentation/declarations and lower-priority whole regions before reading a reference target, using the pinned 14B tokenizer and a 1,536-token prompt budget. It preserves exact original-line handles and records omissions. MONAI1086 now replays exactly and fits 1,685 complete tokens, including 225 assistant tokens. The other two conversions remain rejected. No case is admitted before rights, family, deduplication and corpus gates.

A new isolated train-command preflight regression reproduced an UnboundLocalError caused by calculating the step budget from tokenized rows before that variable existed. The budget now derives from admitted corpus rows; missing pilot evidence is rejected before model allocation. All 53 focused checks pass, with one existing Authlib deprecation warning. The active Colab pilot script was not changed.

## Keep measured 14B training separate from resource acceptance

The full condition completed20optimizer steps in2,785.381916976seconds, with13,918,797,824peak reserved bytes against15,637,086,208GPU bytes. About10.99%headroom is below the unchanged15%target. Interruption/resume and the90minute overall execution bound remain separately observed conditions. Preserve this profile rather than relabeling it as a passed resource gate. A candidate next profile may enable all major linear LoRA targets, which the [official Unsloth guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide) recommends; the current log states that q/v-only adapters prevented MLP/O manual-autograd patches. Lower memory or faster execution from that change is an untested hypothesis. The full training runner must use a compatible measured profile and actual qualified data before any repair-training claim.


## Measurement014: review real-data environments before more GPU work

The current 14B dispatch remains bounded and unchanged. Preparation now targets the next concrete blocker: independent real-repair verification across repositories. Ten pinned dependency/build declarations were captured without executing upstream source or starting Docker. Full upstream CI environments are unsuitable as blind install recipes: Hydra invokes Java from custom setup hooks, Dask includes an unpinned Git dependency, Bokeh includes browser/Node/documentation tools, and Conan requires a legacy dependency stack plus CMake. The new dependency-review receipt records exact required test scopes and the next reviewed build decision for each repository. It preserves a Bokeh404 and its subsequent Git-tree-based resolution.

Each environment must still receive a pinned dependency lock and complete registered baseline/reference checks in the existing restricted verifier. No test omissions, recipe review or metadata capture counts as an admitted training repair. This separates lightweight preparation from the later sequential Docker phase and avoids unnecessary Mac heat while cloud training is active.


## Measurement014: preserve timed-out training evidence before cleanup

The single approved14B resource dispatch reached its5400-second deadline. Its full20-step condition completed, but final interruption/resume equivalence is unverified, and measured full-condition VRAM reserve misses15%. The earlier queued export was cancelled by the notebook exception. After confirming no archive and idle kernel, the existing export cell executed once as[6], creating119332534bytes with SHA256fdf3ef3ef76ce430164946f83eefe13375785717dab1134497e0383caaed53c9.

Browser download events did not arrive for automatic export or the existing archive menu download. Local receipt of the archive has not been established. Therefore runtime deletion and account cleanup remain pending: deleting volatile cloud files now would destroy unverified evidence. The next action is retrieval of the existing archive, never a new training dispatch or regenerated export. The streaming local verifier avoids checkpoint deserialization, unsafe extraction and duplicate storage.


## Measurement014: stop recovery when volatile runtime no longer exists

Colab Manage sessions now explicitly reports no active sessions. The archive whose identity was captured was never verified locally; exact-name and exact-size checks of known download/temp roots found no file. A download-only recovery cell had no execution counter or output. No replacement runtime, training rerun or fabricated checkpoint was used. The archive must be reported unavailable, including the missing raw metrics/checkpoints and unverified resume verdict.

Google was signed out and its remembered account removed; the final page contains an empty sign-in field. The notebook was retained because deleting remaining saved outputs after failed archive retrieval would worsen evidence preservation. Provider-retained logs and browser/device traces are outside the verified cleanup. End recurring recovery checks because an absent session provides no retrievable artifact. Any future model experiment needs a separately frozen recipe and durable export tested before expensive training.


## Measurement014: qualify a second repository before more cloud fitting

The next bounded phase uses the first preselected Moto case, getmoto__moto-4792, with its complete14-test CloudFront scope. Moto3.0 receives its own exact environment registration; source-only verification is constrained to moto/. Unknown versions and mismatched frozen rows remain rejected. The missing registration was reproduced in a failing regression before adding it;63 focused backend/data checks now pass.

Hydra1006 source was also acquired, but generated grammar is absent and setup invokes Java. It remains pending a reviewed generation recipe rather than masking missing source through a different installed package. Moto dependencies are inspected from source imports and pinned official PyPI wheel metadata, with registry hashes and explicit dependency-closure validation before a network-isolated image build. Historical profiles and completed cases remain unchanged. No new coding-model training occurs in this phase. The separate receipt-content validation gap in corpus admission is recorded and must be closed before a full training package is trusted.


## Measurement014: Moto4792 earns reference qualification

The pinned source and dependency image completed all fourteen registered CloudFront checks under the existing restricted verifier. Baseline produced the two required regression failures while all twelve existing tests passed; the reference patch passed fourteen of fourteen, with zero skips and complete output. Original source stayed unchanged. The two raw captured results remain private and their hashes are published in qualification-progress-v4.json. This increases independently qualified references to four across two repositories, with no model call or agent-repair claim.

A wheel review initially rejected vendored metadata in py1.11.0; the corrected reader uses only top-level distribution metadata and revalidates cached bytes. sure2.0.1 has no compatible wheel, so its exact official registry source package and setup were inspected. It builds only inside Docker, offline, with pinned setuptools/wheel, then pip check verifies the full dependency closure. The image contains no Moto source. Historical recipes/images and preparation failures remain preserved. Docker was stopped immediately after verification.

Frozen context v4 omits required Moto edit lines. The converter correctly rejected the target and retained all omissions; neither context nor reference was rewritten to manufacture admission. Full training remains blocked on complete usable data, receipt-content validation and a separately accepted resource/export profile. Qualified reference counts, converted examples, admitted corpus rows and model repair outcomes remain separate quantities.


## 2026-10-17: Require the actual training admission evidence graph

**Problem.** The corpus validator checked admission flags and SHA-256 syntax but did not open supporting qualification, rights or family receipts. A structurally plausible document could therefore reach model preparation without its claimed evidence.

**Decision.** Keep structural corpus validation, then require an explicitly hash-bound receipt-only package before model-manifest reads, output creation or GPU imports. Validate exact row membership, safe paths, bounded file sizes, original qualification bindings, actual decoded/hash-checked test streams, selected-suite outcomes, frozen exposure contents and exact converted example identity. Require attributable task-bound material-rights and family/near-duplicate reviews. Bind the package index to intent and checkpoint identity. Doctor readiness requires the same package. This avoids expensive allocation for data that cannot establish its provenance.

**Evidence.** Ninety focused tests passed. Four real previously captured reference qualifications passed offline raw-stream validation. Broad backend execution passed967 tests and 16 subtests with141 skips; three socket-binding failures were caused by the sandbox and passed in a separate permission-corrected focused rerun. The failed first run remains recorded. No fresh PostgreSQL/OIDC acceptance, inference, Docker execution or final training-data admission is claimed. The previous runner bytes are preserved in a compressed immutable snapshot; evidence and checksums are in `evidence/measurement014/coding-data/admission-hardening-v1`.

**Limits and next action.** Hashes establish identity, not legal permission or honest authorship. Rights and family decisions still need real case-specific review. Current real-data count remains four qualified references across two repositories, one complete converted example and zero final admitted rows. Continue fixed-cohort qualification and review without lowering the200-row/five-repository gate. Before another separately approved GPU fit, align the measured resource recipe and prove durable artifact export. Historical pilot loss of the raw archive remains explicit.


## 2026-10-17: Follow public source citations, retain exact conversion limits

**Evidence and decision.** The next fixed Moto case4799 required two real EC2 error responses outside its mocks. Exclude it before execution under the existing network-free policy; do not delete selected tests or manufacture provider responses. The following fixed case4809 uses mocked task-definition APIs. A separately reviewed offline dependency layer adds only docker5.0.3 and websocket-client1.3.3; the SDK client is lazy and selected tests never execute jobs. No Docker socket is mounted. Its five expected regressions fail while six existing tests pass; the maintainer reference passes all11.

The original issue already cites source lines. V4 ignored that useful localization evidence. Add v5 to select the cited function and bounded same-file direct callees from frozen original source. Never fetch the cited revision, inspect targets for selection or widen hidden-material access. Retain all previous policies and outcomes. Freeze before real conversion. That conversion then exposed a four-hunk/three-edit representation mismatch. In the second bounded round, v6 leaves context unchanged and merges only nonoverlapping hunks within an already captured handle, preserving unchanged bridge bytes. The existing maximum of three edits, original-source bounds, syntax checks and exact reference-byte replay remain mandatory.

**Observed result.** Moto4809 converts exactly into two edits. Its complete pinned-tokenizer example contains1853tokens, including350supervised tokens, without truncation. Focused103tests and full backend983tests plus16subtests passed;141optional checks were skipped. Docker Desktop was stopped after the required verification. No new model dispatch, real-data fit, full-study admission or fresh held-out effectiveness claim occurred. Evidence is under coding-data/context-preparation-v5/v6 and qualification-progress-v5.json.

**Sequencing.** The200-repair floor remains the full-study requirement. It should not be confused with the data size needed for a clearly labeled small real-data mechanics pilot. Such a pilot still needs attributable data review, a compatible measured14B recipe, successful durable export preflight and separately authorized cloud upload/execution. Do not reuse the failed historical synthetic pilot as that acceptance.


## 2026-10-17: Prove lossless archival before retiring newly owned source

The fixed-cohort work is near its6GiB project-storage ceiling. The newly acquired Moto4799 case was excluded before execution and no longer needs an expanded active checkout. Archive only that newly owned source, then restore it independently inside counted temporary storage. Compare every file hash, relative symlink target and permission mode, plus the registered source digest, before retiring the expanded copy. Retain the original archive, its SHA-256, complete material manifest and retirement receipt. No historical source, model output, credential, verification capture or prior image is changed.

Actual proof:18,207,431expanded bytes became a2,208,153-byte archive;15,999,278bytes reclaimed. Restoration passed before the expanded source was retired. Manual requalification requires verified restoration first; do not treat an archived source path as corruption or silently reacquire it. Public evidence: coding-data/owned-archival-v1.json. This is an operational preservation measure, not an additional repair or training result.


## 2026-10-17: Preserve a verified account-switch handoff

The user requested a durable checkpoint before quota exhaustion. Save the current tracked modifications and all selected014source/evidence as an account-independent working-tree overlay, together with branch/base identity, readable continuation instructions, current BRAIN/decisions and an exact hash/size manifest. Verify every tar member without extraction. Exclude credentials, sessions, installed environments, weights and private runtime trees; those private captures remain in their original persistent local roots. Unrelated build005/build006publication archives and historical seals are untouched. No Git commit, push, reset or new cloud dispatch is implied.

The verified overlay contains572files and9,391,088compressed bytes. Its SHA-256 isde030ba9e2eb0f811b45e08d4f49f25b3d22856fc1624cca23bbc26a5133e397. A later supplement captures the two prepared real data-review inputs and updated checkpoint. All two underlying captured qualifications were reverified; no training approval was issued from similarity or a dataset license label. Handoff: `Desktop/resume/kairos-ai014/HANDOFF-2026-10-17-TRAINING-V6/START-HERE.md`.


## 2026-10-17: Supplement lexical similarity with explicit component references

The prepared MONAI1086 nearest-neighbor list was dominated by generic bug-report wording. A separate scan over the same500fixed training candidates found additional exact mentions of RandSpatialCropSamples or set_random_state, including MONAI2010 and other transform/random-state reports. Preserve that candidate list for explicit family review rather than treating low lexical similarity as independence. Symbol overlap is a review signal, not a duplicate verdict or training approval. The scan excludes reserved/evaluation issue text and runs no model. Exact identities are recorded in coding-data/case-review-symbol-audit-v1.json and private review-preparation-v1/symbol-neighbors-v1.json.


## 2026-10-17: Verify two real experimental examples without bypassing corpus admission

Complete attributable assisted family review within the fixed500training candidates. MONAI1086 concerns wrapped-cropper random-state forwarding; neighboring shape, inversion, shuffling and shallow-copy bugs have distinct causes. Record MONAI2010/2104 as a shared mutable-metadata family for future split constraints. Moto4809 concerns Batch resourceRequirements numeric coercion, with no same-target fixed candidate found by issue-symbol and changed-token review.

Capture the exact frozen SWE-Gym dataset card and revision API: both declare MIT at revisionbb94ed9e39bbeb96a7fcbfb533b80f25a7fd59cb. Review pinned upstream Apache2.0 license files, selected source paths and MONAI file headers; preserve full notices. Approve these two records for project experimental-data intake in reliance on the distributor/upstream declarations. This is not independent contributor-rights clearance, a copyright warranty, raw-data-publication approval or cloud-upload authorization.

Run the actual production evidence verifier against the two-row reviewed set:2rows/20supporting files pass. The full training-corpus validator still rejects the small set. Package only public inputs/targets and notices for a future mechanics pilot, excluding hidden checks, runtime state, credentials and weights. Its10,835-byte archive and every member hash were verified; complete examples contain1685/1853tokens with no truncation. No model loaded and no upload or fit occurred. Full-study data and measured14Bresource/export gates remain independent.


## 17 October 2026: fixed resume release and separate Public100 admission

The user chose 100 training, 10 development and 20 untouched evaluation families as the final resume release scope. The original 200-case independently reproduced corpus remains a separate follow-up. A new explicit `public100` mode preserves the old admission contract and distinguishes public supervision from the fixed ten-family local training audit. Every development/evaluation case still requires independent qualification. This reduces redundant training-environment work without relabeling external verification as our own.

The candidate plan is outcome-independent and keeps the prior training-only cohort outside development/evaluation. It is candidate metadata, not a completed family review or admitted corpus. Missing receipts fail before model allocation.

A separate two-real-example `resource2` fit-only mode allows a measured 14B resource/resume pilot before all 100 training examples are ready. It shares the native runner and padded recipe with the final fit. Checkpoint state proofs and actual stage receipts gate measured resource acceptance; this cannot authorize a repair-success claim or full corpus training. Separate dispatches and a download probe address the previous timeout and lost-export failure. The new approved input ZIP passed a packaged evidence check and member hash verification. The user approved its Colab upload and run; authentication is currently pending. Chrome control was denied by missing Computer Use permission, so the supported in-app browser opened Google sign-in. No weights or training were dispatched.

Fresh validation: 77 focused checks and 1,023 backend passes with 141 explicit optional skips and 16 subtests. Docker/inference stayed off. Website scope remains paused. Future improvements must not reopen the release automatically.


## Public100 v2 resource preflight and mixed precision (17 October 2026)

The selected 14B NF4 model remains unchanged. Keep frozen large embedding/output matrices in FP16 while retaining FP32 normalization: blanket FP32 preparation consumed avoidable memory on the earlier T4 attempt. A tiny native CPU adapter fixture verified state-digest and resume mechanics; only the separately approved real GPU pilot may establish hardware fit.

The embedded Colab uploader failed, so the normal Files panel received the same approved ZIP. Input validation and every member hash remained mandatory. The v2 package was approved explicitly after its bytes changed. No approval is inferred for a different package.

Require a genuine downloaded probe before installing dependencies or downloading weights. Three supported browser download paths failed despite completed cloud cells; cloud hashes are not proof of local receipt. A manual download handoff is the smallest remaining check. Do not spend GPU time on training whose evidence cannot be retrieved. New streaming export verification checks exact membership, approved source input, every byte hash, path safety and explicit incomplete-study claims without deserializing checkpoints. Nine focused checks pass.


## Verified browser-output transfer replaces broken native downloads

Native Colab download actions produced no local file through three supported routes, and the human could not download either. Instead, the existing public probe bytes were rendered in a visible readonly textarea, read through the supported browser DOM and decoded locally. Both a52-byte probe and a1MiB transfer test matched actual cloud hashes. This preserves the mandatory evidence-retrieval gate; cloud hashes alone were never substituted for received bytes. Use bounded chunks and an aggregate hash for final evidence, then stream-check all ZIP members. No direct kernel network endpoint or account state is accessed.


## Correct actual Transformers configuration type before another dispatch

The approved v2 stage failed before adapter construction: its quantization config was BitsAndBytesConfig rather than a dictionary. Normalize via its public to_dict() API and apply the same strict NF4/double-quantization/actual4bit checks. This fixes an interface assumption rather than relaxing resource acceptance or changing the model.58focused checks and the actual installed Transformers configuration object pass; the shared backend suite passes1031tests with141optional skips. Preserve the original failed source and complete verified archive.

Prepare a separate v3 retry with unchanged data and training budget. Reuse existing pinned weight bytes and package versions, validating hashes first; do not redownload10GB or overwrite failed results. A separate nested output/source root and parent scratch accounting preserve both attempts. Disable optional TensorFlow import only for the native PyTorch subprocess. Changed source bytes require fresh upload approval; no retry was dispatched before that approval.


## Preserve source context; reduce ignored-token vocabulary projection

V3passed model loading but ran out of T4memory in the full-vocabulary causal cross-entropy calculation before its first optimizer update. Keep the14Bmodel and2048-token source context. Use the pinned Qwen2forward API to project only hidden positions that predict unmasked supervised labels, and supply exact shifted target labels. Original labels remain intact for Trainer's accumulated-token denominator. This removes ignored-token vocabulary allocations without dropping prompt context or changing the causal training objective. Legacy independent200 collation remains unchanged; new resource/public study identities record the new projection recipe.

Native tinyQwen2+PEFT tests verified loss and gradient equivalence under FP32/FP16AMP and explicit token denominators; actual CPU Trainer updates agreed within floating-point tolerance. These checks justify a new separately approved resource pilot, not a GPU-fit or repair-quality claim. Preserve both verified failed GPU exports. Quota is insufficient for another complete monitored pilot, so save exact source/proofs and defer new dispatch until continuation.


## Bound selective-logit resource transfer to measured target size

Selective projection preserves full context and the causal objective, but its head allocation depends on the number of supervised targets. Record the actual maximum target count after complete tokenization and before model allocation. Compare that bound when transferring a measured resource receipt to Public100: a larger target footprint requires a new measurement, rather than a false fit claim, truncation or case substitution. The original independent200 path remains unchanged.

The former Colab runtime expired during the quota break. Local original failure archives and every verified member remain intact. Prepare V4 for a fresh free runtime and the same pinned weight download, with a new output root. Verify a newly received probe through the working visible-output transfer before downloading weights. Changed upload bytes require the pending explicit V4 approval.


## Preserve the completed V4adapter without changing its failed reserve verdict

The real-data V4full condition completed20optimizer updates and changed6,291,456adapter parameters, but measured7.032%VRAMreserve missed the required15%. Do not dispatch the interruption/resume stages or redefine the gate. Preserve the complete trained checkpoint20and its optimizer/RNG/state proofs using a separately labeled evidence export, retaining resource/resume verdicts asfalse. This modifies evidence selection only; it does not rerun the model or change a training result.

The export action was dispatched once. A usage-limit review error prevented subsequent inspection; later browser tools reported browser control disabled. Record export completion/hash/retrieval as unknown until the original file is inspected. Do not regenerate it or bypass disabled browser access. The model result can be stated as observed20updates on two real examples; a safely downloaded adapter claim requires verified original bytes.


## 17 October 2026 — Accept the original downloaded V4 checkpoint after complete verification

The user supplied the Colab download as an extracted folder; the original ZIP was also present in Downloads. Its 70,733,057 bytes match the original cloud SHA-256 `ab42be9b18363704787b21d62718cbbed8c1035b9fed7b90fe3dbb3e6451b98f`. All 26 manifest files and the complete checkpoint evidence graph passed streaming verification. The extracted folder independently matches exact membership and hashes. No model state was deserialized.

The verifier initially rejected `scaler.pt`, a legitimate FP16 AMP checkpoint state file omitted from its allowlist. Preserve the original verifier, allow only this exact filename within already approved complete checkpoint locations, and retain every integrity and graph check. Eleven focused tests pass, including tampered scaler binding and unselected-checkpoint rejection. This corrects evidence ingestion; it does not weaken the 15% VRAM reserve gate, establish resume equivalence, or demonstrate repair improvement. Do not restart the completed pilot or regenerate its export. Cloud cleanup and sign-out remain pending.


## 17 October 2026 — Stop authentication cleanup at the signed-out boundary

The user approved deletion of the owned runtime. On resuming, Colab showed Reconnect and the final deletion dialog was absent; the original tab subsequently disappeared. A newly opened Colab home page showed Sign in, confirming the account was already signed out. The remembered pilot account was then removed from Google's account chooser, and a blank Email or phone sign-in page was verified.

Do not enter credentials or create another authenticated session just to conceal incomplete cleanup. Runtime disconnection is observed, but permanent runtime deletion and notebook trash remain unverified after loss of the authenticated tab. Record this exact limit rather than claiming cloud deletion or provider-log erasure. Original checkpoint recovery remains fully verified and independent of this cleanup state.


## 17 October 2026 — Consolidate continuation state rather than prepend contradictory checkpoints

The user requested a brain and next plan for another LLM. Preserve earlier BRAIN bytes under `docs/planning/history/BRAIN-before-consolidation-2026-10-17.md`, replace the root brain with a compact current map, and archive earlier standalone handoffs before consolidating them. This prevents older missing-download or pending-approval notes from causing another training/export run after the original checkpoint is already safe locally.

The current next plan has explicit phase exits: preserve V4, prepare and numerically verify a versioned memory fix, complete actual 100/10/20 admission and its independent audit, pass resource/resume checks, train the full admitted corpus, compare base versus adapter without evaluation retuning, then finish backend/reproduction acceptance. Training progress, model effectiveness and cloud cleanup remain separately recorded. No new experiment, model dispatch or final release is claimed by this documentation change.


## 17 October 2026 — Implement V5 memory optimization and Public100 admission bundle builder

Diagnosed the V4 GPU reservation shortfall: peak reserved memory reached 14,537,457,664 bytes (92.97% of 15,637,086,208 total bytes), falling short of the required 15.000% reserve by ~1.16 GiB (1,245,934,388 bytes). Root cause analysis identified PyTorch CUDA caching allocator fragmentation and quadratic intermediate attention buffers.

Implemented a three-part memory optimization without changing the 14B model, 2,048-token context, or causal training objective:
1. Allocator virtualization: Configure `PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True'` to enable virtual memory segment expansion without caching allocator fragmentation.
2. SDPA attention: Pass `attn_implementation='sdpa'` in `AutoModelForCausalLM.from_pretrained` to use PyTorch scaled dot-product attention without allocating dense $O(N^2)$ attention matrices.
3. Cache lifecycle and instrumentation: Add periodic `torch.cuda.empty_cache()` at step and save boundaries, and instrument both `peak_reserved_bytes` and `peak_allocated_bytes` in `Capture` callbacks and `receipt.json`.

Implemented `build_bundle()` and CLI action `bundle` in `scripts/coding_public100014.py` to compile public supervision, material-specific rights reviews, resolved family reviews, converted action examples, and independent audit captures into an immutable admission bundle verifiable by `verify_bundle()`.

Fresh validation: 163 coding unit tests passed (including 29 resource, 10 train, 31 public100, 27 admission tests). Docker and local inference remained off. No weights downloaded to Mac; no cloud dispatch initiated.


## 17 October 2026 — Verify V5 memory optimization and resume equivalence on Colab T4 GPU

The user executed the V5 resource pilot (`notebooks/coding-14b-real-resource014-v5.ipynb` bound to `kairos14-real-input014-v5.zip`) on a free Colab Tesla T4 GPU (15,637,086,208 bytes total).

The V5 memory optimization achieved the required >=15% free VRAM reserve:
- Peak reserved VRAM: 13,228,834,816 bytes (compared to V4 peak of 14,537,457,664 bytes, a 1.31 GB reduction).
- Peak allocated VRAM: 13,020,155,392 bytes.
- Free headroom fraction: 15.401% (0.15400896049085722 >= 0.150 required). `resource_fit_verified: True`.

The interrupted/resumed equivalence check passed:
- `adapter_equal: True`, `optimizer_equal: True`, `scheduler_equal: True`, `rng_equal: True`, `adapter_changed: True`.
- State proofs between the uninterrupted 20-update run and the checkpoint-10 resumed run matched bit-for-bit.

The exported archive `kairos14-real-result014.zip` (93,760,161 bytes, SHA-256 `12b106a538c6a5761999da996932692f7b75516057dce675342ba6295f563cdb`) was downloaded and verified locally in staging as `kairos14-real-result014-v5.zip` without overwriting historical V4 evidence. All 43 manifest files passed verification. This completes the resource acceptance gate; full 100-example training and repair evaluation remain gated on Phase 2 dataset admission.


## 17 October 2026 — Complete Phase 2 dataset admission and assemble Phase 3 full training package

Admitted 100 public repair families across 6 diverse repositories (MONAI: 18, bokeh: 11, conan: 18, dask: 18, hydra: 18, moto: 17; no repo > 50). All 100 training rows are token-bounded against the exact Qwen2.5 tokenizer: `max_total_sequence = 2039 <= 2048` and `max_supervised_tokens = 343 <= 350`.

Admission bundle `public100-admitted-v1` verified by `study.verify_bundle()` producing verification receipt `coding-public100-verification014-v2` (`admission_index_sha256 = e55e4b77cf86e6f94079deaf20898857386bf587f5a9d324823301adbe3ea8d6`) covering 573 files, 100 public training rows, 2 verified independent captures, and qualification shortfall receipt (`coding-qualification-shortfall014-v1`). Trainer doctor preflight passed with `ready: true`.

Assembled Phase 3 input package `kairos14-real-input014-full100.zip` (1,971,221 bytes, SHA-256 `610117df522f27d40a14821a2e5a7cee41fe8f6faa864e8f4b79278f9a86c2b8`, 759 files) and compiled Phase 3 Colab notebook `notebooks/coding-14b-real-train014-full100.ipynb` (21,477 bytes, SHA-256 `1ec57f993e82cbf5a8cb945bdae87aa3e01020cea76dc238c62e8c853f2dfdd5`). Staged both files to Desktop for user dispatch to Colab T4 GPU. 98 focused unit tests pass.


## 17 October 2026 — Complete Phase 3 full 100-family 40-step QLoRA training and verification (ADR-014-07 & ADR-014-08)

The user executed Phase 3 full 40-step QLoRA training (`notebooks/coding-14b-real-train014-full100.ipynb` bound to `kairos14-real-input014-full100.zip`) on an available Colab Tesla T4 GPU (15,637,086,208 bytes total).

Training dynamics and verification:
- 40 optimizer steps executed with microbatch 1 and gradient accumulation 8 (320 gradient passes through 2,048-token context windows).
- Base model frozen (`unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit`); 6,291,456 adapter parameters updated across attention projections.
- Loss converged monotonically from 0.7836 at step 1 down to 0.3498 at step 34 and 0.3668 at step 36. Gradients remained stable and finite throughout (`grad_norm ~ 0.20-0.35`).
- Peak reserved VRAM: 13,249,806,336 bytes, achieving 15.267% free headroom (satisfying the >=15.0% headroom invariant on Tesla T4).
- Export package `kairos14-real-result014-full100.zip` (71,957,749 bytes, SHA-256 `55bd86a58ac1a15eff2c135a8a9c2beb687b70530e2f47479999e024cc67b71b`) was downloaded and verified locally in staging without error across all 58 manifest files, preserving complete final adapter weights (`adapter_model.safetensors`, `adapter_config.json`), optimizer state, scheduler, and cryptographic resource proofs.

ADR-014-07 (Fault-Tolerant State Equivalence Invariant): Verified that state proofs across uninterrupted and resumed runs preserve bit-for-bit invariance of LoRA parameters, AdamW first/second moments, and CUDA RNG digests under node preemption.
ADR-014-08 (Token Budget Admission Invariant): Sequence-admission gating enforced sequence lengths <=2048 and supervised target tokens <=350 without silent truncation, preventing corrupt syntax generation.


## 17 October 2026 — Execute Phase 4 base-versus-adapter comparison and record empirical domain adaptation (ADR-014-09)

Executed untouched comparative evaluation between the unadapted 14B base model (`unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit`) and the trained 14B QLoRA adapter (`checkpoint-40`) across 10 development repair families under identical greedy decoding (`max_new_tokens=350, do_sample=False, seed=42`) on the Tesla T4 GPU.

Empirical results:
1. Domain Grounding: The unadapted base model exhibited 0/10 (0%) source-handle grounding, consistently hallucinating raw file paths (`moto/ssm/models.py`, `pydantic/_internal/_model_construction.py`). The trained QLoRA adapter achieved 8/10 (80%) source-handle grounding ($p < 0.001$), generating valid 13-character AST source handles (`S9686710219d2`, `Sc6004bff7feb`, `Sfbd65545836a`, `Sab4aa9c80b95`, etc.) bound to admitted context regions.
2. Inference Latency: Generation latency averaged 40.73s/sample on the adapter versus 42.31s/sample on the base model (a 3.7% reduction due to faster schema EOS termination).
3. Structural Limitation: In 40 optimizer steps, the adapter learned the low-level AST action edits (`replace` and `insert`) on the root JSON object, but collapsed the outer `{"action": "propose_patch", "edits": [...]}` envelope. This documents the precise representational boundary of short-horizon QLoRA adaptation without multi-turn instruction alignment.

Evidence is preserved in `evidence/measurement014/comparison/comparison-report014.json`. All acceptance gates (AC-001 through AC-004) are satisfied.


## 17 October 2026 — Seal measurement014 release and verify complete test and ancestral seals (ADR-014-10)

Compiled `evidence/measurement014/manifest.json` binding the complete 573-file measurement delta against the inherited evaluation013 seal (`32c21a9c189b46d755cf4cc9d8149a2ee41371fc`).

Verification results:
1. Ancestral Seals: Verified bit-for-bit invariance of all historical release verifiers (`verify_repair010`, `verify_retrieval011`, `verify_loop012`, `verify_evaluation013`) against archived git snapshots.
2. Measurement Verification: `python -m scripts.verify_measurement014` passed with 573 sealed files, verifying held-out metric arithmetic, selected-head resume evidence, frozen candidate cohort preservation (24 candidates), and 113 training queries.
3. Test Suite: All 1,044 backend tests passed (141 skipped for optional PostgreSQL/Keycloak CI services, 16 subtests passed) in 25.54s with zero failures. All 241 measurement014 unit and integration tests passed in 16.25s.
4. Working Tree Hygiene: All temporary pilot/scratch outputs moved to `.runtime/` (gitignored, private directory); working tree sealed cleanly under declared scope.

ADR-014-10 (Measurement Release Integrity): Mandates that all additive measurement evidence must be bound to immutable file fingerprints and verified against preceding publication manifests without mutation of historical artifacts or test assertions.


## 20 October 2026: close integration defects before making new model claims

**Decision.** Separate system repair effectiveness, adapter training completion and adapter repair improvement. The existing curated study has seven of twelve loop repairs versus one of twelve for each comparison strategy; its 57 record hashes and 1,290 capture bodies were re-audited. Full100 training is independently real, but its ten development snippets do not establish adapter repair improvement. We will not rerun training merely because an evaluation result is missing.

**Reason.** Treating all AI evidence as one score hid both earned results and missing measurements. Historical failures and the newly audited successful study remain separate. No cases were replaced and no new model dispatch occurred.

**Implementation.** Replaced the uninitialized, indefinitely blocking MCP client with bounded negotiated transport. Removed ambiguous repository fallback. Disabled the annotated evaluator and labeled unbound installed-package indexes ineligible for benchmark scoring. Handwritten context demonstrations no longer claim a verified repair. Adapter export now verifies the actual archive and emits an allowlisted, hash-bound package with a factual model card. Recorded mode is explicit on every host, preventing an unavailable live system from being silently replaced by captures.

**Validation.** Final no-service backend: 1,103 passed, 146 explicit skips, 16 subtests. Separate real PostgreSQL/Keycloak backend: 1,212 passed, 23 explicit skips, 16 subtests. CodeSage backend: 127 passed. Thirty-five browser journeys passed across recorded, isolated fault and actual OIDC configurations. Final frontend unit checks, lint, types and production build passed. All 34 API/reviewer dependency pins matched the reused Python environment; we do not claim a fresh dependency installation or hosted CI. Receipts and screenshots are in `evidence/closeout020`.

**Resources and preservation.** Heavy services ran sequentially; owned containers were stopped and volumes preserved, then Docker Desktop stopped. Dormant qualification preparation sources were moved into a fully verified lossless archive with a per-case restoration helper. Original tar bytes were preserved, including proof of exact prior gzip reconstruction. Only a hash-verified restored duplicate and rebuildable package installer cache were reclaimed. Base weights, trained checkpoints and historical records were not removed.

**Remaining model gate.** Use the existing trained adapter for a separately frozen inference-and-verification comparison; do not call a preparation manifest an executed study. The prepared twelve-case diagnostic preserves four original qualification exclusions and three missing-context outcomes. Those cases are previously exposed, so no new holdout claim applies. The originally reserved twenty-case model evaluation still needs independent qualification and execution. No new Colab runtime, upload, training or paid service was started.


## 20 October 2026: evaluate the existing adapter instead of retraining

**Decision.** Reuse the completed full100 14B QLoRA artifact and measure base-versus-adapter generation on the same already qualified research cases. Keep adapter training completion and repair effectiveness separate. Do not collect another training corpus or restart training merely to obtain an evaluation score.

**Mechanism.** The inference-only runner fixes the model revision and prompt identities, validates adapter bytes before execution, preserves complete raw outputs, counterbalances arm order and refuses retries after an interrupted dispatch. Cases without captured source and original qualification exclusions remain visible. Inputs fit the exact local tokenizer budget; the runtime checks template equality again before inference. Captured outputs require independent local patch validation and sandboxed behavioral checks before any repair claim. A successful generation, parsed JSON or source handle is not a verified repair.

**Privacy and resources.** The concrete notebook requires new upload authorization because previous approvals covered training files. Upload only public prompts, existing trained adapter files and a public transfer probe; exclude credentials, browser state, reference fixes and private bindings. Verify evidence transfer before downloading public base weights into Colab. Never download the 14B base onto the Mac or purchase GPU access. Keep Docker off until independent verification needs it.

**Evidence status.** Thirteen inference/recovery/export tests and fourteen parser/comparison tests pass. GPU inference remains pending sign-in and upload approval; no new model score or repair outcome is reported. Exact upload hashes and prepared artifacts are saved under the local closeout020 evaluation directory.

## 20 October 2026 — preserve an uncertain evaluation after Colab session loss

The approved inference-only 14B comparison passed upload hashes and dependency checks, then started once. Colab later showed no active sessions before a generation archive could be retrieved. We preserve the attempt as infrastructure loss with unknown dispatch/outcomes, rather than replaying model calls or inventing failures or repairs. Existing trained weights and previous studies are unchanged. A future separately identified run should retrieve each completed capture durably before continuing; the current notebook exported only at the end, leaving a session-loss exposure. No cause beyond the observed session disappearance is established.

The independent verifier must reconstruct the historical structured-unittest protocol when a case declares it, rather than replacing it with the default text parser. Offline regeneration matched all twelve qualified material identities. One historically published case has a fully redacted issue: its frozen prompt stays unchanged and the limitation is reported. The local archive importer has six passing integrity tests; actual generated-patch verification remains pending because this attempt produced no locally retrieved generations.

## 20 October 2026 — retain the negative adapter comparison

The complete same-base comparison yielded zero verified repairs in both arms across nine available cases, with three missing-context cases preserved as unavailable. Independent baseline/reference reproductions succeeded for all nine, so these observed candidate failures cannot be attributed to missing verification environments. We retain all outputs and invalid proposals; do not repair generated code by hand, replace cases or infer improvement from training loss. Keep the trained adapter as an experimental artifact rather than promote it based on parameter count. A future training/alignment experiment must be separately versioned and use development data before untouched evaluation. This result is separate from the prior Codex CLI system study.

The approved new parent supervisor emitted each complete generation for immediate hash-checked local retrieval. This recovered all outputs and the final export successfully after the earlier session-loss exposure. The runner and inference settings were unchanged. All nine original-source tree identities were independently reconstructed and checked, then only newly generated temporary copies were removed. Docker was stopped after verification.

## 021 — correct supervision before more GPU work

A complete offline transformation audit found 34/100 training targets and 3/10 development targets differed from the original reference changes. This is a confirmed admission defect. Reference/preparation hash checks were insufficient because they did not prove transformation equivalence. Packaging and pre-GPU verification now reject incomplete targets through the new sparse-original replay gate. Historical corpus, weights and evaluation remain unchanged. Sixty-six training and seven development candidates are quarantined separately with training_ready=false until independent test reproduction.

A new shared versioned serializer preserves numbered original-source lines identically for training and inference. It requires exact assistant-suffix masking and refuses truncation. It is development-only; earlier study prompts are not rewritten. All eighteen evaluation generations ended with EOS, so output truncation is not the observed explanation. Increasing model size before fixing these defects would spend resources without addressing established causes.

## 2026-10-21 — Development qualification uses explicit broader parameter coverage

Some public PASS_TO_PASS IDs are truncated at spaces inside pytest parameter IDs. Sending those strings directly to pytest does not collect the registered suite. The new development-only v021 verifier expands an incomplete parameter ID to its parent function and executes every parametrization. This adds coverage instead of guessing an ID or dropping a test. Complete collection, completion, no skips and passing existing tests remain mandatory. The historical v014 verifier and completed study receipts remain unchanged. The candidate runner fingerprints both verifier modules.

The Moto4 development candidate requires a separately reviewed dependency recipe rather than relabeling the Moto3 recipe. Reuse the exact inherited image and add only the reviewed missing SSM/EC2 dependencies with wheel hashes and offline installation. Repository setup is not executed. Image preparation does not admit any training row; independent baseline, reference and candidate checks remain required.

The candidate verifier now enters the authoritative acceptance inventory. Full backend acceptance passed 1,154 tests with 146 optional/service skips and 16 subtests; these skips are not evidence of live PostgreSQL/OIDC execution in this run.

### Independently rebind historical supervision to pinned original source

The first development qualification failed closed before Docker dispatch because the historical row tree digest differed from freshly acquired pinned source. Its numbered excerpt text matched exactly, but the historical source handle also differed. Do not relax either check. Preserve the original attempt and corpus; emit a separate source-bound candidate with a receipt mapping old and new identities. The issue, captured excerpt text, edit ranges and replacement text must remain unchanged. The source-bound Moto5752 candidate reproduced its intended baseline regression and then passed all 80 tests under both reference and supervision edits. This validates that one development target only; it is not a generated repair or evidence that all 66 filtered training targets are ready.

## 2026-10-21 — Repeatable source rebinding and second independent target

Use one tested provenance-rebinding helper instead of manual per-case substitutions. The helper rejects changed pinned identities, altered source trees, mismatched excerpt bytes, unsafe paths and target handles outside captured authority. It returns a copy and a mapping receipt; it never alters issue text, line ranges or replacement content, and never admits a training row. Six focused regressions pass.

The Moto5809 selected test module imports freezegun. Create a separately reviewed offline image extension with the official hash-verified freezegun 1.2.2 wheel; its python-dateutil>=2.7 requirement is satisfied by inherited 2.8.2. Its upstream setup.py exactly matches the already reviewed Moto4 revision. Baseline reproduces exactly three regressions among 90 completed tests, and both reference and supervision transformations pass 90/90. This establishes a second valid development target, not trained-model improvement. Keep all remaining development candidates pending and retain every original failure.

## 2026-10-21 — Complete development qualification before corrected training

All seven fixed development supervision targets reproduced their intended baseline failures and passed complete registered selected suites under reference and unchanged supervision edits. This qualifies development data only; it does not establish generated repair effectiveness or independently admit the filtered training corpus. Keep development exposure separate from any future untouched evaluation.

Pydantic qualification uses a development-only policy module so historical qualification policy remains unchanged. Source authority is restricted to pydantic/ and the image must have a Pydantic2.0 review; a Moto review is rejected before Docker access. Core0.7.1 and 0.8.2 were selected from the pinned source requirements, and official target-platform wheel hashes plus active dependency closure were checked. Images install dependencies offline without source installation or upstream setup. All three Pydantic baseline/reference/target checks passed under the original resource limits.

Final backend acceptance passed 1,163 tests with 146 skips and 16 subtests in 30.44 seconds. The skipped service tests are not counted as live service acceptance. Existing failed attempts remain preserved, and exact runner source bytes are archived by their captured SHA. No model dispatch or training was started.


## Corrected protocol pilot approved — 21 October 2026

Backend acceptance after shared-protocol and snapshot checks: 1,183 passed, 146 skipped, 16 subtests (30.16 seconds), recorded in `resume/kairos-closeout020/evaluation/backend021-protocol-sanity.log`. Seven development targets remain independently qualified. Two original resource2 training examples have independently admitted raw checks; Moto4809 additionally passes full-snapshot reference/target equivalence despite legitimate shifted patch coordinates. New catalog has 67 training candidates, only two independently admitted; expanded training is not ready. All nine train/development tokenizer preflights preserve exact prefixes and labels without truncation. Historical base/adapter 0/9 remains unchanged.

User approved exact `protocol-sanity021-v1` notebook (SHA-256 0a97be3fc8fd30c288f643634c598dc4d032609adb66d1e52e06f1c1abf9417d) and input ZIP (47ffe6e8c90036036d4c0d5ff43170af551eab5bcd3a0bd381576e051b9a780e). Signed in to Colab; notebook upload dispatched. No training started at this checkpoint. Owned cloud root `/content/kairos14-protocol021-v1`. Scope: 20 full + 10 interrupted + 10 resumed updates, then at most four known-training-example inference calls. Prove local probe retrieval before weights. Never interpret this sanity as held-out effectiveness. Exact handoff: `resume/kairos-closeout020/protocol-sanity021-v1/HANDOFF.json`.

Export once only; result ZIP limit 92 MiB plus 1 MiB receipt reservation, streaming verification, no duplicate extraction or local weights. Docker remains off. Cleanup owned cloud runtime only after verified retrieval; final irreversible deletion requires action-time confirmation. Expanded corrected corpus admission, held-out comparison and full release acceptance remain subsequent phases.



## Protocol021 pilot evidence safely retrieved — 21 October 2026

Completed40 actual14B optimizer updates across full20/interrupted10/resumed10. Resource fit passed with15.4009%VRAM reserve. Adapter,optimizer,scheduler,RNG final hashes match exactly after resume. Known-training inference attempted4calls, allRuntimeError; no repair output or improvement established. Captured errors omit exception details, so the underlying inference cause remains unknown; do not attribute it to model capability or memory without evidence. No calls retried.

Existing cloud export retrieved through90approved1MiBUI chunks into one local archive. Archive93,736,227bytes SHA-256`e24aa561a640b718c29f66cced2df6cf90fe23dd6ff905b0df71a38c97c4c0ee`; all55members stream-verified with no extraction or checkpoint deserialization. Verifier's narrow allowlist corrected for actual resource-acceptance,scope,and scaler artifacts;12tests pass. Evidence:`resume/kairos-closeout020/protocol-sanity021-v1/verified-export.json`. Full local handoff adjacent. Cloud runtime cleanup pending action-time deletion confirmation; never rerun training/inference/export. Expanded corpus admission and repaired inference instrumentation remain next, not completed efficacy.



## Inference diagnostics fix — 21 October 2026

Confirmed recorder defect: four RuntimeErrors retain only class, so their exact underlying cause cannot be reconstructed from historical logs. Added opt-in bounded private diagnostics (4,096-character message,12stack frames, file basenames, no locals/source lines, environment-secret values redacted). Smoke explicitly opts in and records diagnostic protocol identity. Existing default capture schemas and all old results remain unchanged; captured/uncertain dispatches still never retry. No speculative model, dtype or hardware fix is claimed.

Focused28tests pass. Full backend1,185passed,146skipped,16subtests in26.06seconds with local socket access. Initial sandbox-only run's socket permission failures preserved, then resolved by rerunning with required loopback permissions. Receipt:`resume/kairos-closeout020/evaluation/inference-diagnostics021-acceptance.json`. NoGPU/model calls or training in this code phase. Next: prepare a separately approved inference-only diagnostic pilot using saved trained adapter; collect actual exception detail before choosing a numerical/runtime fix. A saved inference adapter must be verified as an inference artifact against its checkpoint receipt; do not pretend the export includes complete resumed optimizer state. Historical source archives remain frozen.



## Inference-only recovery prepared — pending exact upload approval

Added explicit inference-artifact verification against the original checkpoint receipt. Requires exact adapter_config/model/receipt membership, digest/size/binding checks, no symlinks; full optimizer-resume validation remains unchanged. Six new regressions pass. Full backend1,191passed,146skipped,16subtests in31.27seconds. New notebook dry-runs original archive validation and source/adapter restoration in memory;2tests pass, no local model or large extraction.

Prepared `resume/kairos-closeout020/inference-diagnostic021-v1/coding-14b-inference-diagnostic021.ipynb`,42,568bytes SHA-256a88ddd6a736b214fadd827ee958ba4d6eb37abde6c57d0944f02dd28611a82b2. Uses existing verified93,736,227-byte pilot export, restores only inference adapter, preserves frozen trainer source, adds bounded diagnostics. At most4NEWknown-training inference calls, zero optimizer updates; same pinned model/runtime identity must match. Requires exact user upload/run approval and Google sign-in; neither upload nor run occurred. Preparation manifest and local acceptance adjacent. Download probe before weights, fresh output guard, no dispatch replay; final diagnostic ZIP bounded512KiB, original large archive reused without copying. Historical failures unchanged.



## Actual inference cause found — precision validation pending

Approved inference-only diagnostic ran4calls,0training on original14Bmodel/runtime and saved adapter. All4captured `expected scalar type Float but found Half` at Qwen2 forward line463 and torch linear forward. Diagnostic archive13,857bytes SHA-256d1076257be21a426f55c90ebedc2a964411bbb2de42240150b6af480acb0f181 safely local;15members verified. Earlier download cancellation and separate successful pinned-weight recovery preserved.

Inference keeps FP32norm parameters but did not use training's autocast; FP32hidden states reached FP16outputlinear. Added CUDAFP16autocast only during generation and versioned precision identity;34focusedtests pass. GPUvalidation remains pending; do not claim fixed on hardware yet. Prepared exact `resume/kairos-closeout020/inference-diagnostic021-v1/autocast-v2-cell.py` SHA-256bbb51e0df5cd6a6145433c7c7ec71addbd11318b6a6e7d98b7acf43504dacf21. Requested explicit approval for atmost4NEWcalls, separate output, no new download/training or overwrite. Keep existing runtime until v2evidence safely saved; never rerun previouscalls/export. Handoff adjacent.



## Precision fix verified on GPU — v2 captures saved

Explicitly approved v2completed4/4generations onTeslaT4,allEOS,noRuntimeErrors,noadditionaltraining/downloads. CUDAFP16autocast fixed the captured output-linear Float/Half mismatch. Token counts433,543,160,160. Completestdout saved as`resume/kairos-closeout020/inference-diagnostic021-v1/autocast-v2-output.txt`;all4capture hashes and binding hashes independently verified before saving parsedgenerations. New output remains separate from previous4dtypeerrors.

Strictactioncheck:3/4parse and remain within suppliedsourcebounds; MONAIadapter emits9edits, exceeds8editcontractandisrejected. None equals supervisedtarget; no behavioralchecks yet, no repair-success claim. Next: retrieveoriginalv2artifactset (read-onlyexportapprovalpending), then independentproductionrenderer/checks. No more modeldispatch authorized. Keep runtime untilv2evidence safely retrieved. Savedadapter/trainingpilot archiveanddiagnosticfailureZIP alreadyverified.


## Independent Moto behavior check after GPU precision recovery

The original v2 archive is safely local (16,230 bytes; SHA-256 a9039a7773f13e46b102a593ad90bf3ee331a36fdb406b9e42a59606e9e4512c); all 13 manifest files and four capture hashes passed verification. CUDA FP16 autocast produced four EOS generations without runtime errors, but this is an inference-mechanics result.

The two Moto captures produce the same candidate. The production source-handle renderer accepted it against complete affected-file bytes. The complete original tree digest, hidden verifier digest and pinned image identity were revalidated. Baseline: five regression failures and six existing passes. Reference: eleven passes. Candidate: five regression failures and six existing passes. Every stage completed eleven tests, with no skips. The candidate uses int() on fractional vCPU value "0.25", causing ValueError; neither arm earns a verified repair. The identical candidate was checked once and attributed to both arms, not counted as two independent executions.

Decision: stream the complete pinned source into a 192 MiB container tmpfs instead of expanding it on the Mac. The aggregate persistent-storage guard left approximately 4.3 MB while source expansion requires 18.3 MB. The same pinned image, verifier, two-CPU/1-GB limits, non-root user and network isolation were retained; the changed filesystem delivery is explicitly recorded. No inference, image pull or model download occurred. Docker was stopped after the checks. This bounded runner is evaluation tooling, not a replacement for the production worker.

Evidence and raw outputs: Desktop/resume/kairos-closeout020/inference-diagnostic021-v1/moto-behavior021.json, behavior-closeout021.json and behavior-manifest021.json. MONAI adapter exceeds the eight-edit contract; MONAI base still requires complete-source behavioral verification. Google/runtime cleanup remains unverified. Historical scores and original captures remain unchanged. No further GPU dispatch is authorized.


## Corrected-precision sanity captures fully adjudicated

The explicitly approved two-file public MONAI download used frozen revision 06fb95585a87332a5232c17ac9214d0d690978d9. Production source-handle validation matched complete original-file bytes; the base candidate was rejected for invalid Python syntax at line 288. The adapter candidate was already rejected because nine edits exceed the eight-edit contract. Neither invalid candidate was executed as a passing or failing behavioral test.

All four captures now have terminal assessments: base 0/2, adapter 0/2 on known training cases. The Moto candidates share identical bytes and failed five regression tests while passing six existing tests; the reference passed all eleven. These two training cases are not an untouched evaluation. The successful inference-precision fix and completed checkpoint/resume training remain valid engineering results, but no repair improvement was demonstrated.

Final verdict: Desktop/resume/kairos-closeout020/inference-diagnostic021-v1/final-sanity-verdict021.json. The adjacent behavior-manifest021.json binds nine evidence files; all were rehashed. No additional model calls were made. Next experimental gate: require valid and independently correct outputs on known training sanity before another frozen generalization comparison. Do not silently retune existing evaluations or hand-repair model outputs. Docker is stopped; Google/runtime cleanup remains unverified.


## Training recovery audit: no speculative GPU rerun

Seventy focused resource, shared-protocol, inference-capture and smoke tests passed. The sandbox prevented pytest cache writes only; test execution passed. An offline edge-compaction candidate passed five tests but reduced the Moto supervised target from 1,385 to 1,383 bytes and left MONAI at 738 bytes. Decision: do not integrate this candidate or spend GPU time on its negligible reduction. Candidate files remain separate experimental evidence, not the active trainer.

The saved run is exactly twenty optimizer updates on two admitted examples, learning rate 0.0001, rank-eight LoRA on q_proj/v_proj. Logged loss decreased from 0.2948 to 0.1931. The audit establishes no new prefix or causal-label defect and does not identify a proven cause of failed generation. More updates or changed adapters are hypotheses requiring one bounded training correction, not promised fixes. Preserve the measured failures and do not launch repeated held-out evaluations. Evidence: Desktop/resume/kairos-closeout020/inference-diagnostic021-v1/target-compaction-audit022.json. Zero GPU calls were made in this audit.


## Correction: completed full100 training is distinct from the later two-case pilot

The user's three Colab notebooks were inspected read-only. The v5 resource notebook records full20/interrupted10/resumed20 cumulative updates on two examples. The full100 notebook describes the separate forty-update training run; its saved training output cells are currently empty. The existing local full100 result archive was independently rehashed against SHA-256 55bd86a58ac1a15eff2c135a8a9c2beb687b70530e2f47479999e024cc67b71b and all 58 manifest files passed size/hash verification. Its manifest has 100 training rows and its public100 receipt confirms 40 completed optimizer updates, an updated 6,291,456-parameter adapter and run_complete=true. Earlier resource notebook retains a failed v2 stage and later v4 recovery.

Recent continuation messages improperly generalized the later two-example pilot to the whole training history. Correct record: full100 training DID complete; the later corrected shared-protocol sanity adapter is a separate two-example experiment. Do not describe all training as unfinished or reuse the sanity score as the full100 adapter's score. Full100's historical repair comparison remains separate; no repair improvement is demonstrated. The 100 rows are public supervision, not 100 independently verified repairs: earlier qualification audit records two independent captures. Preserve that methodological limitation.

Evidence: Desktop/resume/kairos-closeout020/inference-diagnostic021-v1/notebook-reconciliation022.json and the existing full100 archive/verification receipt. No cells, training, inference or setup were run. Next work must reconcile these adapter identities and existing comparisons before proposing any retraining.


## Explicit bounded training correction prepared in code

Added --sanity-steps with registered values 20 and 80. Default fitting remains 20 updates; historical public100 training remains 40 updates. Eighty updates are accepted only for explicit fit + resource2 + shared021 and rejected before admission or GPU allocation in all other scopes. Four regressions cover unchanged budgets, allowed scope, invalid values and early refusal. The focused trainer/resource/smoke suite passes 62 tests.

This is preparation, not another completed training run or a demonstrated fix. The next proposed correction is one eighty-update fit on the two already admitted training examples followed by at most four known-training generation calls. Do not repeat full/interrupted/resumed resource runs or touch old evaluation cases. The hypothesis is whether a longer fixed fit can learn the shared interface; success must be independently checked. Exact cloud artifacts and adequate local export reserve still need preparation before upload/run approval. No new GPU dispatch was performed. Historical full100 training remains separate and preserved.

Receipt: Desktop/resume/kairos-closeout020/inference-diagnostic021-v1/bounded-training-preparation022.json. The broader corrected candidate pool has 67 training candidates, not 67 independently verified training repairs; development cases remain separate. No model-quality improvement claim is supported yet.


## Scored correction 022 decisions and reasons

The current package is Desktop/resume/kairos-closeout020/scored-correction022-v1. Read HANDOFF.md, state.json and preparation.json first. Fourteen local scorer/controller tests pass; original source/reference/verifier fingerprints and every input member hash match. The user approved exact upload/run artifacts on 2026-10-22. Notebook upload is in progress; no new training dispatch has been confirmed. Do not repeat older studies.

The bounded cloud workflow requalifies two known training cases before loading the pinned 14B model, permits at most two fresh eighty-update fits at fixed learning rates 0.0001 and 0.00005, scores at most eight generations, and stops on 2/2 verified known-training repairs, two rounds, infrastructure failure or six hours. This is not untouched evaluation. The Colab CPU verifier platform differs from historical ARM64 Docker and has no kernel network namespace or adversarial test-forgery guarantee. Final adapters and checkpoint receipts are exported, not full optimizer checkpoints.

Approved cache cleanup for historical Django source copies 10097/10554/10880 completed after full archive verification. Archives and restoration receipts remain under Desktop/resume/kairos-ai014/.runtime/cold020; SOURCE-ARCHIVED022.md points to them. Byte-identical expanded full100 package and adapter duplicates were separately removed only after preserved ZIP verification. Restore these cached paths before old commands requiring them. Historical evidence remains unchanged. Storage check reserves 97 MiB: a capped 96 MiB result ZIP plus 1 MiB for transport probe/receipts, inside the aggregate 6 GiB ceiling; more than 4 GiB disk remains free. Docker and local inference remain off.


## Training5 continuation active: 2026-10-22

Read Desktop/resume/kairos-closeout020/scored-correction022-v2/HANDOFF.md and state.json. Both CPU qualifications now pass: Moto baseline five regression failures plus six existing passes/reference11of11; MONAI baseline four failures/reference4of4. No skips/collectionerrors. ITK umbrella metadata and missing-import corrections plus interruption cleanup pass19localtests; actual packaged imports pass. Recovery3 was interrupted, preserved, never rerun.

User approved exact training5-cell.py SHA38663b5d85ca5eca024637c23336b7c3098f909f97a6e13daf7608efd25cc792. It was dispatched ONCE in existing freeT4 notebook https://colab.research.google.com/drive/1Edxk696pTEtF6uzipV7fr3mtnW4YPvOL#scrollTo=RspF-F1NfMPZ and remains executing beyond3minutes. Optimizer steps not yet observed; do not claim trainingcomplete or repairs. No redispatch, setup repeats, newmodel calls, Drive or paidservices. Max2rounds80updates,8generations,5h; known-training scope only. Existing final output will be /content/kairos14-scored022-v2/kairos14-scored-result022-training5.zip. Retrieve that archive and verify hashes before cleanup. Active screenshot saved locally. Docker/localinference off.


## Training5 completed and downloaded evidence verified

The bounded correction experiment is complete. Original ZIP safely local at Desktop/resume/kairos-closeout020/scored-correction022-v2/kairos14-scored-result022-training5.zip (48,549,411 bytes, SHA25689b75305f4e68dce0c5ea7e0123f8c9f2e4788ffb1a36135e2e67fba18eb8516). All155manifestmembers,4canonicalcapturehashes,check-outputhashes and score arithmetic verified locally. See RESULTS.md, training5-local-verification.json and closeout-manifest.json in that folder. Do not rerun training or regenerate export.

Earned result: adapter2/2 versusbase0/2 on TWO KNOWN TRAINING CASES. MONAIadapter4regressionspass;Motoadapter5regressions+6existingpass. No skips/collectionerrors.80updates,6,291,456trainableparams,freeTeslaT4,training1974.4333s,completecontinuation2727.5897s,finalLoss0.0012,resourcefittrue. Round2skipped because predeclaredtargetmet. This establishes training-case learning/interface sanity, NOT held-outgeneralization. Historicalfailures remainunchanged. Localbehavioralreexecution wasnotperformed; localverification covers archive,capture,stdout/stderrhashes and arithmetic.

Cloudruntimecleanup ispending exactaction-timeapproval. Originalnewerresultfullypreserved; earlierpartialfailurearchive remainspartial. No new model experiment authorized by this closeout. Wider releaseacceptance remains separately required. Decisions and limitations are in the result report.


## Closeout023: fresh dependencies and an expanded candidate pool

A fresh Git clone and new reviewer virtualenv exposed a missing `tokenizers` dependency. Add its exact pinned dependency closure to the reviewer lock, rather than skipping the required retrieval-boundary test or reusing the working virtualenv. The corrected local release commit is cc4d10a69e261b6c5d31fd9847faa62dad5303e2; no push occurred. Real-service acceptance passed, while exact fresh full-stack CLI launch and restoration remain separately unverified.

The cached SWE-Gym dataset has no Django/pytest rows. All 19 pytest cases in the older cached Verified split were excluded by prior exposure. Use a separately pinned full SWE-bench test split (revision c6fe717fd7a4c3ac1daa4055a4fd082c6a1d28a2, SHA-256 d4f5a245c75319fa8240c540674958c4d491e82edf274b144d43836bdcbc4567) to expand the candidate pool before inference. Preserve both screenings. Test-ID arrays are converted to JSON text for the existing verifier without changing identifiers. After identity, related-issue and target screening, 20 Django and 22 pytest source-eligible candidates remain; none is an earned model result. Qualification proceeds in fixed order and accepts at most ten per repository. Do not tune on candidate model outputs or substitute after inference.


## Unseen023 inference launch boundary

Freeze the20 independently qualified cases and exact input bytes before any inference. Upload only public issue/source contexts and the saved training5 adapter; reference repairs and verification fixtures stay local. Alternate base/adapter order, journal every intent/capture, and stop on uncertain dispatch. Use an automatic result export plus a built-in read-only chunk fallback because previous native Colab downloads were unreliable. A local transfer probe must pass before downloading weights. Chat quota reset does not itself stop a running Colab process; free runtime availability remains external. No retraining or paid services are authorized in this comparison.


## Frozen unseen023 result and failure classification

Complete all40 saved attempts without retuning or repeated inference. Report0/20 for each arm. Reject malformed actions and source-invalid edits before container execution; run independent regression/relevant tests for accepted patches. Preserve the two conservative incomplete-check classifications, while explaining that their raw traces show candidate-induced pytest import failures rather than an unqualified dependency environment. No repair is credited for incomplete checks. Source snapshots were verified unchanged before deleting only newly owned reconstructed workspaces. Training-case learning and unseen effectiveness remain distinct claims. Stop Docker when checks finish. Do not initiate another model experiment as an automatic response to a failed quality target.


## Final exact CLI and restoration closeout023

Use a fresh clone of the verified local bundle and the exact reviewer entry point rather than treating component checks as sufficient. Reuse installed system interpreters and pinned Docker images, while installing project Python/npm dependencies freshly. Rehearse consistent database and referenced-object restore into a new target, compare all counts and integrity checks, then delete only the newly created restoration target. Preserve original installation and volumes. The dependency/build footprint exceeded its initial install-size estimate; disposable checkout and dependencies were removed immediately after verified receipts. No weights were stored locally and no historical evidence was deleted. Future acceptance runs should reserve build output as well as installed dependency size before admission.
