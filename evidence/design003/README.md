# Design003: copy and interface refinement

2026-10-11. Addresses the supplied screenshots of the homepage metadata banner and guarantee cards.

Replaced dense monospace guarantee cards and bracketed codes with sentence-case definition lists. Simplified homepage copy, headings and internal action labels across the main pages. Introduced a shared presentation formatter while retaining raw command values, access roles, identifiers and downloaded evidence. Switched the actual body font to the already bundled DM Sans, with Instrument Serif display emphasis. Muted semantic colors, removed decorative card tilt and shadows, and made status chips compact. Fixed mobile word joining at a hidden line break and corrected the footer guarantee anchor.

Validation: production build, ESLint and TypeScript pass. Browser checks cover the homepage at 1440px and 390px; engineering, evidence, model runs, workbench and docs have no page overflow at 390px. The guarantee body renders at 15px. Report statuses render as 27px-high chips. Context switching, report disclosure and the candidate-failure filter work; the filter retains 29 of 32 rows. Mathematical method text preserves the signed range. Screenshots and compact browser observations are included.

The isolated build was initially placed in a new generated directory that ESLint treated as source. That temporary output was removed; the final build uses the existing ignored `.next-build` convention, and the final lint receipt is clean.

This pass changes frontend presentation and writing. Backend functionality was not retested. Build002 evidence is preserved as a historical snapshot; its source fingerprints predate this pass. This manifest records local file hashes for review, not immutable or externally attested history.
