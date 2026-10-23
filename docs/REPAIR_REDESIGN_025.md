# Repair engine redesign 025: root cause and decision record

Status: 22 October 2026, research in progress. Evidence base: the 13 real F024 generations
(`evidence/localization024/f024-pilot/{turn1,turn2}/colab-results`) and their independent Docker
scores. Cases are referred to as A (django) and B (pytest). This document is append-only:
later decisions are added below and nothing is overwritten.

## Phase 2: forensic findings (verified from captures)

| Hyp. | Claim | Supporting evidence | Contradicting evidence | Confidence | Falsifying diagnostic |
|---|---|---|---|---|---|
| H4 | No interaction: the model never observes code behaviour | The only executable edit (A oracle base t2) implemented the issue's idea but used sha256 instead of md5 and dropped the `:` separator. The issue text itself discusses alternate hashes, so only test output disambiguates. The model cannot run anything. | 3 import-breaking edits would also be caught by a static check without any interaction | High | Give the same model one observation of a targeted test failure; if it does not change the A edit, H4 is not the binding cause |
| H3 | Edit protocol traps | No insert operation: B oracle base replaced line 11 with a new import and destroyed `import attr`. A issue base emitted 5 empty replacements that deleted classes. 4 final outputs were indentation or syntax errors from whole-line rewriting. | 12/13 outputs were valid protocol JSON, so the model understands the format | High | Replay the same intents through a search/replace format (anchor-based, insert expressible); the attr overwrite becomes impossible to express accidentally |
| H5 | Feedback not salient | 3/5 turn-two outputs were byte-identical to turn one under greedy decoding. Feedback was a `rejected_attempt` key at char ~2300 of a 5400-char JSON user message, not a conversational turn. | 2/5 retries did change (A oracle base, B issue adapter) | Medium-high | Same model and decoding with feedback as a separate user turn after the model's own output; identical-retry rate should drop |
| H2 | Prompt contract not suited to the checkpoint | The user message is a JSON-serialized payload with numbered lines; the output is JSON-only with no space to reason. | Template, roles and EOS are correct; the model followed the format | Medium | Same task with plain-markdown context and a think-then-edit contract |
| H1 | Base capability insufficient | Oracle arm failed for both base and adapter; the adapter shows no gain (trained on 2 examples) | Failures are confounded by H3/H4/H5; the one executable edit shows partial understanding | Unknown (confounded) | Run after H3-H5 fixes; also test a stronger open model on the same tasks |
| H6 | Token/context limits | 1/13 truncated at 512 tokens (its retry at 154 tokens was complete) | Oracle contexts contained every edited line and still failed | Low | Raise the cap only with a measured memory run |
| H7 | Inference defect | none found | EOS `<|im_end|>` = 151645 matches config; 12/13 ended on EOS; 0 template-token leaks; template rendering verified 20/20; adapter outputs differ from base | Low | n/a |

## Pending

- Phase 1 upstream research (mini-swe-agent, Aider, Agentless, OpenHands) with source citations.
- Phase 3 architecture comparison, Phase 4 plan, Phase 5 offline prototype, Phase 6 approval gate.

## Phase 1: upstream research (gh api source reads; V = verified in code, A = assumed from docs)

| System | Mechanism | Source | Kairos today |
|---|---|---|---|
| mini-swe-agent | One bash tool; append-only chat; every action's real output returned as its own user turn (head/tail 5000 chars) | `src/minisweagent/agents/default.py`, `config/mini.yaml` (V) | Single shot, no observation |
| mini-swe-agent | Format errors become a fresh user message; 3 consecutive errors end the run; truncation gets a "respond more concisely" message | `models/utils/actions_toolcall.py`, `actions_text.py` (V) | Feedback is a JSON key mid-payload |
| mini-swe-agent | Docker env `--rm`; submit sentinel `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`; step/cost/wall-time limits | `environments/docker.py`, `environments/local.py` (V) | Journal plus caps (comparable) |
| Aider | Content-anchored SEARCH/REPLACE; exact match then whitespace-tolerant fallback | `aider/coders/editblock_coder.py` (V) | Line-number whole-line replacement, no insert op |
| Aider | Unmatched block gets the failed block echoed plus "Did you mean ... actual lines", as a new user turn; up to 3 reflections | `editblock_coder.py` apply_edits; `base_coder.py:101` `max_reflections = 3` (V, lead re-checked) | Byte-identical retries 3/5 |
| Aider | Lint (compile + flake8 with surrounding context) and optional test output fed back as a reflection | `base_coder.py` ~L1596-1622, `aider/linter.py` (V) | Syntax-only validator, no import check |
| Aider | Small open models benchmarked with `whole`, not `diff` (e.g. qwen2.5-coder 7B q8 = whole) | `aider/website/_data/edit_leaderboard.yml` (V, lead re-checked) | Custom JSON format |
| Agentless | localize, then SEARCH/REPLACE repair with 1 greedy + N temp-0.8 samples, then filter by regression + reproduction tests, then rerank; no multi-turn loop | `agentless/repair/repair.py` L108-131, L409-446; `agentless/test/*` (V) | 1 greedy sample, no filtering |
| OpenHands | CodeAct loop with editor actions in a Docker runtime | not verified (A) | n/a |

