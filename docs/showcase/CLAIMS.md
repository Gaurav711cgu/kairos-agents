# Claims and résumé wording

## Claim-to-evidence map

| Claim | Evidence and limits |
| --- | --- |
| Full-stack investigation workbench | Next.js/FastAPI, actual PostgreSQL/OIDC browser acceptance; role/tenant boundaries and durable command receipts |
| Tested software release | [428 backend passes, six skips](../../evidence/docs008/checks/backend-summary.json); [complete acceptance](../../evidence/docs008/checks/fullstack-acceptance.json) |
| 24 browser journeys | Eight evidence-viewer, eleven isolated-fault, four real-OIDC, one separately executed real-model journey |
| Browser-submitted AI repair | [Django development receipt](../../evidence/docs008/live-execution/receipt.json): two calls, one candidate, four tests; issue-hinted/exposed scope |
| Measured local capacity | [435,270 HTTP requests](../../evidence/build004/capacity-summary-final.json), approximately 42 minutes; fixture identity/tasks and no inference throughput |
| 275.19 ms acknowledgement p95 | Ten-client 30-minute local soak; successful-response percentile, retained failures and methodology |
| Saved repair reproduction | [110 tests, one skip](../../evidence/build007/repair-reproduction.json), original Django10914 patch and disclosed rebuilt verifier image |

## Three résumé bullets

- Built a Next.js/FastAPI agent-investigation workbench with PostgreSQL durable receipts, OIDC workspace authorization, fenced workers and sandboxed source-patch verification.
- Validated 428 backend tests and 24 browser journeys; measured 435,270 local control-plane requests with zero unexpected errors and 275.19 ms soak acknowledgement p95.
- Demonstrated a browser-submitted Django development repair with two model calls and four passing tests; reproduced a separate saved model patch against 110 tests with one skip.

Retain the local-workload and development-case qualifiers. Explain the separate fresh 0/10 study when discussing repair effectiveness. The architecture and failure receipts provide the stronger engineering argument; no production scale, broad autonomous repair or model research claim is earned by these numbers.
