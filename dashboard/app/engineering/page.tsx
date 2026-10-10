import Link from "next/link";
export const metadata = { title: "Engineering decisions" };
export default function Engineering() {
  return (
    <div className="page-shell reading-page">
      <div className="page-heading">
        <span className="eyebrow">ENGINEERING / BUILD 001</span>
        <h1>
          The boundary
          <br />
          <em>is the design.</em>
        </h1>
        <p>
          An incident interface is useful only if the evidence beneath it
          survives failures and retains its meaning.
        </p>
      </div>
      <div className="article-layout">
        <aside className="article-index">
          <span className="eyebrow">IN THIS STUDY</span>
          <a href="#durability">01 Commit before response</a>
          <a href="#context">02 Context is evidence</a>
          <a href="#grading">03 Independent grading</a>
          <a href="#isolation">04 Honest isolation</a>
        </aside>
        <article className="prose">
          <section id="durability">
            <span className="eyebrow">01 / STORAGE CORRECTNESS</span>
            <h2>Commit before acknowledgement.</h2>
            <p>
              A memory buffer is fast, but an accepted request can disappear
              when its process dies. The initial implementation places the run,
              ordered events, and idempotency identity in one PostgreSQL
              transaction. A successful response follows the commit.
            </p>
            <div className="engineering-flow">
              <span>Authorize</span>
              <b>→</b>
              <span>Execute</span>
              <b>→</b>
              <strong>Commit</strong>
              <b>→</b>
              <span>Respond</span>
            </div>
            <h3>Why this tradeoff</h3>
            <p>
              One transaction is easier to reason about than a second ingestion
              service, asynchronous spill queue, and cross-service
              acknowledgement protocol. Throughput is an open measurement, not a
              justification for extra infrastructure.
            </p>
            <h3>The failure boundary</h3>
            <p>
              A response lost after commit leaves the client uncertain. Retrying
              the same command identity with the same request retrieves the
              committed result. Reusing that identity with a different request
              must fail.
            </p>
          </section>
          <section id="context">
            <span className="eyebrow">02 / HARNESS OBSERVABILITY</span>
            <h2>Preserve what the runner received.</h2>
            <p>
              The late-order exception scenario has two context policies.
              Compact drops the exception block; preserve retains it. The
              resulting record includes source blocks, inclusion decisions,
              proposed output, and ordered events.
            </p>
            <p>
              This controlled runner deliberately makes the context dependency
              visible. It establishes the capture and investigation contract. It
              does not claim that a real language model made this mistake.
            </p>
            <Link className="text-link" href="/incidents">
              Open the context experiment ↗
            </Link>
          </section>
          <section id="grading">
            <span className="eyebrow">03 / EVALUATION BOUNDARY</span>
            <h2>The scorer gets its own evidence.</h2>
            <p>
              The grader reads the original scenario, including the exception,
              independently of the runner’s selected context. Turning context
              preservation on or off changes the execution, not the scoring
              truth.
            </p>
            <p>
              Per-run deterministic checks are useful regression evidence. They
              are not a statistical estimate of model performance. A future
              release gate requires representative task families, independent
              holdouts, an acceptable degradation margin, and an inconclusive
              outcome when evidence is insufficient.
            </p>
          </section>
          <section id="isolation">
            <span className="eyebrow">04 / AUTHORITY AND RECOVERY</span>
            <h2>Name the guarantee precisely.</h2>
            <p>
              Tenant identity comes from a configured server-side developer
              credential. Public routes expose sanitized controlled records.
              Public mutations are disabled; the local developer proxy is
              available only when explicitly enabled.
            </p>
            <p>
              A fork in this version is a fresh scenario execution with parent
              lineage. It does not resume arbitrary checkpoints. No external
              refund is issued. The event hash chain checks local record
              consistency; it does not make history immutable against a
              privileged administrator.
            </p>
            <aside className="scope-note">
              <strong>Still to prove</strong>
              <p>
                Managed identity, real model qualification, long-trace behavior,
                uncertain external effects, off-host recovery, hosted CI, and
                production deployment.
              </p>
            </aside>
          </section>
        </article>
      </div>
    </div>
  );
}
