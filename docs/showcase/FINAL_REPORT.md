# Delivery 008 final evidence report

## Completed release

The website distinguishes the evidence viewer from live execution without a negative global slogan. Workbench provides executable local setup;  home and walkthrough open the same earned development case. A professional README covers purpose, architecture, workflow, operating limits, measured results and receipts. The preserved fresh evaluation remains 0/10.

## Acceptance

| Gate | Actual result | Receipt |
| --- | --- | --- |
| Complete backend | 434 collected; 428 passed; 6 explicit skips; 0 failures/errors | [Backend](../../evidence/docs008/checks/backend-summary.json) |
| Frontend | Boundary/client/package checks, lint, types, recorded/live builds passed | [Aggregate](../../evidence/docs008/checks/fullstack-acceptance.json) |
| Evidence viewer | 8 browser journeys passed | [Recorded](../../evidence/docs008/checks/recorded-browser.json) |
| Interaction faults | 11 isolated browser journeys passed | [Fixtures](../../evidence/docs008/checks/fixture-browser.json) |
| Real authentication | 4 actual PostgreSQL/Keycloak journeys passed | [OIDC](../../evidence/docs008/checks/fullstack-browser.json) |
| Actual model execution | 1 separate browser journey passed; 2 model calls, 1 candidate, 4 passing tests | [Live run](../../evidence/docs008/live-execution/receipt.json) |
| Private runtime | Ownership, roles, credentials, Git exclusion and isolation checks passed | [Preflight](../../evidence/docs008/checks/private-runtime-preflight.json) |

Twenty-four browser journeys comprise the 23 control-plane/inspection cases plus the separate real-model journey. The latter is an exposed Django development case with an issue-provided repair hint. Its 35.100004-second worker execution excludes installation, startup and qualification. It does not change locked validation or establish general repair effectiveness.

The aggregate acceptance used a newly provisioned isolated runtime with generated credentials and inference off. The actual inference run used a different owned runtime, preserving its completed investigation and volumes. Public receipt copies substitute logical checkout/home paths;  original private files remain unchanged and their hashes are recorded.

## Reviewed fixes

- Replace the ambiguous global banner with an evidence-viewer label and live-setup link.
- Make reviewer inference an explicit opt-in with pinned assets and bounded ownership.
- Stop model startup if its ownership receipt cannot be written.
- Reject changed profile/cache/case-root when reusing a running session.
- Attempt cleanup even when process metadata, receipt writes or signal restoration fail. Never signal unverified PIDs.
- Record browser success only after logout verification.
- Exclude generated .next* output from source lint for repeatable acceptance.
- Fix private-state Git quiet mode to check each pathname independently. The real-Git regression confirms fully and partially ignored cases.

Earlier attempts stopped on stale capacity-copy assertions, generated-output lint and the Git checker’s unsupported two-path quiet call. These were fixed with focused regressions and the complete reviewer command then passed. No failed model attempt was rewritten as a success.

## Preserved evidence

Original build007 source/archive/index/receipt, 122 published records/1243 blobs, model profiles and frozen studies remain unchanged. The 435,270-request control-plane study, failed earlier runs, 110-test Django reproduction and operational restoration drills retain original receipts. Newer 0/10 and historical 0/10/0/36 outcomes remain visible. The uncertain free-provider request was not resent.

## Handoff

Use `python3 -m scripts.reviewer demo` for the lightweight reviewer path. Use the [explicit live command](OPERATIONS.md#live-repair-execution) for prepared local execution. Use `python3 -m scripts.reviewer check --fullstack` for full acceptance and scoped `stop` for owned services.

The delivery manifest binds presentation/bootstrap changes to the preserved seal. The sanitized publication snapshot excludes credentials, sessions, installed dependencies and model weights. Source/archive and clean-extraction verification have separate packaging receipts. Docker and inference are stopped after heavy work;  only the lightweight website runs at handoff. No repository push, PR or public hosting was performed.
