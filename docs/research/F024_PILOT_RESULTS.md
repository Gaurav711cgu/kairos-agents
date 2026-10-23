# F024 pilot results (final)

Evidence: `evidence/localization024/f024-pilot/{turn1,turn2}/MANIFEST.json`. Two development cases
(A = django, B = pytest) x {issue-only frozen023, gold-hunk oracle} x {base 14B, training5
adapter}. 13 generations (8 + 5) of a cap of 16, on a free Colab T4 with the pinned model revision
and dependency profile. Journals, parent bindings and capture hashes were verified for all 13.

## Outcome per chain (last turn scored independently in pinned Docker images)

| Chain | Turn 1 | Turn 2 | Final |
|---|---|---|---|
| A issue base | accepted | (none) | breaks import (0 tests ran) |
| A issue adapter | accepted | (none) | breaks import |
| A oracle base | no-op | changed | **executable, 412 tests ran, 6/6 regression tests still fail** |
| A oracle adapter | indentation | **identical to turn 1** | indentation |
| B issue base | syntax | **identical to turn 1** | syntax |
| B issue adapter | parse (512-token truncation) | changed, complete | indentation |
| B oracle base | accepted | (none) | breaks import |
| B oracle adapter | syntax | **identical to turn 1** | syntax |

**Verified repairs: 0/8.** Funnel at the final turn: 4 parse/syntax-valid of 8, 1 importable and
executable of 8, 0 passing regression. With 2 cases no rate generalizes; this is a pipeline check.

## Defects by layer

- **Model reasoning:** even with every edited line visible (oracle), base and adapter failed. The
  one executable edit removed the right import but did not produce the correct behaviour.
- **Patch protocol:** the accepted edits deleted or overwrote whole lines (removing exported classes;
  overwriting `import attr` instead of inserting). Source handles and the validator worked as designed.
- **Validation:** syntax-only acceptance let 3 import-breaking edits through to Docker. The new
  deterministic `scripts/edit_preflight024.py` (`dangling_removals`: a removed top-level name
  still referenced in the module or imported by a sibling) flags all 3 retrospectively and does
  not flag the executable edit, whose removal matches the gold fix. Analysis only; it is not
  wired into the frozen validator.
- **Feedback:** 3 of 5 turn-two outputs were byte-identical to turn one under greedy decoding.
  The feedback, a `rejected_attempt` key inside the JSON payload, was effectively ignored. That is
  a hypothesis about placement and attention, not tested.
- **Retrieval:** issue-only context for A included the right file; both issue-only arms broke
  imports. Oracle context did not help either arm, so retrieval is not the binding constraint for
  these cases.

## Truncation and memory

- One turn-one output hit the 512-token cap without EOS and was unparseable. Its turn-two retry
  was 154 tokens and complete but mis-indented.
- Peak `torch.cuda.max_memory_reserved`: 9.96 to 10.93 GiB (10.70 to 11.74 GB) at at most 2040
  tokens in+out on a 14.56 GiB T4. The "1 GiB" figure in the 014 docs is the CPU Docker sandbox
  limit for regression checks, not GPU memory. Raising the output cap to 1024 is plausible from
  this headroom but untested; the historical run peaked at 14.42 GiB at 3539 tokens. Do not
  raise it without a measured run at the new length.

## Highest-value next change

1. Wire `dangling_removals` into the validation path for new runs (a new protocol version), so
   import-breaking edits are rejected before Docker and their names go into feedback.
2. Add safe runtime-diagnostic feedback: an import-only check of the edited module in the pinned
   sandbox (no test material), feeding back the exception type and message. Syntax feedback
   cannot express "you deleted MD5".
3. Test feedback placement, for example a separate instruction field ahead of the source payload,
   offline first, since the current placement produced identical retries.

Training is still not justified by evidence. The oracle arm shows reasoning failures, but 2 cases
cannot separate model capability from protocol effects.

## Correction (22 October 2026, redesign 025)

The "Retrieval" bullet above is wrong. A re-read of the packaged prompts shows that issue-only
context held 0 regions from any gold file in both cases: A had `functions/text.py` and two template
backends instead of `cache/utils.py`; B had `_code/code.py`, `capture.py` and `mark/structures.py`
instead of `hookspec.py`/`skipping.py`. Retrieval was binding for the issue arm (6 of 13
generations). Details: `docs/REPAIR_REDESIGN_025.md`, Addendum 1.
