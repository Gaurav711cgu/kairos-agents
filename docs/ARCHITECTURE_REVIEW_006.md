# Kairos build006: engineering and AI architecture assessment

Review date: 2026-10-13. This assessment describes the local release and its evidence. It does not confer a hiring decision, professional title or demonstrated personal code ownership.

## Verdict

Kairos provides credible early-career SDE and AI infrastructure interview material: a full-stack investigation workbench, durable command/recovery boundaries, typed source tools, bounded verification, reproducible inspection and preserved failures. Release acceptance and archive verification are the completion gate; their exact results are linked from the final report.

**General repair effectiveness fails the declared evidence bar.** Fresh v5 validation earned 0/10 verified repairs; the older comparison remains 0/36. Six new verified development attempts cover one issue-hinted Django defect. Reliable software does not turn those model outcomes into successful repairs. Position the project as investigation and evaluation infrastructure, with limited repair demonstrations.

## Review by discipline

| Area | Verdict | Evidence and practical boundary |
| --- | --- | --- |
| Frontend architecture | Pass within local scope | Transport, command journal and workbench state are separate. Abort/generation checks reject stale reads; polling respects visibility and terminal state. The evidence inspector presents source, patch, checks and paired cost. Recorded browser acceptance covers keyboard controls and 390px layouts. |
| API design | Pass | Registered task/configuration inputs, stable command identities, explicit conflicts, progress without artifact bodies, cursor lists, cancellation, fresh forks and execution-free replay. Public endpoints expose only published records. |
| Authorization | Pass within local scope | Actual Keycloak OIDC, PKCE/state/nonce, opaque HttpOnly sessions, server membership checks, origin checks and role-gated publication. Real browser journeys exercise roles and cross-tenant record/progress/download/cursor denial. Public HTTPS deployment is not tested. |
| Database and command consistency | Pass | Tenant-scoped idempotency, synchronous acceptance, serialized quotas, additive schema changes and stable creation-time/ID pagination. One global execution slot is a deliberate laptop limit, not horizontal scale. The active investigation pool has eight connections, 32 waiting borrowers and a five-second acquisition timeout per process. |
| Concurrency and recovery | Pass within tested boundaries | Database-clock leases and fencing reject stale commits. Captured results resume; uncertain dispatches stay unknown. Cancellation prevents later writes but cannot undo inference already sent. New SIGKILL drills use explicitly labeled provider fixtures; historical real-model drills remain separate. |
| Storage and evidence | Pass within local scope | Original content-addressed bytes are fsynced before references commit. Loaders/downloads verify hashes, schemas, ordering and references. Fresh database/object restoration is checked. Hashes do not provide signed provenance or administrator-proof history; orphan bytes can survive rollback. |
| Patch and sandbox boundary | Limitation | Source paths, symlinks, excerpt identity, overlap, syntax, file/line budgets and output are constrained. Registered checks run non-root without network, credentials or Docker socket. Trusted host/recipes remain assumptions. Candidate Python shares the verifier environment; adversarial test-forgery resistance is not established. |
| Context and loop engineering | Pass within tested protocol | V5 fixes a diagnosed source-authority defect, retains original source independently, records omissions, binds compact exact edits and checks accepted patches immediately. Calls, applied candidates, checks and deadlines are bounded. New runtime guards reject incompatible model/context/slot declarations before dispatch. |
| AI repair quality | **Fail** | Fresh 0/10 and historical 0/36; no demonstrated broad repair competence or loop superiority. The public Django11066 issue supplies the suggested fix, and source entry files were human-localized. |
| Evaluation design | Pass with substantial limits | Baseline/reference qualification precedes inference, configurations are frozen, exclusions and unsuccessful attempts remain recorded, and development is separate. Public cases may be contaminated. Five cases missed the six-case qualification target. Small curated cohorts do not establish representative performance or a leaderboard result. |
| Verification independence | Limitation | Reference fixes and hidden verification files remain outside source read/search tools. Check output is feedback-visible and can reveal assertions. This is an independent execution mechanism with feedback, not an unseen blind final holdout. |
| Operations and reproducibility | Pass when final release checks pass | Owned isolated services, locked installation, recorded inspection without inference, fresh repair reproduction, restoration and sanitized byte-indexed packaging. No offsite disaster recovery, production retention/SLO, TLS edge or hosted CI claim. |
| FDE/customer adoption | Unproven | The project demonstrates local integration and operational workflows. No outside customer discovery, adoption or production deployment has been measured. |
| Personal code ownership | Unproven by automation | Documentation and tests support a defense. The candidate must still explain the implementation and debug an unfamiliar defect; generated code and a successful demo do not establish that ability automatically. |

## Engineering choices worth defending

- PostgreSQL owns the durable acceptance boundary because a memory-buffer acknowledgement cannot establish committed capture.
- Dispatch intent precedes HTTP inference, and recovery preserves uncertainty because provider execution cannot be deduced from a lost response.
- Database time and fencing address clock skew and stale workers; cancellation is a fence, not a reversal of an external action.
- Original source is distinct from a candidate because edit anchors must remain stable across revisions and recovery.
- Exact source handles simplify model output without relaxing path/hash/excerpt validation.
- Immediate checks make scarce verification useful; repeated model text without new evidence remains an unsuccessful attempt.
- Recorded/live modes have explicit authority because an API outage must not silently substitute successful-looking data.
- Separate local environments and ownership checks make reproduction safe without resetting the existing installation.

## A five-minute defense

Trace one create request from the browser's stable command journal through OIDC authority, PostgreSQL receipt, queue claim, context capture, dispatch intent, captured response, patch validation, checks and public evidence. Show a lost-response retry with the same identity. Explain the unknown-dispatch record. Open the failed fresh comparison and account for extra loop calls/tokens. Finish with the source-context bug and the repair limits that remained after its fix.

For ownership practice, explain why fencing is still required after lease expiry; what happens if artifact fsync succeeds but the database transaction fails; why a hash chain does not make history immutable; how a late UI response is rejected; and why target-regression success cannot override a failing existing test. Then debug an unfamiliar defect without consulting its reference repair.

## Claims that remain outside this release

Production scale, general autonomous repair, loop superiority, model research, signed/immutable provenance, hostile test-forgery resistance, outside-user adoption and the candidate's interview performance. These are evidence boundaries, not reasons to invent more features or rewrite unsuccessful studies.

The [overload workflow map](OVERLOAD_WORKFLOWS_006.md) records admission, saturation, failure and recovery behavior. Pool sizes multiply with process count; no unlimited-scale or global-ingress protection is inferred.
