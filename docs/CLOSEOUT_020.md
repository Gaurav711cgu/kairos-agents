> Update: the separately approved inference-only comparison has now completed. Base and trained adapter each achieved 0/9 verified repairs; three other frozen cases remained unavailable per arm. All nine baseline/reference reproductions passed. See [the complete adapter report](ADAPTER_EVALUATION_020.md). This supersedes statements below that this phase had no uploads or inference; those describe the earlier closeout checkpoint.

# Kairos integration closeout — 20 October 2026

The closeout repairs concrete protocol, evaluation and packaging defects. It does not certify autonomous repair effectiveness, production scale or staff-level operating impact. Historical receipts remain unchanged; this document supersedes unsupported narrative interpretations.

## Verified training

The full100 export SHA-256 is `55bd86a58ac1a15eff2c135a8a9c2beb687b70530e2f47479999e024cc67b71b` (71,957,749 bytes). All 58 manifest members were checked. QLoRA trained 6,291,456 adapter parameters over the frozen `unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit` revision `ecfc63c083900ce4f19daad695e711f38ab98fcf`: 100 public supervision examples and 40 optimizer updates.

These are training examples, not 100 independently reproduced repairs. Admission contains two independent qualification captures, below the earlier 40-capture target. Full100 completion is recorded; its resource-fit flag is false despite measured headroom exceeding 15%, so the flag is not silently relabeled. A separate two-example V5 resource/resume pilot recorded matching adapter, optimizer, scheduler and random-generator state. The distinction is retained.

The ten development generations do not establish an untouched repair comparison. Scored canonical `valid_source_handle` values are false, contradicting the earlier 80% narrative. There are no canonical accepted patch actions in those compared outputs. The p<0.001 claim is unsupported; even eight paired wins without losses would give a two-sided exact sign-test p-value of 0.0078125. No training-effectiveness improvement is claimed.

## Defects corrected

| Defect | Implemented correction | Independent checks |
| --- | --- | --- |
| MCP could wait indefinitely, accept wrong response IDs and omit initialization | Negotiated initialization, absolute I/O deadlines, serialized requests, 4 MiB frames, ID/envelope checks, tool-error handling and owned-child teardown | Nineteen fake-peer transport regressions and actual stdio handshake/call capture |
| Unknown repositories could resolve to unrelated cached/indexed data | Exact repository identity, configured database first, no latest/fuzzy graph fallback | Full CodeSage backend suite: 127 passed |
| Historical 15/15 retrieval result used caller labels during selection | Public legacy execution disabled; new issue-only ranking interface; annotations used only after selection | Annotation-independence, actual rank, deterministic ties and equal joint-token-budget tests |
| Current indexes were installed packages, unbound to case revisions | Diagnostic marks them benchmark-ineligible; benchmark recall/MRR remain unavailable | Provenance regression and immutable diagnostic receipt |
| Handwritten patch plus parsing an unrelated function was called a repair | Context demonstration explicitly reports handwritten origin, zero model/check runs and no verified repair | Three isolated truthfulness/immutability tests |
| Packaging could imply unsupported scores or publish partial/missing files | Frozen archive and member verification, minimal allowlist, derived-file manifest, factual model card, explicit upload flag | Eight packaging regressions; no network upload performed |
| Hosting flags silently selected recorded data | Live is the default everywhere; recorded mode must be explicitly configured | Node 24 environment-mode regression |
| Browser tests used JSON imports incompatible with the required Node version | Explicit JSON import attributes | Recorded browser suite on Node 24 |

## Evidence and local acceptance

Acceptance receipts are under `../evidence/closeout020/`. Separate invocations are not added into a larger test total.

- Kairos backend without PostgreSQL/optional services: **1,103 passed, 146 skipped, 16 subtests passed**. The first restricted run's loopback permission failures remain preserved; rerunning with loopback access passed.
- CodeSage backend: **127 passed**, with two pre-existing deprecation warnings.
- Recorded browser acceptance: **20 passed**. Includes genuine downloads, historical failures, context inspection, diagnostic provenance, keyboard focus and 390px layouts.
- Frontend boundary/client/recorded unit checks, lint, TypeScript and production build passed. The final explicit-mode unit regression also passed. Earlier lint failures are retained with their focused fixes.
- Fresh isolated PostgreSQL/Keycloak acceptance: **1,212 passed, 23 skipped, 16 subtests**, followed by **four real OIDC browser journeys**. Login/logout, generated credentials, runtime/migration roles, tenant boundaries, retries, pagination, queue/cancel/fork/replay/publication and downloads passed.
- Isolated interaction-fault journeys: **11 passed**, including stale responses, uncertain submissions, poll backoff and cancellation.
- The existing Python environment matched all **34 API/reviewer package pins**. It was reused to avoid a duplicate installation; this is not a fresh dependency installation claim.

## What a person does and receives

1. Open the recorded website and select an investigation. The DOM shows the issue, pinned source, captured model actions and an observed outcome.
2. Inspect the diff and independent check output. Download the original patch/evidence. Downloads are validated bytes, not newly generated successes.
3. Open the strategy comparison. See each attempted outcome, actual calls and captured timing. Historical 0/10 and 0/36 remain separate from later curated study results.
4. Open CodeSage inspection. See an explicitly annotated, handwritten context demonstration; the retrieval page explains why its current indexes are ineligible for a benchmark. No repair is invented.
5. In isolated live mode, sign in through Keycloak. Authorized roles can queue, cancel, fork, replay and publish; another tenant cannot access private work. Without an explicitly prepared worker, a queued investigation remains queued. No model is started by control-plane acceptance.

## Existing repair effectiveness, separated from training

The earlier measurement014 system already achieved **7/12 loop repairs**, versus **1/12 single-call** and **1/12 independent drafts**, on its small curated held-out Django/pytest sample. A new audit verified **all 57 record hashes, 1,290 captured request/result body hashes**, raw output byte counts/hashes, complete verifier results and patch-to-check digest bindings. This is a new integrity audit of existing execution, not new inference or a new repair score. The experiment used the captured Codex CLI transport; these results are not attributed to the trained 14B adapter.

The original 0/10 and 0/36 studies remain historical, independently attributed failures. They are not the latest system result. Earlier statements that repair effectiveness was entirely unestablished were too broad; the missing result specifically concerns the trained adapter.

A separate preparation command, `python3 -m scripts.coding_eval020 prepare --help`, now freezes public prompts and private source bindings without model execution. It preserves all 12 already qualified cases and all four pre-model qualification exclusions. Three qualified cases had no initial AST context in their historical baseline capture; they remain explicitly unavailable rather than being removed. These are already exposed research cases, not a new holdout. No notebook, data or weights were uploaded.

## Remaining trained-adapter effectiveness gate

A useful next model claim requires a frozen base-versus-adapter repair comparison on independently qualified cases excluded from training/development, with independently executed baseline failures, patch checks and relevant existing tests. The old annotated retrieval cohort cannot be renamed a fresh holdout. Indexes must bind exact source revisions before benchmark scoring. More training is not a substitute for this evaluation.

No public hosting, model upload, email or internship submission was performed. No new inference or training dispatch ran during this closeout. Docker is used only for isolated service checks and then stopped. Model weights and historical data remain preserved. Dormant qualification sources have verified lossless cold archives with restoration tooling; only an archived duplicate and rebuildable installer cache were reclaimed.
