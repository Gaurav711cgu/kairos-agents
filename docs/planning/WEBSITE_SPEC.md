# Website and workbench specification

Status: design and content plan, not a built or validated website. The target is a distinctive, populated developer product with an immediate recruiter entry point.

## W01 — First visit and product story

Primary visitor question: “What hard problem did this engineer solve, and can I inspect the proof?”

Proposed headline: **Find the step that changed the outcome.**

Supporting copy: “Inspect an agent failure, compare the context it received, and test a repair in an isolated run.”

Primary action: **Inspect an incident.** Secondary action: **Read the engineering case study.** GitHub remains visible in navigation. Visitors can understand the product without signing up, running a terminal, supplying an API key, or watching a long video.

The opening interaction uses a sanitized recording from a real controlled execution. “Recorded run,” scenario provenance, and execution date are visible. The feature never simulates live generation or claims that an animation is a new experiment.

## W02 — Visual direction

Concept: **editorial engineering instrument**. Combine the reading quality of a technical journal with the precision of a professional debugging tool.

- Warm paper base `#F5F2EB`, deep ink `#172621`, forest accent `#174C3C`, and restrained burnt amber `#934113`. White/near-white panels provide reading contrast.
- Use a narrow navigation rail and strong alignment lines, varied column widths, a large left-aligned headline, and one substantial incident interaction. Avoid repeating an identical card shape for every section.
- Use a restrained sans family for prose/UI and monospace for event identifiers, request fragments, and timings. System fonts are acceptable initially; any custom font needs licensed, subsetted, self-hosted files and measured loading cost.
- Type scale and spacing come from tokens. Approximate desktop headline 64–80 px, body 17–18 px, interface text 14–16 px; adapt with clamps and reading-width constraints. Smaller metadata must remain readable.
- Use thin rules, limited corner radii, and shallow surfaces. Show hierarchy through composition, text, and information density rather than excessive decoration.
- Reserve forest for selection/confirmed states and amber for attention. Failure, pending, unsupported, and inconclusive require text/icon labels as well as color. Check every actual foreground/background pair for contrast.
- Motion explains transitions: selected event, context addition/removal, fork lineage, and result arrival. Keep ordinary transitions short, respect reduced-motion preferences, and preserve reading position.

Excluded by user preference: purple/blue glow, gradient blobs, generic robot art, infinite logo marquees, fake terminal typing, decorative node networks, glass-card grids, animated fake metrics, universal pill badges, and “revolutionize your workflow” copy. Do not replace them with another stock SaaS template.

Distinctiveness comes from art direction, incident content, composition, and interaction. “Elite” remains a design goal until visual and user review support it.

## W03 — Information architecture

| Route | Purpose | Required meaningful content |
|---|---|---|
| `/` | Explain and demonstrate value | featured incident, interactive context moment, engineering evidence, next action |
| `/incidents` | Browse real controlled case studies | failure, healthy control, recovery case; each labeled by provenance |
| `/incidents/:slug` | Follow one investigation | task, initial result, relevant events, intervention, actual outcome, limitations |
| `/engineering` | Establish SDE reasoning | architecture, transaction/effect boundary, runner and storage tradeoffs |
| `/engineering/:slug` | Deep technical case study | problem, rejected options, implementation evidence, measured limitation |
| `/evidence` | Inspect claims | result manifests, raw artifacts, methods, source revision, dates |
| `/docs` | Reproduce and integrate | setup, API contracts, guarantees, limits, runbooks |
| `/app/projects/:id` | Work on private projects | scoped runs, filtering, actionable errors and genuine empty state |
| `/app/runs/:id` | Investigate run | timeline, context, receipts, provenance, fork action |
| `/app/experiments/:id` | Assess change | task/trial counts, paired results, failures, uncertainty, decision rationale |

These are route designs, not claims of implemented features. Publish pages only when their contents exist; an unavailable case study should not masquerade as complete.

## W04 — Homepage composition

1. **Opening scene:** wordmark/navigation; asymmetrical headline and short explanation beside a wide incident canvas. The canvas shows task context, selected event, and a concise evidence-backed finding.
2. **Interactive incident moment:** one clear control advances among original context, omitted evidence, and forked context. The selected comparison remains inspectable as text. Separate observed facts from the author's interpretation.
3. **Incident index:** editorial rows for the featured failure, a recovery case, and a healthy/control case. Include task category, what failed, execution mode, and actual evidence availability.
4. **Engineering argument:** one annotated architecture diagram plus short explanation of the durability/effect boundary. Link to an ADR and corresponding test artifact.
5. **Release evidence:** show one actual report with primary outcome, interval, hard-check status, and pass/fail/inconclusive rationale. When report does not yet exist, omit this public claim rather than inventing values.
6. **Reproduce and inspect:** setup link, repo, methodology, concise limitations, author ownership, and current project status.

Do not place a wall of KPI cards above the product. Never use customer logos, endorsements, uptime, scale, or adoption numbers without evidence and permission.

## W05 — Incident workbench

Desktop composition: narrow event navigation, substantial context/detail pane, and a secondary outcome/provenance pane. Side panels can collapse. The current task, run mode, and selected step remain visible.

Timeline capabilities:

- Event-type/search filters, stable sequence ordering, deep links, keyboard navigation, and focus-safe selection.
- Cursor pagination and virtualization for long traces; fetch large payloads on demand.
- Event labels explain the action: “Context compacted,” “Adjustment proposed,” “Receipt reconciled.” Raw JSON remains available as secondary detail.
- Stream connection and data freshness are explicit. New events never steal focus or force scrolling when the user is reading history.

Context comparison:

- Show added, removed, retained, and summarized blocks, with source evidence links and token-accounting provenance.
- Include readable side-by-side and inline/text modes. Indicate truncation and allow deliberate expansion.
- Distinguish exact captured request bytes from a human-readable rendering. A semantic summary is not an exact diff.
- “First observed divergence” stays an observation; causal claims require experimental evidence.

Fork composer:

- Start from selected checkpoint; explain parent preservation.
- Edit one primary factor, show explicit patch, frozen/live scenario state, enabled tools, budget estimate, and approval status.
- Validate locally for responsiveness and server-side for authority. Show unsupported checkpoints before submission.
- After submission, open authoritative run status. Do not optimistically display success or automatically retry an unknown effect.

## W06 — Evaluation report interaction

Lead with the decision and its reason. Display baseline/candidate configuration, source digest, task-set and grader versions, distinct task count, trial count, and excluded/failed infrastructure runs.

Use a paired-result plot/table that exposes task-level gains and regressions. Show effect intervals with margin/reference lines. Give cost and latency their own units and scope. An inconclusive result gets a complete explanation and a specific next experiment; it never looks like a passed check.

Provide raw-result and reproduction links next to claims. Include task-family breakdowns and representative failures. Charts must have table/text equivalents, keyboard access where interactive, and labels that remain readable on mobile.

## W07 — Populated content without fictional success

Initial public content set:

- One real observed model/context failure, selected after P00/P03. Do not force the model to produce a predetermined failure story.
- One deterministic recovery experiment with a real sandbox commit and intentionally lost response.
- One healthy/control run showing that concurrent or long execution is not inherently a failure.
- One independent evaluation report; its actual result may be failure or inconclusive.
- Engineering articles on commit acknowledgement, effect reconciliation, and statistical decision limits.
- A “what this version guarantees” page and a reproducible setup guide.

Controlled fault injection is valid evidence when labeled. Stored recordings are valid product content when provenance is preserved. Fabricated model answers or randomized success metrics are not.

Each case uses: user task; environment; observed failure; selected evidence; hypothesis; intervention; measured outcome; limits; reproduction. Use actual application screenshots, not generated pictures pretending to be implemented screens.

## W08 — Frontend depth and implementation discipline

Use semantic components and clear domain state. Keep server state separate from transient view state. Generate API types from the backend contract; validate untrusted runtime payloads. URL state should encode shareable selection/filter/comparison, excluding private payloads and secrets.

Use a maintained virtualization library instead of inventing scrolling infrastructure. [TanStack Virtual](https://tanstack.com/virtual/latest/docs/introduction) is one candidate. Virtualized content still needs focus management, total-row context, and accessible reading alternatives.

Implement explicit initial/loading/empty/partial/error/unauthorized/stale/disconnected/unsupported states. Reserve layout space to prevent jumps. Avoid displaying stale private content after logout or membership change.

Keep expensive diff computation out of the critical interaction path; use bounded work, cancellation, lazy loading, and worker computation only when profiling warrants it. Export and search must cover the declared full dataset rather than silently only loaded rows.

## W09 — Quality gates

- Review at 390, 768, and 1440 px, plus zoom/text enlargement. Mobile uses stacked inspection and full-screen comparison, not a scaled-down desktop screenshot.
- Complete core journey with keyboard, visible focus, and reduced motion. No hover-only explanation or drag-only operation.
- Target WCAG 2.2 AA for the delivered scope, with automated checks plus manual focus, naming, reading order, and contrast review. Do not claim compliance from an automated score alone. [W3C reference](https://www.w3.org/WAI/WCAG22/quickref/).
- Target Core Web Vitals of LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 at the 75th percentile when sufficient real field data exists. Before that, report defined lab conditions and browser interaction measurements separately. Lighthouse alone does not measure field INP. [Web Vitals](https://web.dev/articles/vitals).
- Initial stress fixture: one run with 10,000 events, documented payload distribution, bounded loaded pages, and reproducible scroll/filter/diff tests. This is a UI test workload, not a claim of production users or capacity.
- Browser tests cover double submission, stale approval, API failure, stream reconnect, missing evidence, and mobile context comparison. Collect failure traces and selected visual snapshots.
- Every public claim links to evidence or is explicitly marked as planned. All visible links/buttons work. Public content remains useful when the model provider is down.

## W10 — Recruiter walkthrough

Suggested short visit: understand the problem; inspect the incident; compare the context; open an engineering decision; inspect the proof; visit the repository.

Suggested technical deep dive: transaction boundary; crash/effect reconciliation; isolation canary; context experiment; independent release gate; frontend profile and accessible interaction.

Measure whether users can complete these visits. Do not manufacture a target recruiter engagement rate. A concise narrated recording supports the interactive site; it does not replace it.
