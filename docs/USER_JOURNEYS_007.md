# User actions and observed results

The website explains the first path at `/how-it-works`. These are automated browser journeys, not outside-user adoption. The recorded, fault-fixture and actual-OIDC scopes stay separate.

| Person action | Observed result | Scope |
| --- | --- | --- |
| Start with a saved case, open source/patch/checks, compare and download | Inspectable evidence and original downloads; keyboard and 390px layouts passed | Genuine public captures |
| Sign in, queue a registered case and inspect progress | Durable queued receipt with zero model calls; inference remains off | Real OIDC/PostgreSQL |
| Cancel, fork, replay, publish and download | Cancelled/fresh-child states, zero-execution playback, admin publication and verified download | Real OIDC/PostgreSQL |
| Repeat create/fork with same identity; send a conflicting body | Same record for identical command; HTTP 409 for conflicting payload | Real authenticated API |
| Use viewer or different tenant | UI/server mutation denial; other tenant records/progress/downloads/cursors inaccessible | Real OIDC/PostgreSQL |
| Change selection during a delayed read; reload after lost acknowledgement | Newer selection remains; original create/fork identity survives reload | Isolated fault fixture |
| Follow active progress through errors and completion | Visible 2 s polling; 30 s error backoff; navigation/terminal state stops reads | Isolated fault fixture |
| Request missing/corrupt/unavailable evidence | Explicit errors; no substitute records or successful-looking fallback | Browser plus package regressions |
| Obtain a successful fresh repair | **Not achieved: baseline 0/5, loop 0/5.** One previously exposed development repair is separate | Frozen study007 |
| Use the optional stronger free API model | No proposal captured: corrected request returned HTTP 503 during high demand. Unknown dispatch was not resent | Separate development pilot |

## Every browser journey

| Phase | Journey | Result |
| --- | --- | --- |
| recorded-browser | recorded repair exposes genuine patch, verifier evidence and keyboard context | Passed |
| recorded-browser | frozen comparison retains zero repairs, costs and incomplete timing | Passed |
| recorded-browser | recorded mode closes private commands and never simulates login | Passed |
| recorded-browser | 390px evidence, capacity history and unavailable records remain readable | Passed |
| recorded-browser | follow-up keeps fresh failures, paired development evidence and original bytes visible | Passed |
| recorded-browser | current documentation uses the reviewer entry point and states verification limits | Passed |
| recorded-browser | first-time reviewer follows the interaction path and sees an earned outcome | Passed |
| recorded-browser | current study exposes every fresh result and keeps development comparisons separate | Passed |
| fixture-browser | recorded public evidence, comparison, diff and downloads need no login | Passed |
| fixture-browser | public evidence and capacity remain readable at 390px | Passed |
| fixture-browser | public missing records show an explicit unavailable state | Passed |
| fixture-browser | frozen build004 compares all three strategies and shows measured study cost | Passed |
| fixture-browser | late detail response cannot overwrite a newer selection | Passed |
| fixture-browser | uncertain create keeps the command identity across reload | Passed |
| fixture-browser | uncertain fork keeps its identity across reload | Passed |
| fixture-browser | viewer controls, evidence download and keyboard work at 390px | Passed |
| fixture-browser | visible progress refreshes evidence and stops at a terminal state | Passed |
| fixture-browser | cancel, publication and replay show captured evidence without execution | Passed |
| fixture-browser | poll errors back off for 30 seconds and navigation cancels reads | Passed |
| fullstack-browser | fresh real OIDC supports queue, cancel, fork, replay, publication, download and logout | Passed |
| fullstack-browser | real session preserves command identity, rejects conflicts and paginates without duplicates | Passed |
| fullstack-browser | real viewer membership denies mutations in UI and server | Passed |
| fullstack-browser | real operator cannot access another tenant record, progress, downloads or cursor | Passed |

Receipts: `evidence/build007/checks/recorded-browser.json`, `fixture-browser.json`, `fullstack-browser.json`, `fullstack-acceptance.json` and `clean-acceptance.json`. Separate clean installation repeats 19 recorded/fixture journeys with no Docker or database. Full-stack backend: 393 passed/six opt-in skips. Clean recorded-only backend: 277 passed/122 environment/opt-in skips. These counts are separate invocations, not one combined run.

The original Django10914 saved model patch reproduced 110 tests with one upstream skip in a fresh disposable environment. Newer Django11066 development evidence has four captured tests. Neither result establishes general repair competence.
