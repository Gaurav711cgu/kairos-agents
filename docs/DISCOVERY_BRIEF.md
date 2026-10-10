# Discovery brief — hypotheses for build001

**User hypothesis:** a developer changing an agent context policy needs to diagnose a wrong business decision and determine whether a proposed repair addresses it. No customer interview has validated this hypothesis yet.

**Decision:** identify missing evidence, inspect the independent expected outcome, run a controlled change and retain its parent record.

**Current workflow hypothesis:** developers compare prompts, console logs and final answers manually; logs may lack exact context inclusion decisions. This is a hypothesis, not a measured market finding.

**First task:** investigate a labeled synthetic order with a prior-compensation exception. Compact context deliberately omits it; preserve retains it. No actual customer refund is issued.

**Success for the next user study:** an unfamiliar developer locates the omitted exception, explains the incorrect480cent proposal, creates a preserve-context comparison, and finds its independent grade and lineage without author assistance. Record correctness, time, blockers and task familiarity; counterbalance comparable tasks where possible.

**Failure costs to test:** repeated manual investigation, incorrect policy proposals and uncertainty about repair effectiveness. No financial loss or productivity savings have been measured.

**Loop-value question:** does this task need a multi-step agent at all? Compare a simple structured model call plus deterministic arithmetic and grading before adding orchestration. Current reference runner does not answer that question.