Caveat: no upstream result read here demonstrates 14B-class SWE-bench repair. These are mechanism fixes,
not guaranteed gains.

## Phase 3: architecture comparison

| | A. Fix existing single-shot | B. Architect then Editor | C. Bounded interactive loop (Aider-shaped) |
|---|---|---|---|
| Addresses | H3 (format), H5 (feedback turn) | H3, H2 (reasoning space) | H3, H4 (observation), H5 |
| Fair observation available | none | none | compile/import/lint + visible or synthetic tests; never hidden FAIL_TO_PASS |
| 14B feasibility | yes | 2 calls per attempt, larger context | yes if history is truncated to the latest attempt (T4 envelope 3539 tokens) |
| Where it runs | Colab single shot (exists) | Colab | Colab: model plus a disposable checkout and sandboxed subprocess checks; final oracle stays local Docker |
| Cost | lowest | ~2x | ~1-4 generations per task |
| Security | unchanged | unchanged | generated code runs only in a disposable Colab VM, never on the host; final scoring in pinned Docker (network none) |
| Kairos compatibility | journal/receipts reused | same | same journal semantics per step |

**Decision (lead):** C, with A's format fix inside it: content-anchored SEARCH/REPLACE edits, a
think-then-edit contract, feedback as a new user turn, and reflections up to 3. B is deferred: it
doubles generations without addressing observation. The mini-swe-agent bash-only loop is rejected
for a 14B: it depends on frontier-model multi-step shell reliability (A).

**Honesty constraint:** under fair rules the loop may observe compile/import/lint output and visible
or synthetic tests only. The F024 case-A near miss (sha256 vs md5) depends on hidden test values and
is not fixable by fair observation. Fair observation addresses the import-break class (3/8).

## Hardware finding
This Mac has 8 GB RAM (Apple M2) and no CUDA, so the 14B (about 9 GB at 4-bit) cannot run locally;
only 3B/1.7B GGUFs exist here. Every 14B experiment runs on the Colab T4. A stronger model (for
example a 32B coder at 4-bit, about 18-20 GB) does not fit a free T4 and would need paid GPU or API
access: a spend decision for the user.

## Phase 4: engineering plan (design C)

Loop per chain: render prompt (markdown context with numbered regions, issue, then "think briefly,
then emit SEARCH/REPLACE blocks") -> generate -> `parse_blocks` -> `apply_blocks` (exact unique
match, captured-region scope, syntax, `dangling_removals`, workspace prefix gate) -> on rejection,
the reason becomes a new user turn after the model's own assistant turn -> at most 3 reflections ->
the final accepted patch goes to unchanged local Docker scoring (`f024_score`, pinned images,
network none).

| Item | Detail |
|---|---|
| New | `scripts/search_replace025.py` (built), `scripts/search_replace_control025.py` (built), runner `scripts/f025_colab.py` (not built: chat history, turn cap, journal per step reusing f024 intent/capture hashing) |
| Preserved | f024 journal and hash binding, model/dependency pins, `workspace.propose` gate, `f024_score`, frozen validator for historical runs (untouched) |
| Observation (fair) | static only in the first experiment: no-match/multi-match with line numbers, out-of-scope, syntax error, dangling names. No test output, no hidden tests, no network in the loop |
| Security | no generated code executes in the loop; execution happens only in the pinned local Docker scorer |
| Rollback | new files only; f024 path unchanged; delete the 025 files to revert |
| Budget | free Colab T4, $0, at most 16 generations |
| Not addressed | H1 capability, spec ambiguity needing behavioural tests (case A sha256 vs md5) |

## Phase 5: offline validation (lead re-ran, 22 October 2026)

- `pytest tests/test_search_replace025.py tests/test_edit_preflight024.py tests/test_feedback_turn021.py`: 27 passed.
- Positive control (gold patches, infrastructure only, never model-visible): 4/4 gold hunks are
  expressible as a unique SEARCH inside the captured oracle regions (django-11772 `cache/utils.py`;
  pytest-8124 `hookspec.py`, `skipping.py` x2).
- The F024 `import attr` overwrite cannot be expressed by accident: an insert is anchor plus new
  lines, and a dropped name is rejected by `dangling_removals` (test-covered).
- Not done: replay of the 13 F024 outputs (they use the line-handle format and cannot be replayed
  as SEARCH/REPLACE without rewriting them, which would be authoring, not replay); `apply_blocks`
  on the real source tree; the Colab runner.
- **These are deterministic mock and control results. They show the pipeline can carry a correct
  edit. They are not evidence that the 14B can produce one.**

