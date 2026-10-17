# Frozen013 qualification runner

`qualify014.py` is additive staging source. It imports the existing
`scripts.qualify006` scope/verifier/summary and the existing `CaseRegistry` and
`Workspace` from the explicit `--project` checkout. It does not modify those
modules, historical case definitions, images or experiment evidence. The staging
invocation must supply `--project`; after integration under `scripts/`, the default
is the project root.

The exact original cohort bytes are pinned by SHA-256
`97f681a503ca3e1f63314c5c22c82e6e12be0f7891b2a80b6c16e74042f4fd1f`.
All 24 candidates retain their original order and development/holdout assignment.
No failed or excluded candidate is replaced. Before any source or Docker action,
the runner writes an immutable plan classifying every candidate. Eligibility
requires at most two approved Python source files and 40 added plus removed
lines, verified with actual Git diff statistics. Every source-scope exclusion and
unavailable input remains in the plan and terminal report.

## Required hidden input

Both `--hidden-records` and `--hidden-provenance` are required. The records file
must be a JSON array containing the complete 300-row Lite test split. A cohort
subset is rejected. All seven reviewed metadata fields must match all 300 frozen
metadata rows exactly; each candidate also matches its repository, base commit
and original issue bytes. The provenance JSON must contain these fields:

```json
{
  "dataset": "princeton-nlp/SWE-bench_Lite",
  "revision": "6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2",
  "split": "test",
  "rows": 300,
  "records_sha256": "SHA-256 of the exact hidden records JSON bytes"
}
```

Additional acquisition provenance is allowed. The runner binds the sidecar's own
SHA-256, the hidden records SHA-256, cohort SHA-256, imported implementation files,
runner implementation, approved image IDs, resource roots and source-download
authorization into one immutable binding. Missing or inconsistent hidden input
produces `input_unavailable` for all 24 candidates. It never produces a source
eligibility or qualification claim from incomplete metadata.

## Plan and execution

Use an initially nonexistent `--output` directory within a counted budget root.
Repeating a command is permitted only when its binding is unchanged. Code or
input changes require a new output directory. The following example uses shell
variables only to keep paths readable:

```bash
project=/path/to/new-karos
stage=/path/to/kairos-ai014
PYTHONDONTWRITEBYTECODE=1 "$project/.venv/bin/python" \
  "$stage/qualification/qualify014.py" \
  --project "$project" \
  --hidden-records "$stage/.runtime/qualification-inputs/hidden-lite-records.json" \
  --hidden-provenance "$stage/.runtime/qualification-inputs/hidden-lite-provenance.json" \
  --output "$stage/.runtime/qualification014-run1" \
  --budget-root "$project/.runtime/investigations" \
  --budget-root "$project/.runtime/study007" \
  --budget-root "$project/.runtime/retrieval011" \
  --budget-root "$stage" \
  --allow-source-download
```

Supply every other owned experiment root with another `--budget-root`; omit an
example root only when it does not exist and is not owned experiment storage.
The established historical `.runtime/investigations` root must be covered. The
aggregate guard de-duplicates nested roots, enforces 6 GiB of logical file bytes
and a 4 GiB free-space reserve, and includes the hidden input and all new output.
It rejects roots traversing symbolic links.

Without `--execute`, the command creates only the bound plan and plan report. It
does not inspect Docker, download source, start services, make model calls or run
tests. To execute the frozen plan, repeat the same command with `--execute`.
Source acquisition additionally requires `--allow-source-download` in both the
plan and execution binding. Without it, missing source remains
`input_unavailable`. No source fallback or unpinned checkout is used.

Only these historical reviewed images are accepted:

| Repository | Existing tag | Required image ID |
| --- | --- | --- |
| Django | `kairos-investigation-django:build003` | `sha256:df8f0ef9be4fb1f710c20ba9738a4ec6fa68d2a1d6422fce277cbfc4b69ed73e` |
| pytest | `kairos-investigation-pytest:build006` | `sha256:3407ec26f4cb3a0a626c5c8412b9e644e319b935a7a5f42ecfc867a9c18192f2` |

The runner does not start Docker or build/pull images. An unavailable image or
changed image ID produces a durable `environment_failure`. Existing Workspace
restrictions apply: network disabled, read-only container, 1 GiB memory, two CPUs,
unprivileged user, 120-second checks and bounded raw output.

Source comes only from the approved repository's GitHub codeload URL at the full
40-character base commit. Downloads are bounded at 80 MiB and extracted source at
240 MiB. Streaming chunks and measured archive contents pass the aggregate guard
before writes. Traversal, special files, hard links and escaping symlinks are
rejected. The source archive is removed only after its full hash and extracted
tree digest are saved. Temporary localization and Workspace trees use the owned
case directory. Before checks, storage admission includes both temporary source
copies, hidden test growth and a 16 MiB bounded-output reservation. Persistent
source is moved into the registry rather than copied again.

## Qualification and recovery

Qualification requires all of the following:

1. The baseline completes every selected regression and records an actual declared
   behavioral regression failure, without an environment error or timeout.
2. The reference repair completes all selected tests and passes every required
   regression with a successful process exit.
3. Both bounded raw output captures are complete and neither hits the output cap.

The existing verifier's test selection and any omissions are frozen before the
baseline. Internal preflight case definitions retain `qualified: false`. Only the
final independently captured receipt may claim qualification. Reference-derived
entry files are qualification material and must not become inference localization
hints. Public benchmark pretraining exposure remains unknown.

Each baseline/reference dispatch first saves a durable started marker, then a
separate immutable result. A completed check is reused on restart. A started
check lacking a final capture is unknown and is never automatically dispatched
again. Completed case receipts are hash-verified before reuse. Completed image
failures also remain terminal. A new output binding is required for a deliberate
new attempt; the old attempt remains preserved.

For each case, the runner saves all available check outputs, source and test
scope provenance, case definition, full source-file hashes and symlink targets,
and a terminal receipt before removing its own ephemeral tree. It verifies both
the exact owner receipt and current tree manifest before deletion. Interrupted
cleanup can finish on restart. No historical source or unowned tree is removed.

`report.json` preserves `qualified`, `behavioral_mismatch`, `environment_failure`,
`input_unavailable` and `scope_excluded` separately, including repository/split
counts and all 24 IDs. `execution_complete` describes terminal accounting;
`qualification_complete` additionally requires no unavailable inputs or
environment failures. Neither field implies that all candidates qualified. The
qualified count and per-case receipts determine that result. No inference,
training or official benchmark score is claimed.

## Verification

```bash
cd /path/to/kairos-ai014/qualification
PYTHONDONTWRITEBYTECODE=1 /path/to/new-karos/.venv/bin/python \
  -m unittest -v test_qualify014.py
```

The 16 tests cover exact order/splits, explicit exclusions, full hidden split and
SHA binding, strict source boundaries and true diff counts, aggregate storage,
complete behavioral qualification, immutable capture, uncertain-dispatch refusal,
resumption after an interrupted baseline, evidence tampering and owned cleanup.
They do not call Docker, download source or make model calls. Real qualification
requires separately captured execution receipts.
