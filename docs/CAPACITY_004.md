# Build 004 local capacity evidence

The completed project-quiescent repeat met all five declared targets. It processed 435,270 requests with zero unexpected errors and zero unplanned quota rejections. The original mixed-workload soak failed and remains preserved. These are local control-plane observations, not production-scale or inference-capacity claims.

The harness used actual HTTP and PostgreSQL with isolated fixture identity and tasks. It measured durable command acknowledgements, retry receipts, progress/list reads and cancellation. It did not measure inference or identity-provider throughput. Clients pause 50 ms between command cycles; these are closed-loop observations, not an open-loop saturation limit.

| Clients | Seconds | Requests | Ack p95, ms | Read p95, ms | Unexpected errors | Unplanned 429s |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 180.01 | 8840 | 24.5 | 7.5 | 0 | 0 |
| 5 | 180.03 | 42275 | 33.0 | 8.5 | 0 | 0 |
| 10 | 180.11 | 67380 | 56.1 | 11.6 | 0 | 0 |
| 20 | 180.15 | 39770 | 281.6 | 68.2 | 0 | 0 |
| 10 | 1800.23 | 212803 | 275.5 | 37.8 | 31858 | 11518 |

Latency percentiles include successful requests only. The soak's failure rate must be read alongside them. The original summary called all 429s expected; this workload did not plan quota pressure. Stranded commands after failures can consume quota. Corrected inclusive non-success rate is recorded in `capacity-analysis.json`.

## Bounded optimization and outage

The first run opened a PostgreSQL connection per request and encountered connection failures. Its receipts remain under `evidence/build004/capacity`. One bounded pass added a maximum-eight-connection pool with health checks and rollback handling. The complete repeat is under `capacity-pooled`.

Other builds, browser checks and local inference overlapped this mixed-workload run on the 8 GB Mac. PostgreSQL logs show orderly shutdown at 18:57:15 UTC and restart at 18:58:52 UTC on October 11. Keycloak also restarted. These logs do not establish the cause. Do not call it proven OOM or attribute it solely to connection churn.

A model dispatch interrupted by the outage was fenced and recorded unknown without redispatch. The worker now backs off after connection failures; it does not retry a model call on that basis. Focused tests cover this behavior, but they do not retroactively make the soak pass.

## Complete repeat and interrupted attempt

The first quieter repeat stopped after two completed stages and part of the ten-client stage. When the chat resumed, its process and Docker daemon were absent and no completion receipt existed. Its cause is unproven. Partial raw rows and `capacity-quiet-interruption.json` remain preserved.

A new full protocol ran from16:43:35 to 17:25:36 UTC on October 12 under `capacity-quiet-2`. Kairos inference, website, browser checks and builds stayed stopped. `caffeinate -i` inhibited idle sleep only while its benchmark process existed. This does not establish the earlier interruption's cause.

The shared host was not dedicated. Docker build history records a separate project's 6.5-second build ending about 59 seconds before benchmark startup. The initial interpretation that it overlapped stage one was wrong; `capacity-quiet-2-host-context.json` corrects it while preserving the earlier receipt. Other shared-host activity was not exhaustively measured.

| Clients | Seconds | Requests | Ack p95, ms | Read p95, ms | Unexpected errors | Unplanned429s |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 180.01 | 9140 | 25.9 | 8.5 | 0 | 0 |
| 5 | 180.04 | 42200 | 33.0 | 8.6 | 0 | 0 |
| 10 | 180.08 | 64825 | 61.9 | 11.8 | 0 | 0 |
| 20 | 180.22 | 46250 | 250.6 | 47.0 | 0 | 0 |
| 10 | 1800.13 | 272855 | 275.2 | 16.8 | 0 | 0 |

All stages met p95<750ms and non-success<1%. The30-minute soak completed272,855 requests, acknowledgement p95 275.19ms and read p95 16.79ms. The corrected runner streams raw rows, retains uncertain create identities and waits for confirmed cancellation before issuing a new command. Its raw 435,270 rows match aggregate request counts and have a recorded SHA-256 hash. The isolated temporary schema was removed on normal completion.

Successful percentiles still exclude non-success responses; error denominators include every request. Here there were zero non-success responses. One finite local repeat does not demonstrate fault tolerance against arbitrary daemon shutdown, saturation throughput or a production availability guarantee. No inference or OIDC throughput was measured.

## Reproduce and inspect

Run `PYTHONPATH=. .venv/bin/python -m scripts.benchmark_control_plane --help` for the isolated runner. Each execution requires a new output directory and runs the full1/5/10/20-client loads plus30-minute ten-client soak by default. Pause other local workloads and measure their absence rather than assuming it. The complete repeat used the maximum-eight-connection pool already introduced in the bounded optimization.

Raw JSONL, original summaries, both interrupted runs, service logs and corrected aggregates remain in the release directory. `capacity-summary-final.json` combines original and complete repeat evidence without rewriting `capacity-analysis.json`. No failed run was deleted.