## Phase 6: GO/NO-GO

- GO for offline build of `scripts/f025_colab.py` plus mocked-model tests (no GPU).
- NO-GO for GPU now: the runner does not exist yet.
- Proposed experiment after the runner passes offline tests (requires user approval):
  base `unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit@ecfc63c0` only (the adapter showed no gain);
  the 2 qualified development cases x {issue-only, oracle} = 4 chains; at most 4 generations per
  chain, 16 in total; greedy; output cap 768 tokens; prompt plus output within the measured
  3539-token envelope; stop on any peak reserved memory above 13.5 GiB, any journal or hash
  failure, or 16 generations. Validation and holdout untouched.
- Success criteria: primary, at least 1 of 4 chains a verified repair in local Docker (this is a
  2-case pipeline result and does not generalize); secondary, 0 import-breaking patches reach Docker,
  and fewer than 3 of the reflection turns identical to the previous turn.
- Q answers: Q1 cause = H4 > H3 > H5 (H1 unknown); Q2 architecture = C; Q3 stronger model = needs
  more than T4 memory (spend decision); Q4 fair feedback = static now, visible/reproduction tests
  later; Q5 smallest test = the 16-generation run above.

## Addendum 1 (22 October 2026): reverse-engineering pass

### Upstream lifecycle, added: SWE-agent (read via gh api, V)
- `config/default.yaml`: plain system prompt; issue in `<pr_description>`; explicit steps "reproduce
  with a script, edit, rerun the script, think about edge cases"; every observation returns as
  `OBSERVATION:` in a new turn; `review_on_submit_m` makes the model re-check its diff before submit.
- `tools/edit_anthropic/bin/str_replace_editor`: `str_replace` requires `old_str` to occur exactly
  once (L524-532, "Multiple occurrences ... in lines"); has a separate `insert` command; runs flake8
  `F821,F822,F831,E111,E112,E113,E999,E902` before and after the edit (L186, L540-575) and reports only
  new errors in the edited window; echoes the edited snippet with line numbers back to the model
  (L577-590).
- Common to Aider, SWE-agent and mini-swe-agent: content-anchored edits, the result of every edit
  shown back to the model, and new errors reported in a separate turn. Kairos F024 had none of the three.

### Per-generation reconstruction (all 13; read from captures, packages and final scores)

Prompt for all 13: 2 messages (system, user). The user message is a JSON string with `issue`,
`original_source` (numbered `N: code` regions of 11-24 lines) and `protocol`. Turn 2 adds a
`rejected_attempt` key inside the same JSON user message; there is no assistant turn. Decoding is
greedy, with no repetition penalty, and EOS is `<|im_end|>`.

| Chain | In/out tokens | Gold file in context? | Generated edit | Validator / score | Earliest preventing design |
|---|---|---|---|---|---|
| A issue base t1 | 1359/256 | **no** (text.py x2, template backends x2) | 5 empty replacements delete the MD5/Ord/SHA classes | accepted / ImportError `MD5` | retrieval; then dangling-name check |
| A issue adapter t1 | 1359/402 | **no** | rewrites the hash classes and drops MD5 | accepted / ImportError | same |
| A oracle base t1 | 693/304 | yes | re-emits lines 1-12 nearly unchanged | no_change | echo of the applied diff |
| A oracle base t2 | 1528/197 | yes | removes `quote`, uses sha256 with no `:` join | **executable, 6/6 regression still fail** | behavioural check (hidden tests only, so not fair) |
| A oracle adapter t1, t2 | 693/85, 1103/85 | yes | replaces lines 7-10, which include the `def` line, with body-only text; **t2 byte-identical** | syntax_indentation | content anchor (the line range swallowed the `def`) |
| B issue base t1, t2 | 965/93, 1302/93 | **no** (`_code/code.py`, capture.py, mark/structures.py) | docstring line rewrite, unterminated; **t2 identical** | syntax_other | retrieval |
| B issue adapter t1 | 965/512 (no EOS) | **no** | rewrites unrelated `code.py` regions, truncated | parse | retrieval; output cap |
| B issue adapter t2 | 1084/154 | **no** | dedents methods | syntax_indentation | retrieval |
| B oracle base t1 | 772/160 | yes | **replaces `import attr` with `from typing import Any`**; rewrites line 96 into 5 lines (duplicate keys) with `"globals": globals_` | accepted / ImportError (`attr`) | insert expressible; dangling-name check |
| B oracle adapter t1, t2 | 772/266, 1478/266 | yes | **copies the `11: ` line-number prefixes into `new`**; **t2 identical** | syntax_other | unnumbered source rendering |

### Corrected root-cause ranking (supersedes the Phase 2 order; Phase 2 is kept above)
1. **Insufficient source (issue arm): High, new.** Issue-only context held 0 regions from any gold
   file in both cases, so 6 of 13 generations could not have succeeded under any edit protocol. This
   corrects `docs/research/F024_PILOT_RESULTS.md` ("issue-only context for A included the right file").
