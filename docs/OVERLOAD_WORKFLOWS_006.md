# Kairos overload and failure workflows

Dedicated workflows protect a system only when resource limits, admission decisions and recovery semantics are enforced. Kairos's active investigation path uses the following controls. These are local boundaries, not proof that every deployment scale is safe.

| Situation | Current workflow | Evidence / limit |
| --- | --- | --- |
| Normal submission | Authenticate, validate a registered command, commit its stable identity, acknowledge, then execute outside the request transaction. | Durable retries and real OIDC journeys. Slow inference does not hold the acceptance transaction. |
| Queue saturation | Serialize admission; allow at most 24 queued/running globally and six per tenant. Reject excess work with HTTP 429. | Backend quota/concurrency tests. Rejection is intentional backpressure, not a successful accepted job. |
| Database connection saturation | Active investigation repository pool: maximum eight connections, 32 waiting borrowers and five-second acquisition timeout. Database/pool unavailability becomes HTTP 503. | `investigations/repository.py`, `app.py`, measured build004 load. Pool limits are per process; multiplying API processes also multiplies possible connections. |
| Slow inference or checks | Run in the worker with six-call/two-candidate/two-check/600-second budget. Registered verification has bounded time, output, CPUs and memory. | Protocol, budget and real Docker checks. Accepted queue waiting is separate from execution deadline. |
| Lost command acknowledgement | Browser retains a workspace-scoped command identity and retries with that identity. Conflicting payloads return HTTP 409. | Client and live durable-retry tests. This does not repeat inference. |
| Uncertain provider dispatch | Keep the durable intent and mark the outcome unknown. Do not retry elsewhere or silently redispatch. | Recovery tests, actual process-death drills and preserved real-model history. Unknown provider consumption remains unavailable. |
| Worker crash / stale worker | Database-clock lease and fencing reject stale writes. Resume a captured result; preserve an unknown dispatch. | Actual PostgreSQL tests and SIGKILL drills. Cancellation cannot reverse an already-started provider call. |
| Cancellation | Fence subsequent writes and mark the record cancelled. Queued work no longer occupies an active slot. | Tenant-scoped API/browser checks. In-flight external work may still complete without authorizing a stale commit. |
| Frontend navigation / polling failure | Abort obsolete reads, reject late generations, poll every two seconds while visible, back off to 30 seconds after errors and stop on terminal state/navigation. | Client/state tests and browser journeys. Browser backoff is not a global traffic limiter. |
| Invalid or oversized candidate | Reject protected paths, escaping symlinks, stale excerpt identities, overlaps, syntax errors and file/line limits before checking. Bound model/check output. | Source/edit regressions and real isolation probe. Rejected edits remain inspectable. |
| Corrupt or unavailable evidence | Fail explicitly on hash/schema/reference/order mismatch or missing records. Live outages never substitute recorded results. | Integrity negative tests, image outage smoke and recorded browser errors. |
| Local heat / resource contention | Keep inference off during release checks, serialize heavy work, stop owned services and Docker after container-dependent phases. Recorded review runs without Docker. | Shutdown receipt and clean recorded-only acceptance. Shared-host capacity is finite. |

## Scaling decisions

The completed local capacity protocol measured 435,270 control-plane requests over 42 minutes with zero unexpected errors. It includes neither inference nor OIDC throughput. The original failed soak stays visible. Successful latency alone would hide error rates; inspect both raw failures and p95.

Before adding API replicas or increasing worker concurrency, set an explicit PostgreSQL connection budget across every process and repository, choose admission limits for the new host, and repeat the relevant load/soak protocol with raw status/error/latency measurements. Increasing every pool and queue together can move overload into PostgreSQL rather than remove it.

Global ingress rate limiting, distributed coordination across separate installations, production database query/lock timeout policy, adversarial traffic, offsite recovery and autoscaling are outside the tested local release. The current one-investigation execution slot is intentional. Additional infrastructure should follow a measured bottleneck and a defined workload, rather than a claim that a separate service prevents overload automatically.
