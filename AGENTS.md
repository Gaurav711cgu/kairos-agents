# Project instructions

Use `caveman:caveman` for user-facing responses by default. Read `/Users/gauravkumarnayak/.codex/plugins/cache/caveman/caveman/3.2.0/skills/caveman/SKILL.md` when needed. Keep responses concise, clear and technically complete; preserve every qualifier and negative. Use normal English in persisted code, comments and documentation. Switch style when the user explicitly requests it.

Read `BRAIN.md` first when continuing Kairos work. It points to the current release and preserved evidence. Do not overwrite historical source, receipts, case configurations or image tags. Do not print ignored credentials. Model outcomes and engineering checks must remain separately reported.

# GRAVITAS Reliability Kernel (Default)

Use Gravitas (`skills/gravitas`) as the default reliability runtime for all engineering tasks:
1. Ground before mutating: Read target, callers, and tests before editing. Never act on assumed state.
2. Stay in declared scope: Writes stay strictly inside allowed task scope.
3. Completion needs fresh evidence: A criterion is done only when executed validator tests pass after the last edit. Stale evidence and self-review never count.
4. Never exact-retry a failure: Change diagnosis, context, or strategy on failure.
5. Satisfy task contract: Required criteria and executable checks gate completion.
6. Report what happened: Mark uncertain or unverifiable claims explicitly. Verify with proof.

