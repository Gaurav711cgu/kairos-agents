# Bounded repair loop012

Date: 15 October 2026. Parent: retrieval011 commit `78586f0`. This phase connects prepared source retrieval to a versioned repair loop. Historical model outcomes and sealed releases remain unchanged.

## Scope and behavior

The existing website, authenticated API and local-model worker remain usable. The API accepts two new explicit configurations; its historical default remains `loop-v3`. Semantic retrieval is selected through the optional `scripts.study012` command, not silently enabled in every API worker or historical investigation. Website presentation of new retrieval comparisons belongs to the next product phase.

| Configuration | Model calls | Applied candidates | Independent checks | Deadline | Claim |
| --- | ---: | ---: | ---: | ---: | --- |
| `baseline-v8` | 1 | 1 | 1 | 600 seconds | One proposal under the new source-handle protocol |
| `loop-v8` | 10 | 4 | 4 | 900 seconds | Bounded source inspection and immediate check feedback |
| Historical `loop-v1` through `loop-v7` | 6 | 2 | 2 | 600 seconds | Preserved historical behavior |

Ten model calls do not mean ten applied repair attempts. Search, read, rejected actions and a final result consume calls. Duplicate checked candidate digests reuse their captured check results. Two identical invalid proposals still stop the loop. Patches retain existing source/path/digest/range/syntax restrictions and independent registered verification.

## Operator workflow

Use a reviewed unresolved-task manifest with pinned original source and independent baseline receipts. The command does not turn arbitrary URLs into trusted cases. Review registration and prepare the source-only index separately before dispatch.

```bash
python3 -m scripts.study012 doctor

python3 -m scripts.study012 validate-task \
  --manifest "$KAIROS_TASK_MANIFEST" --case-root "$KAIROS_CASE_ROOT" \
  --task-id "$KAIROS_TASK_ID" --configuration loop-v8 \
  --retrieval-mode hybrid --index-root "$KAIROS_INDEX_ROOT" \
  --index-id "$KAIROS_INDEX_ID" --encoder-dir "$KAIROS_ENCODER_DIR" \
  --budget-root "$KAIROS_CASE_ROOT" --budget-root "$KAIROS_OLD_EXPERIMENT_ROOT" \
  --budget-root "$KAIROS_NEW_EXPERIMENT_ROOT"
```

These variables identify existing operator-reviewed local assets. Supply every owned experiment root; dependencies, weights, indexes and receipts count toward 6 GiB, with at least 4 GiB free disk retained. Prepared retrieval uses the separately pinned optional dependencies in `requirements-retrieval011.lock`; the default app environment does not install a second model stack. `doctor` starts no service or inference. `validate-task` checks identities and policy without embedding a query or invoking the repair provider.

After validation, use `run` with the same arguments and an explicit new `--runtime`. `report --runtime PATH` validates saved result hashes without starting services. An existing runtime is inspected, never automatically redispatched. Failed, incomplete and unknown execution statuses return a nonzero shell exit status while preserving their JSON report. Failed independent checks are a completed investigation outcome, not a command transport failure.

Use `--retrieval-mode ast` for the existing function/callee method without registered entry hints. Other modes are `lexical`, `dense` and `hybrid`. All arms keep registered case metadata intact for source validation and verifier completion checks. Localization policy controls whether entry hints participate; it does not rewrite the trusted registry. An empty selection is captured and ends as `no_patch`, rather than quietly adding a reference-seeded source region.

## Source, context and recovery

An index binds the exact original revision, source inventory, approved prefix, chunk bytes, vector hashes and encoder identity. Retrieval returns original-source handles before edits. Captured selection includes exact returned observations, ranking policy, omissions and truncation metadata. The ordered selection is durable before model dispatch.

Recovery restores captured selection and pending original-source captures. It does not re-encode a completed selection or silently choose a new index. Captured model responses continue through checks; pending uncertain dispatches remain unknown. Replay reads stored artifacts and performs zero model, encoder or tool execution. Original source checkouts remain unchanged.

Prepared query embeddings run in a short-lived CPU child with a minimal environment and no API credentials. The child exits before repair generation or Docker checks. This avoids keeping PyTorch weights resident alongside verification on the 8 GiB Mac. A real 768-dimensional query probe completed in 8.121 seconds; it is one measurement, not an inference-service latency distribution.

