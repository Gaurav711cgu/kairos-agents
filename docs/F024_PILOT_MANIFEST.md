# F024 pilot execution manifest (awaiting approval; nothing executed)

Prepared 22 October 2026. Every step below has run offline with mocked model outputs
(`evidence/localization024/f024-pilot/mock-dryrun-v2`). No model call, Colab session or Docker
scoring has happened.

## 1. Cases and conditions

Exact identifiers are in `evidence/localization024/f024-pilot/mock-dryrun-v2/pilot-package.json`; they are kept out of scanned docs. The staged pilot files under `~/Desktop/resume` do name them, so the local exposure scan now counts 398 identifiers (`c1bc599d…`, up from 396). That is accurate: these 2 cases will be model-exposed. Future development-localization reruns will fail the `356fbe62` exposure guard by design. Comparing them with earlier receipts needs a frozen exposure list or must accept a 2-case pool change.

| Case | Repository | Pinned revision | Split bucket | Exposed | In unseen023 |
|---|---|---|---|---|---|
| pilot-django (ID in package) | django/django | 6c9778a58e4f | development | no | no |
| pilot-pytest (ID in package) | pytest-dev/pytest | 902739cfc3bb | development | no | no |

Selection rule (fixed before outcomes were seen): the first case per repository, in salted
split order, that is inside the 2-file/40-line edit scope and whose two contexts both fit the
memory envelope. This is a pipeline check, not a representative sample. No validation or
holdout case is used; holdout sources have never been fetched. Exposure set: 396 identifiers,
SHA-256 `356fbe62…`.

| Condition | Context source | Prompt tokens (django / pytest) |
|---|---|---|
| issue / base | frozen023 issue-only selector (`coding_context_v3_014`) + frozen 021 pack | 1359 / 965 |
| issue / adapter | identical prompt | 1359 / 965 |
| oracle / base | gold-hunk windows (`oracle_context024`), **diagnostic upper bound only** | 693 / 772 |
| oracle / adapter | identical prompt | 693 / 772 |

Models: pinned base `unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit@ecfc63c083900ce4f19daad695e711f38ab98fcf`.
Adapter: training5 round 1, checkpoint 80 (trained on 2 known training cases), attached with
PEFT. The base arm runs with the adapter disabled in the same process.

## 2. Generation ledger (hard cap 16)

| Session | Jobs | Rule |
|---|---|---|
| Turn one | exactly 8 | 2 cases x 2 contexts x 2 arms; notebook asserts at most 8 |
| Turn two | 0 to 8 | only for a parser or validator rejection that fits the envelope; one turn, never a third; notebook asserts at most 8 |
| **Total** | **at most 16** | no retry after a generation error, out-of-memory or uncertain dispatch |

## 3. Memory, runtime and stop conditions

- Envelope: prompt + max_new_tokens at most 3539 (largest input+output observed on the T4, peak
  14.42 of 14.6 GiB). Pilot maximum is 1359 + 512 = 1871. Enforced in the package, then again
  after re-rendering with the real tokenizer before the model loads.
- Output cap 512 tokens per turn; greedy decoding; seed 42; fp16 compute profile copied from the
  frozen runner.
- Hard deadline of 180 s per generation: the process writes `hard-timeout.json` and exits 124.
- Refuse before the model loads if any of these differ: package, runner, adapter binding or
  model manifest hashes; the downloaded model file set versus the manifest; adapter bytes;
  dependency profile; GPU memory below 14 GiB; any prompt re-render digest.
- Halt on any generation error, including CUDA out of memory: the error is captured and never
  retried. An intent without a capture is an uncertain dispatch: stop and never redispatch.
- Expected time per session: 8 x about 34 s plus model download and load; at most 8 x 180 s plus
  load.

## 4. Receipts, scoring and failure classes

- Colab journal: `intents/` and `captures/` per job, each bound to the package hash and the job
  hash, plus `capture_sha256`, `runtime.json` and, if triggered, `hard-timeout.json`. Written
  atomically.
- Local validation and turn-two planning: `python -m scripts.f024` writes `turn1-ledger.json`
  and an immutable `turn2-package.json`. Each turn-two job names its parent job and capture hash.
- Qualification (needed before scoring): `scripts/f024_qualify.py` runs the reviewed qualify014
  checks in the pinned local images (pull never, network none). The baseline must fail and the
  reference must pass. Receipts go to `kairos-closeout020/f024-pilot/qualification`.
- Scoring: `scripts/f024_score.py` scores only the last turn per (case, context, arm). It re-admits
  the qualification receipt (every artifact hash rechecked), uses one pinned source per case,
  re-derives the verifier, applies the edit through `validate021`, runs the checks and judges
  against the qualified baseline. Original source is verified unchanged afterwards.
- Outcome classes: `accepted`, `parse`, `syntax_indentation`, `syntax_other`, `range`,
  `no_change`, `validator_other`, `not_captured`, `generation_error`, `case_not_qualified`,
  `verified_repair`, and qualifier statuses for failed behaviour.

