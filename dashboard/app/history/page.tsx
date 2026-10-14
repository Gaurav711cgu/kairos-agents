import Link from "next/link";
import { getIncidents, getIncident } from "@/lib/kairos-api";
import { IncidentRows, ServiceError } from "@/components/IncidentRows";
import { ContextMoment } from "@/components/ContextMoment";

export const dynamic = "force-dynamic";

const guarantees = [
  {
    title: "Saved before confirmation",
    body: "The API commits reference runs before returning success. Model jobs receive a saved receipt before the API accepts the job.",
  },
  {
    title: "Retries identify the same request",
    body: "Request keys belong to a workspace and are tied to the command. Reusing a key with different content returns a conflict.",
  },
  {
    title: "Stored records can be checked",
    body: "Content hashes and event chains detect differences from the stored reference. Someone with permission to rewrite both data and hashes can bypass this check.",
  },
  {
    title: "Forks create separate runs",
    body: "A fork reruns the case with a new context policy and links to its parent. It does not resume from an arbitrary past step.",
  },
];
const limits = [
  {
    title: "Model quality is still unproven",
    body: "A captured response does not establish that a model is suitable for the task. Failed responses remain available for inspection.",
  },
  {
    title: "Effects stay in the sandbox",
    body: "Approvals and receipts cover a PostgreSQL sandbox adjustment. They do not guarantee exactly-once execution in other systems.",
  },
  {
    title: "Local checks are not production evidence",
    body: "Identity integration, restore drills and load tests run locally. Hosted operations and customer adoption remain unverified.",
  },
  {
    title: "Release results have a defined scope",
    body: "The statistical bound applies to the declared synthetic tasks. An inconclusive result cannot approve a release.",
  },
];

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
      <div className="site-meta">
        <span>Historical synthetic order-support cases</span>
        <span>
          {result.error
            ? "Records unavailable"
            : `${records.length} published runs`}
        </span>
      </div>
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow opening-label">
            Agent debugging and evaluation
          </div>
          <h1>
            Find the step <br />
            that changed
            <br />
            <em>the outcome.</em>
          </h1>
          <p className="hero-deck">
            A deterministic policy missed a synthetic refund exception.
            <br />
            See what it received and where it failed.
          </p>
          <p className="hero-description">
            Kairos records context, responses and independent checks. Inspect a
            failed run, change its context policy, then compare the results.
          </p>
          <div className="hero-actions">
            <Link
              className="button primary"
              href={featured ? "/incidents/" + featured.id : "/incidents"}
            >
              Inspect an incident
            </Link>
            <Link className="button dark" href="/workbench">
              Open workbench
            </Link>
            <Link className="text-link" href="/engineering">
              How it works
            </Link>
          </div>
          <div className="hero-footnote">
            <span className="eyebrow">About these runs</span>
            <p>
              Reference policies and a local Qwen model.
              <br />
              Synthetic cases, with failed results included.
            </p>
          </div>
        </div>
        <div className="hero-instrument">
          {detail?.data ? (
            <ContextMoment incident={detail.data} />
          ) : (
            <ServiceError
              message={
                detail?.error ?? result.error ?? "No published runs yet."
              }
            />
          )}
        </div>
      </section>
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Inside Kairos</span>
            <h2>
              From request
              <br />
              <em>to recorded result.</em>
            </h2>
          </div>
          <p>Three parts of the system, each with a defined responsibility.</p>
        </div>
        <div className="architecture-notes">
          <article>
            <span className="note-number">01</span>
            <h3>Durable jobs</h3>
            <p>
              PostgreSQL saves a job before it is accepted. Workers use leases
              to control execution. A dispatched call with no captured response
              stays unknown; it is never silently sent again.
            </p>
            <Link className="text-link" href="/engineering#workers">
              Worker recovery
            </Link>
          </article>
          <article>
            <span className="note-number">02</span>
            <h3>Captured context</h3>
            <p>
              Each record keeps the evidence selected for the request, the
              evidence omitted, and the raw response. Content hashes check
              stored files for consistency.
            </p>
            <Link className="text-link" href="/engineering#context">
              Context and storage
            </Link>
          </article>
          <article>
            <span className="note-number">03</span>
            <h3>Release checks</h3>
            <p>
              A paired Hoeffding bound compares outcomes across 1,024 synthetic
              holdout tasks using a 10-percentage-point margin. Failed
              invariants block release; uncertain results stay inconclusive.
            </p>
            <Link className="text-link" href="/reports">
              Evaluation reports
            </Link>
          </article>
        </div>
      </section>
      <section className="section index-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Published incidents</span>
            <h2>
              Inspect a failed run.
              <br />
              <em>Compare its repair.</em>
            </h2>
          </div>
          <p>Recorded context, decisions and independent checks.</p>
        </div>
        {result.error ? (
          <ServiceError message={result.error} />
        ) : records.length ? (
          <IncidentRows incidents={caseFiles.slice(0, 4)} />
        ) : (
          <p className="empty-state">No published runs yet.</p>
        )}
        <div className="section-links">
          <Link className="text-link" href="/incidents">
            All incidents
          </Link>
          <Link className="text-link" href="/executions">
            Model responses
          </Link>
        </div>
      </section>
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Review the project</span>
            <h2>
              Choose where
              <br />
              <em>to start.</em>
            </h2>
          </div>
          <p>
            Inspect one incident, read a model response, or review an
            evaluation.
          </p>
        </div>
        <div className="review-paths">
          {[
            {
              href: "/incidents",
              label: "Debugging",
              title: "Compare the context",
              body: "Switch between the captured request and full source. Follow the decision through its event timeline.",
              action: "Browse incidents",
            },
            {
              href: "/executions",
              label: "Model behavior",
              title: "Read the response",
              body: "Inspect Qwen requests, unmodified responses and failed checks. A completed call can still fail the task.",
              action: "Browse model runs",
            },
            {
              href: "/reports",
              label: "Evaluation",
              title: "Examine the comparison",
              body: "Review task pairs, sample sizes, statistical bounds and provider failures. Download the full report.",
              action: "Browse reports",
            },
          ].map((item) => (
            <Link key={item.href} href={item.href} className="review-path">
              <span className="eyebrow">{item.label}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
              <span className="text-link">{item.action}</span>
            </Link>
          ))}
        </div>
      </section>
      <section className="section" id="guarantees">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Guarantees and limits</span>
            <h2>
              What the system
              <br />
              <em>can guarantee.</em>
            </h2>
          </div>
          <p>These guarantees apply to the implemented local system.</p>
        </div>
        <div className="contract-columns">
          <div className="contract-panel">
            <h3>Implemented guarantees</h3>
            <dl>
              {guarantees.map((item) => (
                <div key={item.title}>
                  <dt>{item.title}</dt>
                  <dd>{item.body}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="contract-panel">
            <h3>Current limits</h3>
            <dl>
              {limits.map((item) => (
                <div key={item.title}>
                  <dt>{item.title}</dt>
                  <dd>{item.body}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>
      <section className="engineering-teaser section">
        <div>
          <span className="eyebrow">Engineering decisions</span>
          <h2>
            Save the record.
            <br />
            <em>Then respond.</em>
          </h2>
          <p>
            Requests pass authorization and validation before the database
            commits their records. The API confirms success after that commit.
          </p>
          <Link className="text-link" href="/engineering">
            Read the architecture
          </Link>
        </div>
        <div
          className="boundary-diagram"
          aria-label="Request passes authorization, executes policy, commits events in PostgreSQL, then responds"
        >
          <div>
            <span>01</span>
            <strong>Authorize</strong>
            <small>Server-derived workspace</small>
          </div>
          <div>
            <span>02</span>
            <strong>Execute and grade</strong>
            <small>Context and source evidence</small>
          </div>
          <div className="commit-step">
            <span>03</span>
            <strong>Commit</strong>
            <small>Run, events and request identity</small>
          </div>
          <div>
            <span>04</span>
            <strong>Confirm</strong>
            <small>After the database commit</small>
          </div>
        </div>
      </section>
      <section className="closing section">
        <span className="eyebrow">Explore further</span>
        <h2>
          Read the records.
          <br />
          <em>Run the project.</em>
        </h2>
        <div>
          <Link href="/evidence">Published evidence</Link>
          <Link href="/executions">Model responses</Link>
          <Link href="/reports">Release reports</Link>
          <Link href="/workbench">Workbench</Link>
          <Link href="/docs">Local setup</Link>
        </div>
      </section>
    </>
  );
}
