# Primary-source reference index

Checked: 2026-10-11. These sources support specific capabilities and techniques, not predictions about recruiter response. Reverify when selecting versions, applying to a role, or relying on a time-sensitive behavior.

## Role examples

- [Amazon SDE, Distributed Services](https://www.amazon.jobs/en/jobs/10562446/software-development-engineer-distributed-services): design, fundamentals, scalable implementation, testing, operational practices, and communication. This is an experienced-role example, not a graduate eligibility guide.
- [OpenAI Full Stack Software Engineer, Agent Enablement](https://openai.com/careers/full-stack-software-engineer-agent-enablement-san-francisco/): frontend/backend/APIs/data models/product design, agent observation/control, identity/permissions, and user feedback.
- [OpenAI Forward Deployed Software Engineer, NYC](https://openai.com/careers/forward-deployed-software-engineer-nyc-new-york-city/): customer discovery, iterative full-stack delivery, scoped prototypes/production work, and reusable abstractions. Its experience requirements cannot be replaced by this project.

These examples inform the capability mapping. No specific target job descriptions were provided by the user.

## Existing products and architecture

- [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers): checkpoint boundaries, persistence, fault recovery.
- [LangGraph time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel): replay and fork semantics, including later-node reexecution.
- [Langfuse evaluation](https://langfuse.com/docs/evaluation/overview): datasets, experiments, evaluators, CI gates. These are existing capabilities, not Kairos inventions.
- [Temporal activities](https://docs.temporal.io/activities): idempotency and retry responsibilities.
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html): concurrent transaction semantics. Read Committed alone does not serialize arbitrary read-check-write workflows.
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): policies and privileged-role caveats.
- [PostgreSQL PITR](https://www.postgresql.org/docs/current/continuous-archiving.html): base backup and WAL requirements.
- [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html): WORM/version/retention semantics.
- [GitHub secure workflow use](https://docs.github.com/en/actions/reference/security/secure-use): privileged workflow and untrusted-code hazards.

## AI evaluation and statistics

- [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): start simple and measure added complexity.
- [Anthropic: Demystifying agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): tasks/trials/graders, outcome scoring, isolation, and repeat variability.
- [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html): paired resampling and interval methods; experimental design remains the caller's responsibility.
- [statsmodels multiple tests](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html): adjustment of valid p-values, including Holm.

## Implementation and validation techniques

- [Hypothesis stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html): generated action sequences and invariants.
- [Toxiproxy](https://github.com/Shopify/toxiproxy): controlled network faults.
- [Testcontainers Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/): real disposable service dependencies in integration tests.
- [Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer): browser investigation artifacts.
- [TanStack Virtual](https://tanstack.com/virtual/latest/docs/introduction): long-list virtualization; accessibility remains application work.
- [k6 arrival-rate allocation](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/arrival-rate-vu-allocation/): offered load and dropped scheduling attempts.
- [Web Vitals](https://web.dev/articles/vitals): field percentile targets and lab limitations.
- [WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/): accessibility requirements for scoped manual/automated assessment.

## Research execution limits

The software-architecture, project-development, and caveman skills informed this work. Primary-source browsing was used. No model council, external Gemini research job, implementation benchmark, or runtime validation is claimed. Prior audit findings remain historical observations rather than newly reproduced defects.