## Provider and token accounting

New optional CLI runs explicitly request `gpt-6.1-sol` through the existing ChatGPT login. They do not enable API billing, buy credits or select another provider after an uncertain call. The CLI transport separately limits dispatches to one for the baseline and ten for the loop; its historical default remains six.

The new wrapper stops subsequent calls after 64,000 captured prompt tokens or 8,192 captured completion tokens. Missing or invalid usage also stops further dispatch. This is post-response admission control: a final call may overshoot, and opaque internal CLI retries are not counted as separate Kairos calls. It must not be described as a hard provider billing/token cap. Prompt metadata records remaining reported allowance and this limitation.

The account's previous usage-limit uncertainty remains preserved. This software phase produces no new repair-quality score. The next model result requires a fresh reviewed task and ordinary provider availability; unknown earlier work is never resent. Later comparison freezes provider, retrieval, source and budgets before held-out execution.

## Database and process decisions

Migrations `0005` and `0006` expand then validate the configuration and all three physical counter constraints. Adding names alone is insufficient: the initial acceptance exposed the old six-call physical limit. The corrected transactional migration adds replacement `NOT VALID` constraints before dropping and renaming old constraints. It preserves historical rows and validates in a separate revision. Existing migration receipts and checksums are untouched.

The database clock sets a 900-second investigation deadline and 960-second lease for `loop-v8`; historical profiles retain 600/660 seconds. Recovery preserves the original deadline. Counter increments, fencing, durable receipts, cancellation and tenant restrictions remain enforced by the repository.

A fresh trusted output supervisor applies the existing file-size limit before executing Docker. The threaded parent no longer uses `preexec_fn`. Registered commands, non-root execution, no network, read-only root, two CPUs, 1 GiB memory and bounded output/time remain in force. This POSIX launcher does not establish Windows runtime support or adversarial test-forgery resistance.

## Acceptance and owned fixes

The full backend run passed **868 tests**, with **six explicit opt-in skips**, in 76.27 seconds. A separate actual Docker isolation/output-bound check passed in 2.25 seconds. Nine real database/container journeys cover the old and new runners; provider/encoder actions in those journeys are fixtures. Four OIDC-provider cases and one actual local-model schema probe remain outside this local invocation. Final hashes and scopes are in `evidence/loop012/acceptance.json`. Mechanical provider/encoder fixtures establish software contracts, not AI repair competence. Actual embedding, database, container, frontend and hosted checks have distinct scopes.

| Observed defect | Fix | Closure check |
| --- | --- | --- |
| V8 name expansion left the physical model-call limit at six | Expand and validate all counter constraints transactionally | Real PostgreSQL permits ten calls/four candidates/four checks and rejects excess |
| New CLI returned shell success for incomplete or unknown reports | Return failure status while retaining the report | Real subprocess exits one for an incomplete runtime |
| Baseline transport advertised six allowed calls | Freeze a one-dispatch profile | A second fresh intent is refused before provider execution |
| Hint removal mutated the registered case and affected verification | Separate localization policy from immutable case metadata | Reviewed-task AST journey passes with completion metadata intact |
| Empty lexical retrieval could fall back to registered entry hints | Persist zero-hit selection and stop without a patch | Zero-hit/recovery regression makes no provider call and captures no hinted region |
| Oversized issue text passed validation but could not be queried | Refuse incompatible query before runtime/service creation | UTF-8 byte, null and empty-token preflight checks |

Historical 0/36 and 0/10 studies remain visible. No broader repair claim, training result or retrieval superiority is earned by passing these software checks. Free Kaggle/Colab training preparation is a later phase; data deduplication, split integrity, measured GPU fit, resumable checkpoints and held-out evaluation remain its gates. See `AI_ADVANCEMENT_PLAN_011.md`.

## Reproduction and preservation

Run `python3 -m scripts.acceptance007 backend` for the authoritative test inventory. Environment-dependent integrations are explicit skips unless the caller supplies their isolated services. Routine CI uses fixture actions and never spends model quota. Run `python3 -m scripts.verify_loop012` to verify current source and inherited evidence bindings.

CI retains original repair010 and retrieval011 verifiers against their exact Git snapshots, then checks the new overlay independently. No historical manifest is rewritten. Hashes prove consistency relative to these stored references, not signed immutable history.