2. **Protocol traps (H3): High.** Of the 7 oracle generations, 5 failed from line-range semantics or
   numbered rendering: the swallowed `def` (x2), an overwrite instead of an insert (x1), and copied
   `11: ` prefixes (x2).
3. **Feedback unusable (H5): High.** Identical retries 3/5; no echo of the applied result, no
   separate turn.
4. **No behavioural observation (H4): Medium.** It matters for exactly 1 of 13 (A oracle base t2).
   Fair observation cannot supply the hidden expected values.
5. **Model capability (H1): unknown.** In the cleanest generation (A oracle base t2), the model
   understood the issue's idea.

### Differential matrix

| Mechanism | Insert | Accidental deletion | Line-number echo | Feedback | Fits 14B / T4 | F024 failures it would block |
|---|---|---|---|---|---|---|
| Kairos source handles (now) | no | easy (range swallows lines) | yes (numbered input) | JSON key | yes | none |
| SEARCH/REPLACE + preflight (built) | yes | rejected (`dangling_removals`) | no (unnumbered input) | separate turn | yes | 3 import-breakers, 5 protocol traps (hypothesis: assumes the model emits valid blocks) |
| Whole-function replace | yes | contained to one function | no | separate turn | yes, but more output tokens | protocol traps; not cross-function edits (B gold edits 2 files) |
| Whole-file | yes | easy (long rewrite) | no | separate turn | **no**: files exceed the 512-768 output cap | n/a |
| mini-swe-agent bash loop | yes | possible | no | separate turn | doubtful for 14B multi-step shell; needs a repo checkout in the VM | depends on agent skill |

Decision: **B + C + retrieval fix**. Replace the edit subsystem (SEARCH/REPLACE, unnumbered rendering,
preflight) inside a bounded loop with separate-turn feedback. Keep the model backend (D deferred):
F024 cannot separate capability from protocol defects, and a bigger model needs a spend decision. A
is subsumed. **The retrieval miss is independent of the editor and must be fixed or bypassed
(oracle arm) before any repair claim.**

Challenge to C: Kairos already had an interactive investigation loop (`kairos_api/investigations/model.py`,
`run_checks`, revise phase), recorded 0/20 historically. Interaction alone is therefore not
sufficient; the 025 loop differs in the edit contract, rendering and feedback placement.

### Prototype: `scripts/repair_loop025.py` (TDD)
- `run_loop(model, workspace, issue, regions, check, receipts, max_corrections=3, max_reads=2)`.
- Flow: plain-text prompt with unnumbered regions → `parse_blocks` → `apply_blocks` (exact unique
  match, region scope, syntax, dangling names, prefix gate) → `check(workspace)` → on failure
  `workspace.reset()` (rollback) and the error goes back as a new user turn after the model's
  assistant turn.
- Stops on: accept, more than 3 failed corrections, or a byte-identical reply.
- `READ path a-b`: bounded (80 lines, approved prefix, budget 2); the text is unnumbered; the read
  widens the editable regions.
- Receipts: JSONL hash chain (step, kind, reply/patch sha256, feedback).
- `subprocess_check`: `python -I` child with an empty environment and a timeout, run on the candidate
  copy. **For synthetic tasks and disposable Colab VMs only. Model output on this host goes through
  the pinned Docker `workspace.checks`.**
- Tests: `tests/test_repair_loop025.py`, 11 tests on a synthetic defect (`add` returns `a - b`) with
  a visible public check. Together with the 025, 024 preflight, feedback and f024 suites: **54
  passed**. The red phase was observed (module missing). One test bug was fixed: a duplicate scripted
  reply correctly triggered the repeat stop.
- **The mock model's replies are written by the test author. These tests prove loop mechanics only,
  not that any model can repair.**

### Model assumptions (Phase 5 of the brief)
- The chat template, roles, EOS and pad were all verified earlier (H7 Low). Qwen2.5 templates support
  multi-turn natively, so the loop needs no template change.
- Greedy decoding without sampling makes identical retries likely when feedback is weak. Agentless
  samples at temperature 0.8 instead. Proposal: greedy on the first try, temperature 0.8 on
  corrections (one variable, recorded).
- The training5 adapter (2 examples, checkpoint 80) showed no gain and learned a JSON contract the
  new protocol drops. **Discard it from the next experiment.** No retraining.
- Capability test that separates protocol-following from bug-fixing, run on authored synthetic tasks:
  - P-tasks: the issue states the exact change ("rename X to Y in f"). These measure format compliance.
  - R-tasks: the issue describes a symptom only, with a visible failing check. These measure repair.
  - Interpret R only if P compliance is at least 5/6.

### Architecture

