# Context and scope

## User requirements

The primary target is SDE/full-stack roles. The project should demonstrate system design, AI, backend architecture, debugging, frontend, databases/storage, context management, harness behavior, and loop control. AI and FDE role coverage must be real rather than a collection of labels.

The user requested detailed reasoning for decisions, setbacks, errors, and likely reviewer objections. They also requested persistent Markdown memory to avoid rereading large files. The website must be populated, polished, recruiter-friendly, and visually distinctive, without generic AI-site patterns or a terminal-only presentation.

The user requested caveman voice in chat. Persisted technical documentation uses clear conventional prose so another engineer can review it.

## Inputs and evidence boundaries

- The supplied architectural specification proposed a Python harness, Go ingestion, PostgreSQL, object storage, replay/fork workers, statistical gates, and a Next.js interface.
- The supplied verdict recommended a restart and described several projects as highly qualified. Those labels are not independent execution evidence.
- Prior Kairos audit (earlier local review, outside this project repository) recorded simulated commits/evaluation results, replay-isolation defects, and causal scheduling problems in the earlier HTTP-replay project. That was a historical read-only audit, not a fresh runtime result.
- Flagship review (earlier local review, outside this project repository) assessed the agent-focused redesign. This planning package gives the more detailed SDE/full-stack execution plan and website treatment.
- No application source was edited or tested as part of this planning task. References to proposed code folders, tests, commands, or routes describe future implementation.

## Facts versus assumptions

Facts: existing frameworks already provide checkpointing, tracing, forks, and evaluation features; the project needs a narrower value proposition. Current official job examples emphasize end-to-end implementation, fundamentals, reliability, data models, user experience, and stakeholder collaboration. Sources are in SOURCES.md.

Assumptions: a solo builder; no fixed deadline, operating budget, language mandate, cloud vendor, domain, or specific target job descriptions have been supplied. The plan optimizes broad SDE/full-stack capability rather than a particular employer's screening rubric.

Working first user: a developer shipping changes to a tool-using agent. Their question is whether a proposed change fixes a real failure while preserving other workflows.

Working first domain: support/order policy decisions. Ground truth is supplied by versioned scenario records and independent business assertions. A local adjustment API provides a real effect without using real money.

## Product boundaries

Included: organizations/projects, permissioned runs, incident inspection, exact context manifests, isolated playback/forks, approval and effect receipts, controlled evaluations, accessible website/workbench, reproducible delivery, and recovery evidence.

Deferred: general-purpose agent framework, autonomous code repair, production payment integrations, arbitrary internet tools, multi-agent orchestration, custom orchestration cluster, high-throughput Go ingest, lock-free queues, broad connector marketplace, billing system, and multi-region failover.

A deferment is a scope decision, not a claim that the problem is solved. Revisit triggers appear in DECISIONS.md.

## Interpretation limits

SDE depth comes from explainable code, correctness, operational behavior, and tradeoffs. Frontend depth comes from interaction, state, performance, accessibility, and error handling. Applied AI depth comes from model-specific failure analysis and controlled evaluation. Model research requires separate research contributions. FDE depth requires actual discovery and adoption evidence.

No project guarantees recruiter attention, employment, experience equivalence, or compensation. Job examples are capability references, not eligibility promises.

## Build 001 execution context — 2026-10-11

The user explicitly authorized starting implementation and selecting/loading skills. app-builder was primary; frontend-design and software-architecture were supporting skills. The existing `resume/new-karos` symlink led to the actual Desktop/new-karos repository. It was reused rather than replaced. Skill-check was a read-only heuristic review, recorded separately; installed skills were not modified.

The selected app-builder coordination guide explicitly called for specialist work. A root PLAN.md was saved and verified before backend/frontend delegation; a read-only specialist review followed. Root performed integration and browser checks. Historical README/architecture claims were archived and replaced with statements matching the new execution path.

The current bounded reference slice narrows the larger planned scope. It does not complete P00/P01, qualify a model, or demonstrate customer adoption. Its separate cached-model probe failed4/4 strict development cases, preserved rather than presented as success.
