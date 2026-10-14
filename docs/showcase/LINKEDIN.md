# Sharing Kairos

Use this draft after the reviewed release is available in the linked repository. The local website at 127.0.0.1 is not a public URL. A reviewer can run the evidence viewer from a clean checkout with the documented demo command; live inference uses the separately prepared local environment.

## Draft post

I built Kairos, a full-stack workbench for investigating repository defects with AI and inspecting the evidence behind a proposed repair.

The interesting work was making the system dependable around an uncertain model: durable PostgreSQL request receipts, OIDC workspace roles, fenced workers, captured context, bounded execution and disposable patch verification.

A real browser-submitted Django development investigation completed with two model calls and four passing registered tests. The website exposes source, patch, checks and downloadable evidence. A separate local control-plane test measured 435,270 requests over approximately 42 minutes, with zero unexpected errors and a ten-client soak acknowledgement p95 of 275.19 ms. That workload excludes model inference and OIDC throughput.

The repair study is visible too: fresh validation was 0/10. It showed tool-format and behavioral errors that a convincing demo alone would miss. The successful development case stays separate from those results.

You can review the architecture, run the saved-evidence website without Docker or a model, and inspect the receipts behind each claim.

Repository: https://github.com/Gaurav711cgu/kairos-agents

## Before sharing

Verify that the repository actually contains this release’s README and reviewer command. Link the repository and its quick start, not localhost. Keep the declared local workload and development-case scope. Ask readers to try the inspection workflow or inspect a specific architectural decision; do not promise an arbitrary repository repair service.
