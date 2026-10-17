# Optional fresh comparison014

These two additive modules reuse the existing v8 action protocol, PostgreSQL
repository, CLI transport and one-task runner. They do not replace a worker,
database, transport or historical configuration.

Install `comparison014.py` as `scripts/comparison014.py` and
`independent_drafts014.py` as
`scripts/repair014/independent_drafts014.py` in a reviewed execution checkout.
Create an empty `scripts/repair014/__init__.py`. Staged imports support fixture
tests, but real execution refuses source located outside its explicit checkout.
Freeze the installed source bytes before running any comparison arm.

## Frozen arm policy

| Arm | Physical configuration | Model calls | Applied patches | Checks | Deadline |
| --- | --- | --- | --- | --- | --- |
| baseline | `baseline-v8` | 1 | 1 | 1 | 600 seconds |
| loop | `loop-v8` | 10 | 4 | 4 | 900 seconds |
| drafts | `loop-v8` | 10 | 4 | 4 | 900 seconds |

All arms start with the same original-source AST localization policy and no
maintainer entry-file hints. The loop retains existing bounded original
search/read and rejection/check feedback. The baseline uses one original-only
context. Each independent draft gets a fresh `baseline-v8` public context with
only the captured original `initial_source` observations. Earlier candidates,
rejections, search results and check outcomes never enter a later draft.

The draft arm captures up to ten model responses before checking any candidate.
It validates each response against its own captured ActionV7 source handles and
restores original source authority during recovery. These structural draft
events do not consume the repository's applied-patch counter. After generation,
one immutable selection event freezes the first four structurally valid
candidates. Only those selected proposals consume the existing patch counter.
Already captured checks for duplicate patches are reused. Checks stop after a
selected pass or an environment failure; the final active proposal therefore
matches the reported final verdict. The entire selected candidate list remains
visible even when later slots were not checked.

`TokenBoundCLI012` still controls new dispatch admission from captured usage:
64,000 reported input tokens and 8,192 reported completion tokens. A final call
may overshoot these post-response admission ceilings. Internal CLI retries and
resolved remote model identity remain unavailable. A token admission stop is
captured and can leave fewer than ten drafts; it is not silently filled with
another case or provider. A pending model dispatch, or a transport exception
after its durable intent, remains `unknown_dispatch` and is never resent.

## Study JSON

The runner requires an externally frozen JSON file and the exact file SHA-256
through `--study-sha256`. It never tunes or rewrites that study. Required shape:

```json
{
  "version": "comparison014-study-v1",
  "cohort_sha256": "97f681a503ca3e1f63314c5c22c82e6e12be0f7891b2a80b6c16e74042f4fd1f",
  "arms": ["baseline", "loop", "drafts"],
  "cases": [
    {
      "instance_id": "one original frozen candidate ID",
      "split": "development or holdout, unchanged",
      "qualification_receipt_sha256": "exact terminal receipt SHA-256"
    }
  ],
  "strategy_profiles_sha256": "digest(strategy_profiles014())",
  "source_sha256": {"every selected source path": "exact SHA-256"},
  "provider": {"exact cli_identity010() identity": "unchanged"}
}
```

The example case is schematic: the real `cases` array must contain all 24 original
IDs in exact frozen order, with their original development/holdout assignments.
Excluded, unavailable and failed qualification candidates remain in that ledger;
the runner refuses to dispatch them. It accepts only a case whose terminal
qualification receipt independently proves a complete behavioral baseline
failure and a complete reference pass. It rechecks artifact hashes and complete
raw output bytes before any provider preflight.

`strategy_profiles014()` returns the reviewed arm profiles. `digest()` uses the
module's compact sorted UTF-8 JSON representation plus a final newline. The
`source_sha256` mapping must equal the merged existing `_source_identity(checkout)`
and every `policy012(...).source_files` entry plus these two installed new
modules. The provider object must equal the identity returned by existing
`cli_identity010()`. Model selection remains explicitly requested
`gpt-6.1-sol`, with no API-key fallback or claim of attested remote weights.

The parent workflow rehydrates each qualified case into a new owned source
registry using its pinned archive/tree hashes. A registered case must match the
qualification `case-definition.json` exactly, with only `qualified` changed to
`true`. Historical registered cases and sources are not overwritten. Source and
reference/test digests are checked through the original `CaseRegistry.verify()`.

## Execution

```bash
PYTHONDONTWRITEBYTECODE=1 /path/to/execution-checkout/.venv/bin/python \
  -m scripts.comparison014 \
  --checkout /path/to/execution-checkout \
  --manifest /counted/new-case-registry.json \
  --case-root /counted/new-case-runtime \
  --task-id original-frozen-id \
  --runtime /counted/fresh-arm-runtime \
  --study /counted/study.json \
  --study-sha256 EXACT_STUDY_SHA256 \
  --qualification-receipt /counted/qualification/cases/original-frozen-id/receipt.json \
  --arm baseline \
  --budget-root /counted/all-owned-root-one \
  --budget-root /counted/all-owned-root-two
```

Each arm needs a fresh runtime. An occupied runtime is refused; inspect captured
results separately instead of triggering redispatch. The existing nonblocking
runner lock prevents overlapping optional investigations in one checkout. The
outer gate counts all declared experiment roots under the existing 6 GiB storage
and 4 GiB free-space reserve. Supply every owned root, including qualification,
new source, study and arm runtimes.

The runner delegates actual execution and cleanup to `_run_new010`. Its policy
metadata binds the study SHA, arm, reviewed strategy profile SHA and selected
source identity. It makes no public export, training claim or official benchmark
score. It produces one captured arm result with the existing durable evidence.

## Fixture verification

```bash
cd /path/to/kairos-ai014/comparison
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/path/to/new-karos \
  /path/to/new-karos/.venv/bin/python -m unittest -v \
  test_independent_drafts014.py test_comparison014.py
```

The 13 tests cover fresh context isolation, pre-check selection, physical
counters, duplicate check reuse, consistent passing-candidate reporting,
uncertain-dispatch refusal, captured-model/context recovery, refusal of candidate
reselection during recovery, token admission
shortfalls, raw output hashes, qualification tampering, strict case identity,
all-24 study ordering and source installation gates. They use fixtures only and
never start a model, Docker, PostgreSQL or a source download.
