# Skill routing and read-only skill check

Date: 2026-10-11. Scope: selected SKILL.md contents only. No installed skills were modified.

## Routing

Primary: `@app-builder`. Build the saved Kairos SDE/full-stack specification in the existing project linked as `resume/new-karos`.

Secondary: `@frontend-design` for the recruiter-facing incident experience; `@software-architecture` for domain/transport/persistence boundaries and library-first choices.

Ready-to-use invocation: `@app-builder implement Kairos build 001 from PLAN.md, using @frontend-design and @software-architecture, with actual persisted controlled runs and explicit evidence limits.`

The user explicitly authorized choosing/loading skills and starting implementation. Area, specificity, stack, and autonomy were already supplied in the conversation and saved brain; repeating the skill-router interview would not resolve missing information. Its recommendation-only limitation is superseded by the user's explicit instruction to load the selected skills.

## Method

Manual application of the supplied SkillCheck categories and penalty rubric, with the [Agent Skills specification](https://agentskills.io/specification) checked for frontmatter/name/description constraints. This is a heuristic content review, not execution of a complete 31-rule official validator. Full rule IDs are not supplied by the local skill; category IDs are used where an exact ID is unavailable. Grades below use this review's declared threshold: >=90 Excellent, >=75 Good, >=50 Needs Work, otherwise Poor.

## app-builder

Score: 95/100 (Excellent). One warning, no critical issue found in reviewed categories.

- **4.x — semantic consistency, line 28:** heading advertises 13 templates while its table lists 12. Fix: align advertised count with table, or remove the count. Penalty: -5.

Core fields are readable, name matches directory, description states application-building purpose, and body provides selective reading, examples, and limitations. Supplementary scaffolding describes 2025 defaults; these are guidance to revalidate, not current dependency versions. The saved Kairos architecture overrides its generic Prisma/custom-auth template.

## frontend-design

Score: 90/100 (Excellent). Two warnings, no critical issue found in reviewed categories.

- **1.2-desc-when, line 3:** description states a role rather than clear task/activation conditions. Fix: describe designing/implementing distinctive web interfaces and when to apply it. Penalty: -5.
- **4.x — semantic contradiction, lines 51–67:** four 1–5 positive dimensions minus a 1–5 risk yield a possible range of -1 to 19, not the documented -5 to 15. Fix: correct range/formula/interpretation together. Penalty: -5.

The body provides concrete implementation guidance, output structure, examples of design direction, and a checklist. Subjective design scores do not establish measured usability, accessibility, production readiness, or recruiter response.

## software-architecture

Score: 95/100 (Excellent). One warning, no critical issue found in reviewed categories.

- **4.x — contextual ambiguity, code-style section:** “Use arrow functions ... when possible” is not language-scoped, although the skill covers software broadly. Fix: scope it to JavaScript/TypeScript and follow idiomatic Python for Python modules. Penalty: -5.

The description includes development triggers and the body gives concrete boundaries and dependency-first guidance. Numerical file/function limits are heuristics; cohesive domain logic and meaningful tests remain the review standard.

## Execution consequences

The app-builder agent-coordination guide explicitly requests specialist agent work, authorizing backend/frontend delegation. Its root-plan checkpoint was satisfied by saving and verifying `/Users/gauravkumarnayak/Desktop/new-karos/PLAN.md` before delegation. Existing user context supplies answers to its generic questioning gate; no additional approval was inferred from skill wording.
