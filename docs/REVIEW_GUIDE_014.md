# Review Kairos in five minutes

**Draft comparison walkthrough:** new comparison routes and homepage changes below are prepared but not installed. Website integration is paused at the user's request. The existing reviewer and accepted retrieval-training page remain available. Use the source reports for completed014 results; do not treat planned visitor steps below as browser acceptance.

## Start the product

Use Python 3.12 and Node 24 from a clean checkout:

```bash
python3 -m scripts.reviewer demo
```

Open http://127.0.0.1:3310. This starts the evidence viewer using genuine captured investigations. No database, Docker, model, login or API key is required to inspect published work. It does not create an investigation when a visitor opens a page.

## Visitor actions and visible results

| Visitor action | System behavior | Result the visitor receives |
| --- | --- | --- |
| Open the homepage | Load the first verified held-out loop case in frozen case order; validate its capture | A real repository issue, observed outcome, counters and an inspection link |
| Select Fresh repair comparison | Load the complete frozen three-strategy report | Held-out totals, actual effort and uncertainty; development cases remain separate |
| Expand Django14752 and inspect the bounded loop | Validate and render its original recorded investigation | The issue, pinned source, two model calls, one captured check and 19 passing tests |
| Open The proposed change | Select the patch whose digest matches the passing check | Readable before/after changes to autocomplete serialization and a patch download |
| Open a source or timeline step | Read the captured original source and action without execution | Source handles, excerpts, context choices, proposals and outcomes in original order |
| Read Independent checks | Render the independently captured verifier result | Verdict, test count, full captured output and a check-result download |
| Open an unsuccessful attempt | Render that actual attempt without substituting a repair | Rejections, missing checks, stop reasons or infrastructure failure evidence |
| Download original investigation | Check bounded byte length and SHA-256 | The exact original capture; a corrupt or unknown record returns an explicit error |
| Open Retrieval training | Load the frozen source-matching experiment | Data splits, selected checkpoint, base/head metrics, uncertainty and trained-head download |

The visitor leaves with a model-proposed patch and independently inspectable evidence. These files are for human review; downloading them changes no repository. The homepage chooses an example for explanation, not which cases enter the study. Every attempted outcome remains in the comparison.

## Keyboard and narrow screens

Use Tab to reach navigation, table regions, expandable steps and downloads. Enter opens a focused disclosure or link. Arrow keys scroll the comparison's bounded table region. At 390 px, the document should not overflow; wide source/diff text remains inside its own region. The browser acceptance receipt and screenshots record actual results rather than assuming these behaviors from CSS.

## Start a new investigation

Stop the viewer before switching modes:

```bash
python3 -m scripts.reviewer stop
python3 -m scripts.reviewer fullstack
```

This provisions isolated local PostgreSQL 55434, Keycloak 8090, API 8310 and website 3310 with generated private credentials. Sign in with an admitted synthetic account. Workspace and role determine available commands. Operators choose registered cases/configurations; users cannot submit arbitrary filesystem paths or URLs.

The default full-stack control plane leaves inference off. The documented `--with-inference` mode connects prepared local assets and a worker for a bounded live session. The new frozen strong-model study used the explicit CLI investigation runner, not a silently replaced web-worker default. Its captured score is not a promise that the default local model produces the same repairs.

Submission saves a stable command identity. The API commits a durable receipt before acknowledgement. A visible active investigation polls actual progress. Cancellation fences later writes; fork creates a new bounded attempt; replay reads captured steps without model/tool execution. Only an administrator can publish. Failed checks, uncertain dispatches and unavailable services remain explicit outcomes.

## Reproduce rather than infer from screenshots

- `python3 -m scripts.reviewer repair` reproduces the historical Django patch against 110 tests with one skip. Its recorded rebuilt-image provenance remains separate from newer cases.
- `python3 -m scripts.reproduce_training014 --output NEW_DIRECTORY --budget-root COUNTED_ROOT` reruns the learned-head fit from the packaged frozen embeddings. Review its documented dependency and output-root requirements. Exact selected bytes were reproduced in the recorded Mac environment; other environments must report their actual comparison.
- `python3 -m scripts.reproduce_repair014 --runtime NEW_PRIVATE_DIRECTORY --hidden-records ORIGINAL_LITE_ROWS_JSON --budget-root COUNTED_ROOT` independently rechecks the published held-out Django14752 patch. The original dataset must be supplied separately; reference fixes and hidden tests are never published by this command. Its hashes must match the frozen qualification. The exact prepared verification image is required, with no silent environment substitution.

The external Lite rows use the original dataset fields, including instance_id, repo, base_commit, problem_statement, patch, test_patch, FAIL_TO_PASS and PASS_TO_PASS. Obtain them from the official SWE-bench Lite dataset at the revision recorded in the qualification provenance. Keep that JSON outside agent source tools and public evidence. Source acquisition is restricted to the pinned upstream repository and commit.

No reproduction command sends a new model request. Prepared inference and further training are separate actions. Complete receipts and the current acceptance matrix are in evidence/measurement014; design decisions are in DECISIONS.md. The coding-model adapter follow-up is planned in docs/CODING_ADAPTER_014.md and has not been run.
