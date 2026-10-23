# Repair failure analysis and next development gate

## Observed evidence

The trained adapter verified0/20 repairs; base verified0/20. Adapter produced15 invalid patches versus12 for base. Accepted patches failed behavior or broke imports. Exact outputs, rejected ranges, syntax errors and independent test captures remain available.

The post-evaluation localization diagnostic found a reference target file in the supplied context for9/20 cases. All reference hunks, including their unchanged context, fit inside captured regions for2/20 cases. This is a conservative coverage diagnostic, not proof that those exact reference edits were the only possible repairs. It does establish a practical weakness: many prompts lack the files changed by the maintainer. The adapter cannot reliably compensate for unavailable source.

Training5 used two independently verified public training examples. Its2/2 training-case result establishes learning of those known tasks; it does not establish diverse repair competence. Increasing model size alone does not correct absent source, source-handle/range mistakes or limited supervision.

## Bounded corrective development, separate from this release

1. Improve issue-only localization on development cases: search identifiers and failing frames, retrieve whole functions, and measure relevant-source coverage before invoking the model. Preserve reference blindness at runtime. Compare existing AST retrieval with the already available retrieval pipeline rather than adding another index by default.
2. Use the existing source-bound validator as feedback in the bounded investigation loop. Return precise format/range/syntax rejection before spending a check slot. Keep original captures unchanged; do not silently repair generated code.
3. Increase diverse verified training coverage only if development evidence identifies a training benefit. Split by issue family and normalized patch targets before training. Validate protocol output and independent behavior, not training loss alone.
4. Freeze the next protocol/model on development data, then admit another project-excluded evaluation cohort. These20 cases are now exposed and cannot support a future untouched claim.

No corrective training, inference or new experiment was started. This report completes the frozen study, while explicitly retaining its failed effectiveness target. A new experiment requires a separate bounded scope; it does not block shipping the verified investigation infrastructure.
