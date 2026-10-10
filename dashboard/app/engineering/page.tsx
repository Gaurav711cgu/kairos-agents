import Link from "next/link";
import { GoIngestSimulator } from "@/components/GoIngestSimulator";
import { CryptoChainAudit } from "@/components/CryptoChainAudit";

export const metadata = { title: "Engineering decisions" };

export default function Engineering() {
  return (
    <div className="page-shell reading-page">
      <div className="page-heading">
        <span className="eyebrow">ENGINEERING ARCHITECTURE / HIGH-THROUGHPUT SYSTEMS</span>
        <h1>
          The boundary
          <br />
          <em>is the design.</em>
        </h1>
        <p>
          An incident interface is useful only if the evidence beneath it
          survives failures and retains cryptographic meaning.
        </p>
      </div>
      <div className="article-layout">
        <aside className="article-index">
          <span className="eyebrow">SYSTEM BLUEPRINT</span>
          <a href="#durability">01 Commit before response</a>
          <a href="#ingest-pipeline">02 Go Ingest &amp; Ring Buffer</a>
          <a href="#context">03 Context is evidence</a>
          <a href="#grading">04 Independent grading</a>
          <a href="#isolation">05 Cryptographic audit</a>
        </aside>
        <article className="prose">
          <section id="durability">
            <span className="eyebrow">01 / STORAGE CORRECTNESS</span>
            <h2>Commit before acknowledgement.</h2>
            <p>
              A memory buffer is fast, but an accepted request can disappear
              when its process dies. The initial implementation places the run,
              ordered events, and idempotency identity in one ACID transaction.
              A successful response follows the commit.
            </p>
            <div className="engineering-flow">
              <span>Authorize</span>
              <b>[NEXT]</b>
              <span>Execute</span>
              <b>[NEXT]</b>
              <strong>Commit</strong>
              <b>[NEXT]</b>
              <span>Respond</span>
            </div>
            <h3>Why this tradeoff</h3>
            <p>
              Short reference executions fit one transaction. Slow model calls
              use a durable intent ledger and fenced worker leases: claim and
              commit, call outside the transaction, then capture and grade. If a
              worker dies after dispatch without a captured response, the
              outcome is unknown rather than silently retried.
            </p>
          </section>

          <section id="ingest-pipeline" className="my-6">
            <span className="eyebrow">02 / HOT PATH INGESTION</span>
            <h2>Go Ingest Engine &amp; Bounded Ring Buffer</h2>
            <p className="mb-4">
              Telemetry ingest sits on the hot path. A Go service accepts batch events into a
              lock-free bounded ring buffer (10,000 slots) with drop counter tracking and single-transaction
              outbox staging.
            </p>
            <GoIngestSimulator />
          </section>

          <section id="context">
            <span className="eyebrow">03 / HARNESS OBSERVABILITY</span>
            <h2>Preserve what the runner received.</h2>
            <p>
              The late-order exception scenario has two context policies.
              Compact drops the exception block; preserve retains it. The
              resulting record includes source blocks, inclusion decisions,
              proposed output, and ordered events.
            </p>
            <p>
              The reference runner isolates the context dependency. Separate
              model jobs capture exact rendered requests and raw responses. The
              model classifies refund, zero or abstain; a deterministic tool
              calculates cents. Invalid schema and wrong policy choices remain
              failed records.
            </p>
            <Link className="text-link" href="/incidents">
              Open the context experiment [VIEW INCIDENTS]
            </Link>
          </section>

          <section id="grading">
            <span className="eyebrow">04 / EVALUATION BOUNDARY</span>
            <h2>The scorer gets its own evidence.</h2>
            <p>
              The grader reads the original scenario, including the exception,
              independently of the runner’s selected context. Turning context
              preservation on or off changes the execution, not the scoring
              truth.
            </p>
            <p>
              The release rule uses fixed paired task outcomes evaluated over 10,000 bootstrap
              resamples with Holm-Bonferroni Family-Wise Error Rate control. A candidate model
              exhibiting statistically significant degradation (upper CI bound &lt; 0) is automatically
              blocked from merging in CI.
            </p>
          </section>

          <section id="isolation">
            <span className="eyebrow">05 / CRYPTOGRAPHIC AUDIT &amp; TAMPER PROOFING</span>
            <h2>Verifiable SHA-256 Hash Chaining</h2>
            <p className="mb-4">
              Every event embeds the SHA-256 hash of its parent step, context snapshot, and emitted decision.
              Tampering with any event immediately breaks the mathematical chain downstream. Test this live
              in the audit workbench below:
            </p>
            <CryptoChainAudit />

            <aside className="scope-note mt-6">
              <strong>Formal Verification Bounds</strong>
              <p>
                Cryptographic hash verification guarantees local tampering detection. Paired bootstrap
                resampling establishes statistical non-inferiority across held-out benchmark tasks.
              </p>
            </aside>
          </section>
        </article>
      </div>
    </div>
  );
}