## 5. Staged artifacts (local only; upload requires approval)

`~/Desktop/resume/kairos-closeout020/f024-pilot/upload-v2/` (supersedes the stale `upload/`, whose runner hash
changed): 7 files. Hashes are listed in `../upload-v2-manifest.json`.

| File | SHA-256 (prefix) |
|---|---|
| f024-package.json | 71b184b4a191edc3 |
| f024_colab.py | 9b244ef5d28916b2 |
| adapter-binding.json | 945e6b22b9066905 |
| model-manifest.json | 62ea7dacec966b6f |
| adapter/adapter_config.json | d6520a57e7f96f8c |
| adapter/adapter_model.safetensors | dba92adad5156224 |
| f024-pilot-turn1.ipynb | 57a279ac3c2cdc27 |

Qualification binding (plan mode, immutable): `4f719da2…`; wrapper `46eeff80…`; package `71b184b4…`.

## 6. Execution commands (in order; each needs approval)

```bash
# Step 0: local qualification. Docker running and healthy for a sustained period first;
# downloads 2 pinned archives (8,983,674 + 1,101,516 bytes); 0 model calls.
.venv/bin/python scripts/f024_qualify.py \
  --package evidence/localization024/f024-pilot/mock-dryrun-v2/pilot-package.json \
  --parquet ~/Desktop/resume/kairos-closeout020/unseen023-full/test.parquet \
  --output ~/Desktop/resume/kairos-closeout020/f024-pilot/qualification \
  --storage-roots ~/Desktop/resume/kairos-closeout020/scored-correction022-v1/storage-check022.json \
  --execute --allow-source-download

# Step 1 (only if both cases qualify): upload the staged upload-v2 folder to a free Colab T4 runtime and run
# f024-pilot-turn1.ipynb. Its final cell runs:
python f024_colab.py --package f024-package.json \
  --package-sha256 71b184b4a191edc3a7def2738ccf3ee2278d24543c7bc8d432b192d0956b2ad3 \
  --adapter adapter --adapter-binding adapter-binding.json --model-manifest model-manifest.json \
  --scratch /content/scratch --output /content/f024-results
# Download /content/f024-results unchanged.

# Step 2: local turn-two package (no model).
.venv/bin/python -m scripts.f024 --package <upload>/f024-package.json --results <downloaded>/f024-results \
  --cache <scratch>/src024 --tokenizer ~/Desktop/resume/kairos-closeout020/unseen023-full/tokenizer-assets \
  --output ~/Desktop/resume/kairos-closeout020/f024-pilot/turn2

# Step 3 (only if turn-two jobs exist): upload turn2-package.json with a new notebook bound to its
# hash (generated locally by scripts.f024_colab.notebook, cap 8) and run it in a new Colab session.

# Step 4: local Docker scoring.
.venv/bin/python scripts/f024_score.py --package <upload>/f024-package.json --package <turn2>/turn2-package.json \
  --results <turn1-results> --results <turn2-results> \
  --qualification ~/Desktop/resume/kairos-closeout020/f024-pilot/qualification-v4 \
  --parquet ~/Desktop/resume/kairos-closeout020/unseen023-full/test.parquet \
  --storage-roots ~/Desktop/resume/kairos-closeout020/scored-correction022-v1/storage-check022.json \
  --admission-module ~/Desktop/resume/kairos-closeout020/unseen023-full/comparison.py \
  --output ~/Desktop/resume/kairos-closeout020/f024-pilot/scoring --execute
```

## 7. GO/NO-GO checklist

| # | Gate | Status |
|---|---|---|
| 1 | Cases are development bucket, unexposed, not unseen023, no holdout | PASS (verified) |
| 2 | Runner, package, bindings, adapter hashes staged and consistent | PASS (verified) |
| 3 | Journal, turn two, scoring selection mock-tested | PASS (tests; two-turn mock dry run) |
| 4 | Memory envelope: every job at most 1871 of 3539 tokens | PASS |
| 5 | Both pilot cases qualify in the pinned images | PASS (qualification-v4: baseline fails, reference passes; 412 and 85 tests; receipts admitted by frozen `admit_receipt`) |
| 6 | Pinned pytest image `kairos-investigation-pytest:build006` present locally | PASS (ID `3407ec26…` matches) |
| 7 | GPU path executed at least once | **NO** (transformers 4.57.6 not installed locally; fails closed before model load) |
| 8 | Scoring execute path exercised | **NO** (Docker; runs after step 0 and Colab) |

**Decision: GO for step 1 (Colab turn one, 8 generations) on approval of the upload and session.**
Step 0 is complete (`evidence/localization024/f024-pilot/qualification-v4.json`). Control Docker
with `docker desktop start` and `docker desktop stop`, and gate on pinned-image inspection before
scoring; `osascript quit` left the backend half-running earlier.
