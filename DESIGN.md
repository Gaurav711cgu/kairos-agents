# Kairos design and writing system

Updated 2026-10-11. Design003 replaces the earlier glowing telemetry treatment.

## Direction

Restrained editorial engineering. The site helps a reviewer inspect a real incident, follow a request through the system, and assess the evidence. Its visual anchor is the large asymmetric incident opener, paired with a working context comparison. Thin rules and clear type organize the supporting detail.

Design feasibility score: impact 4, context fit 5, implementation 5, performance 5, consistency risk 4; DFII 15. This direction uses existing local fonts and native layout without a new dependency.

## Typography and color

DM Sans is the body, navigation and interface font. Instrument Serif supplies italic display emphasis. Monospace is reserved for identifiers, code and raw records. Descriptions use 15px text with generous line spacing; technical metadata has a 12px floor. Labels use sentence case and restrained tracking.

Keep the matte dark canvas, neutral panels and thin borders. Muted sage indicates passing checks, sand indicates attention, and dusty rose indicates failures. Status text always states the outcome. Primary buttons use neutral light fill; secondary actions use dark fill or an underline. No glow, saturated signal colors, pointer tilt, or decorative status dots.

## Writing rules

- Use plain, specific English. Name the action, result or limitation.
- Use sentence case for headings, labels, statuses and buttons. Preserve acronyms such as API, JSON and OIDC.
- Prefer “Saved before confirmation” to “Durable Write Before ACK.”
- Prefer “Current limits” to “Honest non-guarantees.”
- Remove bracketed guarantee codes, theatrical slogans, and repeated arrow suffixes.
- Keep technical implementation detail in engineering and docs. Explain the behavior on the homepage.
- Human-readable enum labels belong in `dashboard/lib/display.ts`. Never rewrite stored identifiers, authorization values, command payloads, downloads or raw evidence for presentation.
- Keep evidence limits beside claims. Local drills do not prove hosted operations or adoption. Captured model responses do not establish qualification.

## Components and verification

Guarantees use semantic definition lists with readable descriptions and separators. Cards stay still. Buttons and status chips share typography, spacing and quiet borders. Context controls retain selected state and keyboard behavior. Public API outages remain visible.

Verify at desktop and 390px widths. Check word boundaries where responsive line breaks are hidden, body readability, horizontal overflow, status capitalization, context switching and report expansion. Design003 evidence lives in `evidence/design003/`. Build002 evidence remains a historical snapshot.


## Build003 — A source case notebook

Lead with the actual source defect, candidate diff and independent verdict. Editorial case titles use sentence case; raw issues, identifiers, requests and downloads remain unchanged. Show baseline and loop cost beside outcomes. Frozen comparison membership is explicit and does not absorb later interactive records. The ledger includes rejected patches and earlier development versions.

Use readable semantic rows, quiet borders, ordinary buttons and muted state text. No animated status glow or decorative badge wall. Timeline selection persists in the URL; code regions scroll by keyboard. Public reading requires no login or live inference. Private session identity, replay and sign-out controls belong in the active workbench, outside collapsed historical workflows. Screenshots and browser observations are retained under evidence/build003.

### Readable investigation evidence

Use paired before/after source panels with original line numbers and muted change backgrounds. Stack the panels at narrow widths and keep long code scrolling inside its region. Present check status, actual test counts, skips and elapsed time before logs. Context steps show budgets, source excerpts and action labels. Raw requests/results, full diff context and model-authored summaries remain available through native disclosures. Presentation must not invent patch intent or replace stored evidence. Final desktop/mobile/failure screenshots and browser observations are recorded under evidence/build003.

## Build004 presentation choices

Private investigations use the same evidence inspector as public records. The timeline explains source reads, whole-line edit validation, immediate checks, context omissions and independent drafts before showing exact JSON in optional disclosures. Before/after code and unified diffs use muted addition/removal colors and keyboard-scrollable regions. Comparison cards expose actual calls, tokens and elapsed time; only a frozen cohort with matching task digest and model profile is paired. Capacity presents failed stages alongside successful latencies, with explicit scope and downloadable corrected measurements.

## Build004 final capacity presentation

Show the complete follow-up and original failure together. Use sentence-case headings, muted colors, explicit client/duration labels and acknowledgement/read/error measurements. Link downloadable aggregates. A passed local target must never hide the failed soak or imply production-scale capacity. Desktop and 390px production checks include this page; viewport screenshots are preserved.

## Build005: inspection before infrastructure

Preserve muted typography, quiet controls and readable source/check panels. Lead reviewers through the problem, proposed change, independent checks, engineering decisions and evidence. The recorded banner and record-level label state the view's authority without presenting saved activity as live progress. Recorded mode removes sign-in and execution controls while keeping inspection available without inference.

Original artifacts and raw responses remain available through disclosures and downloads. Highlighting and ordinary labels explain their structure without rewriting captured evidence. Show zero-repair results, incomplete timing and additional inference cost beside the earlier successful case. Missing or corrupt evidence receives an unavailable state rather than a substitute example.

Recorded acceptance covers keyboard inspection, comparisons, genuine downloads, private closure and 390px layouts. Actual OIDC journeys cover live actions separately. The source website and built image must show the same mode and evidence authority. Existing fixture journeys also pass after delivery changes.