```
issue + regions (retrieval fixed, or oracle) ──► render (unnumbered) ──► 14B (Colab)
      ▲                                                            │ reply
      │ new user turn: reject reason / check output / READ text    ▼
      └──── ≤3 corrections, ≤2 reads ◄── apply_blocks ◄── parse_blocks
                                            │ accepted
                                            ▼
                           check (synthetic: subprocess in VM; dev: static only)
                                            │ final patch + hash-chained receipts
                                            ▼
                           local f024_score (pinned Docker, network none) = only repair verdict
```

### Changed-file plan
- Built (new): `scripts/search_replace025.py`, `scripts/search_replace_control025.py`,
  `scripts/repair_loop025.py`, and tests for each.
- To build (offline, no approval needed): `scripts/f025_colab.py` (Colab driver: model callable,
  envelope guard of 3539 tokens per call, temperature switch, journal), `scripts/f025_tasks.py`
  (6 authored synthetic P/R tasks with visible checks), and the f024_score adapter for 025 patches.
- Untouched: frozen F024 evidence, the f024 validator, sandbox flags.
- Rollback: delete the 025 files. Nothing existing imports them.

### GO / NO-GO
- **GO** for the offline build of `f025_colab.py` and `f025_tasks.py`, with mocked-model tests.
- **NO-GO** for the GPU now: the runner and tasks are not built.
- Proposed run, after approval: base 14B only, no adapter. 6 synthetic tasks plus the 2 dev oracle
  cases (static check only, then local Docker scoring), at most 6 calls each, **at most 48 calls**
  (about 27 minutes at the measured 33.8 s), on a free T4 at $0. Stops on peak memory above 13.5 GiB
  or any journal failure. The issue arm is excluded until retrieval is fixed.

## Addendum 2 (22 October 2026): F025 run 1, the first real-model run of the 025 loop

Run: Colab T4, base 14B at the pinned revision, package `0aa392e1…`. The user ran it; the first
attempt halted at the django source fetch (harmless `../` symlinks under `docs/`), and
`fetch_dev_source` was hand-patched in the Colab VM before the rerun (the same fix is in the repo,
with a regression test). Journal: 21/21 captures verified and bound to the package. Peak reserved
memory 11.59 GiB. Evidence: `evidence/localization025/f025-run1/` (MANIFEST.json, 61 files).

### Pre-registered outcome
- Synthetic: 2/6 accepted (p1, p2). Dev: 0/2 (django repeated, pytest exhausted). **0 verified repairs.**

