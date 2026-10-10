import Link from "next/link";
import { getIncidents, getIncident } from "@/lib/kairos-api";
import { IncidentRows, ServiceError } from "@/components/IncidentRows";
import { ContextMoment } from "@/components/ContextMoment";
export const dynamic = "force-dynamic";
export default async function Home() {
  const result = await getIncidents();
  const records = result.data?.incidents ?? [];
  const caseFiles = records.filter((item) => item.parent_run_id === null);
  const featured =
    records.find(
      (item) =>
        item.policy === "compact" &&
        item.scenario_id === "late-order-exception",
    ) ?? records[0];
  const detail = featured ? await getIncident(featured.id) : null;
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow opening-label">
            <span className="live-dot" /> AGENT RELIABILITY / AN ENGINEERING
            STUDY
          </div>
          <h1>
            Find the step
            <br />
            that changed
            <br />
            <em>the outcome.</em>
          </h1>
          <p className="hero-deck">
            The answer looked right.
            <br />
            The evidence told a different story.
          </p>
          <p className="hero-description">
            Inspect captured context, follow the failure, and test a repair in
            an isolated run.
          </p>
          <div className="hero-actions">
            <Link
              className="button primary"
              href={featured ? "/incidents/" + featured.id : "/incidents"}
            >
              Inspect an incident <span aria-hidden="true">↗</span>
            </Link>
            <Link className="text-link" href="/engineering">
              How it works →
            </Link>
          </div>
          <div className="hero-footnote">
            <span className="mono">01 / THE CONTEXT GAP</span>
            <p>
              Reference-policy executions.
              <br />
              No hidden model or invented results.
            </p>
          </div>
        </div>
        <div className="hero-instrument">
          {detail?.data ? (
            <ContextMoment incident={detail.data} />
          ) : (
            <ServiceError
              message={
                detail?.error ??
                result.error ??
                "No published executions yet. Seed a controlled run to begin."
              }
            />
          )}
        </div>
      </section>
      <section className="section index-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">THE CASE FILES</span>
            <h2>
              Failure is useful.
              <br />
              <em>If you can inspect it.</em>
            </h2>
          </div>
          <p>
            Recorded executions, their original evidence,
            <br />
            and the checks that judged the outcome.
          </p>
        </div>
        {result.error ? (
          <ServiceError message={result.error} />
        ) : records.length ? (
          <IncidentRows incidents={caseFiles.slice(0, 3)} />
        ) : (
          <p className="empty-state">No published executions yet.</p>
        )}
        <Link className="text-link all-link" href="/incidents">
          All incident records →
        </Link>
      </section>
      <section className="engineering-teaser section">
        <div>
          <span className="eyebrow">BEHIND THE INTERFACE</span>
          <h2>
            Trust begins
            <br />
            <em>at the boundary.</em>
          </h2>
          <p>
            A successful response follows the database commit. A fork keeps its
            parent untouched. A grader reads source evidence independently.
          </p>
          <Link className="text-link" href="/engineering">
            Explore the engineering decisions ↗
          </Link>
        </div>
        <div
          className="boundary-diagram"
          aria-label="Request passes authorization, executes policy, commits events in PostgreSQL, then responds"
        >
          <div>
            <span>01</span>
            <strong>Authorize</strong>
            <small>Server-derived tenant</small>
          </div>
          <div>
            <span>02</span>
            <strong>Execute & grade</strong>
            <small>Captured context + source truth</small>
          </div>
          <div className="commit-step">
            <span>03</span>
            <strong>Commit</strong>
            <small>Run + events + idempotency</small>
          </div>
          <div>
            <span>04</span>
            <strong>Acknowledge</strong>
            <small>Only after durable commit</small>
          </div>
        </div>
      </section>
      <section className="closing section">
        <span className="eyebrow">INSPECT THE WORK</span>
        <h2>
          Every claim needs
          <br />
          <em>somewhere to land.</em>
        </h2>
        <div>
          <Link href="/evidence">Execution evidence ↗</Link>
          <Link href="/docs">Reproduce locally ↗</Link>
        </div>
      </section>
    </>
  );
}