### Why: harness defects, observed in the real replies
1. **Fences inside blocks:** the model wrapped SEARCH and REPLACE bodies in ```` ```python ```` fences
   (p3, r1, r3, django, pytest), so SEARCH never matched.
2. **Placeholder path:** the model copied `path/to/` from the prompt's example (`path/to/pkg/tags.py`,
   `path/to/file.py`), so the path gate rejected the edit.
3. **READ refused:** `READ pkg/seq.py 1-10` on a 3-line file was refused instead of clamped (4 chains).
4. Once the reject reason did not explain the problem, the model sent the same reply again,
   including under temperature 0.8 sampling, and the repeat stop ended 5 chains.

### Counterfactual replay (the real captured replies through the fixed parser; not a new model run)
- Synthetic: **6/6** chains: the model's first edit-bearing reply applies and **passes its visible
  check**, including **3/3 symptom-only (R) repairs**.
- Dev: all 5 edit-bearing replies now apply statically. Behaviour: the django edit is the same sha256
  change that failed 6/6 regression tests in F024; the pytest edit adds `"globals": globals()` instead
  of the gold hook. Both are expected to fail Docker scoring (not run).
- Interpretation: this is the first evidence that the 14B can repair simple symptom-only bugs when
  the protocol does not block it. The 6 tasks are tiny, and they were inspected while designing the
  fix, so they are no longer held out.

### Fixes (TDD, 110 tests pass)
- `parse_blocks` strips fences inside blocks.
- `apply_blocks` maps a non-captured path to the single captured file in which SEARCH occurs exactly
  once (constrained mode only).
- READ clamps to the file length and 80 lines.
- The prompt says to replace `path/to/file.py` and not to put fences inside blocks.

### Next run (staged: `f025-probe/upload-v3/`, package `1009496e…`, code `cc65b791…`)
6 **new held-out** synthetic tasks (`HELDOUT` in `f025_tasks.py`, authored after run 1 and never used
for tuning) plus the same 2 dev cases. At most 48 calls. Success = held-out R-task pass rate and dev
Docker scoring.

## Addendum 3 (22 October 2026): F025 run 2, held-out synthetic tasks and dev Docker scoring

Run: Colab T4, base 14B, package `1009496e…`, code `cc65b791…` (no hand patch), results zip
`010d5774…`. Journal: 13/13 captures verified. Peak reserved memory 10.53 GiB. Evidence:
`evidence/localization025/f025-run2/` (with MANIFEST.json).

| Set | Result |
|---|---|
| Held-out P tasks (format following) | **3/3** accepted, visible check passed, 1 call each |
| Held-out R tasks (symptom only, never used for tuning) | **3/3** visible check passed (each did 1 READ, then 1 edit) |
| Dev django-11772 (oracle context) | statically accepted; Docker **behavioral_mismatch**, 6/6 target tests still fail (sha256 instead of md5; dropped the `:` join) |
| Dev pytest-8124 (oracle context) | statically accepted; Docker **behavioral_mismatch**, 4/4 `markeval_namespace` tests still fail (added `"globals": globals()` instead of the `pytest_markeval_namespace` hook) |

**Verified repairs: 0/2 dev.** **Synthetic visible-check pass: 6/6 held-out.**

Interpretation (verified vs inferred):
- Verified: with the 025 protocol, the 14B follows the edit format and fixes small, local
  symptom-only bugs it was never tuned on (6/6, 13 calls). The protocol and harness are no longer
  the binding constraint.
- Verified: on both real dev cases the model produced the same wrong change in F024 and in both
  F025 runs. Each fix needs knowledge the context does not give: django's expected md5 key values,
  and pytest's new hook API, which spans 2 files. Visible feedback never says why the change is
  wrong, because only hidden tests know.
- Inferred: the binding constraint is now real-code reasoning and specification knowledge.
  Candidates, in cost order:
  1. let the loop run and read repository tests, when the issue names behaviour;
  2. a reproduction-test step (SWE-agent style) inside a disposable VM;
  3. a stronger model (needs more than T4 memory, so a spend decision);
  4. fine-tuning (needs data, GPU and approval).
  Two dev cases cannot rank these.

## Addendum 4 (22 October 2026): case validity, options 1 and 2 built, external research, fine-tuning plan

### The 2 dev cases are underspecified (verified)
- Neither `django__django-11772` nor `pytest-dev__pytest-8124` is in SWE-bench Verified (checked
  against all 500 ids from the Hugging Face datasets server). Verified excludes tasks that human
  annotators judged underspecified or unfairly tested.
- django-11772: the issue itself proposes moving away from MD5 (FIPS). The hidden tests expect new
  MD5 values computed with per-argument `update` plus `:`. Base-commit tests show only the old values.
- pytest-8124: the issue body is an empty PR template. `FIND pytest_markeval_namespace` over the
  pinned source and `testing/` returns no line, so the hook name the hidden tests call is not
  discoverable by any fair means.
- Consequence: 0/2 on these cases does not measure repair capability. The next development set must
  come from Verified ∩ development bucket ∩ django/pytest (pinned images exist) ∩ unexposed: 75
  candidates before the exposure scan.

### Options 1 and 2 (built by an agent, re-verified by the lead: 121 tests pass)
- `FIND <text>` (source + visible test roots, 20 hits) and `READ` of base-commit test files
  (read-only; edits to tests stay rejected; the hidden test patch is never present). They share a
  budget of 4.
- `RUN` + python block: a model-written reproduction script runs against the candidate tree in a
  disposable VM only (`allow_run=host_checks`), with a 30 s timeout, an output tail, a process-group
  kill and a budget of 3.
- `fetch_dev_source` also extracts `tests/` (django) and `testing/` (pytest). Checked on the real
  pinned archives: fetch 3.2 s / 0.1 s, FIND 0.6 s.

### External research (agent, primary sources; see the task report)
- 14B references on SWE-bench Verified: SWE-Gym 16.4% (SFT on 491 trajectories), R2E-Gym 26.8%
  (SFT), with large further gains from test-based best-of-n. All are trained on 2-8 H100 at 32k
  context.
- For open models, bounded workflows beat open agents (SWE-Gym on Lite: MoatlessTools 7%/19% vs
  OpenHands 1%/3% for 7B/32B zero-shot). This supports keeping the bounded loop.
- Top cheap idea: multiple samples, filtered by visible tests and a model-written repro test (SWE-Fixer
  +2.6 points from P2P filtering; log-linear best-of-n gains in SWE-Gym and R2E-Gym).

### Fine-tuning plan (option 4; approved in principle, not started)
- Agent-trajectory SFT (SWE-smith, SWE-Gym, R2E) is infeasible on a T4 (32k context, multi-H100).
- Feasible: QLoRA SFT of the 14B on single-turn issue+context → SEARCH/REPLACE pairs from
  `internlm/SWE-Fixer-Train-110K` (MIT; its authors exclude SWE-bench repositories). Filter:
  - drop the 12 SWE-bench repositories and their forks;
  - drop n-gram overlap with any SWE-bench problem statement;
  - keep prompts of at most 3k tokens and single-file edits;
  - take 2-5k examples;
  - run Unsloth on a T4 in about 1-2 h per epoch (unverified).
- Expected gain: no published T4 single-turn result. It most likely improves format and localization,
  and is unlikely to fix specification gaps. Run it only after run 3 (valid cases + options 1/2 +
  best-of-n) shows where the model still fails, and only on development cases. The dataset download
  happens in Colab and is approved under option 4.

## Addendum 5 (22 October 2026): F025 run 3, the first verified model-generated repairs

Setup:
- 5 SWE-bench **Verified** django 3.1 development cases: 12193, 12276, 12304, 12325, 12774.
- Unexposed and all qualified: binding `b472ae97…`, baseline reproduces, reference passes.
- **Oracle context** (gold-hunk windows; no gold text in the package, checked against base source).
- Base 14B, best-of-2 (sample 0 greedy at call 0), FIND/READ-tests/RUN enabled.
- Package `3ec25fa8…`, results zip `2bf17540…`. Journal 43/43 captures verified.
- Evidence: `evidence/localization025/f025-run3/` (MANIFEST.json).

| Case | Fair pick (visible evidence only) | Docker verdict of the pick | Other sample |
|---|---|---|---|
| django-12193 | s0 (accepted, 1 call) | **verified_repair** | s1 loop_exhausted |
| django-12276 | s1 (accepted) | behavioral_mismatch | s0 loop_call_cap |
| django-12304 | s0 (accepted, 6 calls) | **verified_repair** | s1 loop_repeated |
| django-12325 | s0 (accepted, 1 call) | behavioral_mismatch | s1 loop_call_cap |
| django-12774 | none accepted | n/a | both loop failures |

**Headline (fair pick): 2/5 verified repairs** (`fair_pick_verified = 2`; `pass_at_2` = 2, so oracle
selection adds nothing).

These are the **first independently verified model-generated repairs in Kairos**, with qualified
FAIL_TO_PASS and PASS_TO_PASS in the pinned `build003` image, network none.

Honest reading:
- **django-12193:** the model's patch (`attrs = attrs.copy()` before setting `checked`) differs from
  the gold patch (`{**(attrs or {}), 'checked': True}`) and passes. This is genuine independent repair.
- **django-12304:** the patch equals the gold line, but the issue text itself says "declare
  do_not_call_in_templates = True on the various Choices classes". The model chose the placement
  (the metaclass `__new__`). It is fair, but the issue specified the fix.
- Scope limits: oracle context (the fix location was given); 5 cases; one repository and version.
  This is **not** an issue-only repair rate and not a general rate.

Failure analysis (20 rejections; verified from receipts):
- **10/20 "Path is outside approved source files":** the model wrote `path/to/django/forms/widgets.py`
  or `path/to/file.py`, and its SEARCH text did not match exactly, so the placeholder resolver could
  not map it. The feedback then hid the real problem (a SEARCH mismatch).
- 4/20 no blocks; 3/20 SEARCH no match; 2/20 syntax (indentation); 1 READ budget.
- The model never used RUN. It wasted calls repeating FIND with backtick or `text:` prefixes and
  re-READing the same range.

Next engineering (offline, harness only):
1. Strip a `path/to/` prefix before resolving.
2. Aider-style "did you mean" feedback showing the closest real lines for a SEARCH mismatch.
3. A FIND normalizer (strip backticks and a `text:` prefix) and a duplicate-READ answer that does
   not spend budget.
4. A real example path in the prompt instead of a placeholder.

Fine-tuning gate (plan Task 5, step 6): of the non-verified fair picks and the loop failures, most
are format and harness failures, not specification failures. **Fix the harness first (cheap), rerun,
then decide on QLoRA.** Training on this evidence is premature.

## Addendum 6 (22 October 2026): run-3 error analysis, harness fixes, counterfactual, run 4 staged

Error analysis (systematic debugging; read-only against the pinned sources):
- RC1: SEARCH matched by substring, so `return enum.unique(cls)` matched mid-line and gave a misindented
  replacement. A multi-line REPLACE reproduced the bug as an *accepted* patch with code moved out of
  the method.
- RC2: **every** rejected edit block had SEARCH/REPLACE uniformly dedented to column 0 (similarity
  0.86-0.96 to the real lines). The model does this itself; the parser did not.
- RC3: `path/to/` placeholder prefix.
- RC4: FIND/READ/RUN syntax variants were not parsed.
- RC5 (open): RUN in the same reply as edit blocks is ignored. Correction to Addendum 5: the model
  did attempt RUN once (12304-s1).

Fixes (TDD, 146 tests pass):
- Whole-line matching, then Aider-style uniform leading-whitespace tolerance, reimplemented from
  `aider/coders/editblock_coder.py` `replace_part_with_missing_leading_whitespace` (Apache-2.0, idea
  only).
- `path/to/` stripping and a "closest lines" hint on a mismatch.
- FIND/READ/RUN normalization.
- Prompt: no placeholder path; copy indentation.

Counterfactual (real run-3 replies through the fixed layer; `evidence/localization025/f025-run3-counterfactual`):
- 17/20 edit replies apply. Chains with an accepted edit: 4 → 8 of 10.
- Docker: 3/10 chains verified (12304-s1 added). Cases verified stay **2/5**.
- Every newly applying edit on 12193-s1, 12276, 12325 and 12774 is behaviourally wrong.
- **Reading:** for 12276, 12325 and 12774 the edit harness is no longer the binding constraint; the
  model's repair reasoning is. More of the same tuning will not move the case count.

Run 4 (staged, `f025-run4/upload`, package `ba22173a…`, code `53d09674…`): the same 5 *inspected*
development cases, 2 samples each, with the fixed harness. This is a development iteration, not a
fresh measurement. Expected about 2/5. Next levers after it: more cases (other django versions need
other pinned images), retrieval for the issue-only arm, then a larger-model or QLoRA decision.

## Addendum 7 (22 October 2026): why RUN was never used, and the fix (run 5 staged)

Evidence:
- The model attempted RUN once in run 3 (12304-s1 c1) and once in run 4 (12304-s1 c2). Both times
  the reply also carried edit blocks, and the loop gave blocks precedence, so the script never
  executed (RC5).
- Second blocker: even if executed on Colab, a django 3.1 RUN script dies at `import django`.
  `django/utils/version.py` imports `distutils`, which Python 3.12 removed (reproduced locally).
- The pinned scoring image `build003` runs Python 3.8.20 with asgiref 3.2.10, pytz 2024.2 and
  sqlparse 0.4.4 (read from the image).

Fix (TDD, 153 tests pass):
- RUN in the same reply as edits runs first, with its output included in the edit feedback.
- RUN uses a per-repository interpreter (`RUN_ENVS`) plus a Django settings prelude; a missing
  interpreter is reported to the model, not raised.
- The notebook builds `/content/run-env-django` with uv (Python 3.8 + the pinned packages).
- Prompt: "Before your first edit, RUN a short script that reproduces the issue". Calls per chain
  raised from 6 to 8, giving a package cap of 80.
- Verification in the pinned sandbox (network none, read-only, cap-drop):
  - the model's real run-4 RUN script now executes and returns a meaningful `AttributeError: choices`
    (its own script error);
  - an issue-scenario control prints `''` on the unfixed source, so the environment reaches the bug.
- Not verified: the uv environment on Colab itself (first run will show `python --version` in the
  notebook cell).

Run 5 staged (`f025-run5/upload`, package `426e03a8…`, code `7be6c6ab…`): the same 5 inspected
development cases, 2 samples each, up to 80 calls. Development iteration only.

## Addendum 8 (22 October 2026): F025 run 4 scored (development iteration)

- Journal 29/29 verified. 9/10 chains reached an accepted edit (run 3: 4/10), with fewer calls (29 vs 43).
- Docker: **fair pick 2/5** (12193 s0, 12304 s1), `pass_at_2` 2, verified chains 2/10. The other 7 accepted
  edits are behavioral_mismatch.
- This matches the counterfactual prediction from Addendum 6: the harness now delivers edits, and the
  binding constraint on 12276, 12325 and 12774 is repair reasoning. Run 5 tests whether working
  reproduction scripts (Addendum 7) change that.
- Evidence: `evidence/localization025/f025-run4/` (MANIFEST.json).

## Addendum 7 (23 October 2026): run-5 root causes, fixes, local replay, run 6 staged

Run 5 (scored, Docker): 1/5 cases fair pick (12304), 1/10 attempts; run 4 was 2/5.

Root causes (run-5 captures replayed against the pinned sources, Python 3.8):
- RC6: dev chains have a static-only check, so the first applicable edit ended the chain; the model
  never saw its script on its own edit. Replayed, that output exposes the wrong fix on 12325-s0/s1 and
  12774-s0/s1 (reference patch: clean exit / dict; model patch: same error or a crash).
- RC7: 6/9 scripts died on `app_label` (the prompt's instruction was ignored) and one on `no such table`
  before reaching the bug.
- RC8: `RUN` written inside the fence (12304-s1, 12774-s1) was not parsed.
- RC9 (model, not fixed): 12193 imports a nonexistent `forms.SplitArrayField`; 12276 scripts print nothing.

Fixes (TDD; 163 passed + gated real-Django prelude test on 3.8):
- Prelude registers `__main__` as app `repro`, migrates, and creates a table for each script model.
- `_RUN_INSIDE` parses fence-first RUN; empty output gets a print hint; temp roots stripped from output.
- `self_test` (dev chains only): an applied edit reruns the last script on the candidate; DONE keeps it,
  a passing revision replaces it; corrections exhausted, a repeat, or a call/token cap keep it.

Local replay through `run_chains` (captured replies, DONE at the first divergence): every applied edit
gets its self-test turn; peak envelope estimate 3136/3539. Not a model result.

Run 6 staged: `~/Desktop/resume/kairos-closeout020/f025-run6/upload/` (package
22e23b61…7936). Same 5 inspected dev cases: any gain is development-only, not a validation claim.
