import Link from "next/link";
import { getEvidence, getIncidents, date } from "@/lib/kairos-api";
import { ServiceError } from "@/components/IncidentRows";
export const dynamic = "force-dynamic";
export default async function Evidence() {
  const [evidence, runs] = await Promise.all([getEvidence(), getIncidents()]);
  const records = runs.data?.incidents ?? [];
  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">EVIDENCE / CLAIMS WITH A SOURCE</span>
        <h1>
          Inspect the proof.
          <br />
          <em>Keep the limits.</em>
        </h1>
        <p>
          Execution results come directly from the API. Source records remain
          available beside each verdict.
        </p>
      </div>
      {runs.error ? (
        <ServiceError message={runs.error} />
      ) : (
        <section className="evidence-table">
          <div className="table-head">
            <span>Recorded execution</span>
            <span>Independent checks</span>
            <span>Provenance</span>
          </div>
          {records.map((record) => (
            <Link href={"/incidents/" + record.id} key={record.id}>
              <div>
                <strong>{record.title}</strong>
                <small>
                  {record.policy} · {record.event_count} events
                </small>
              </div>
              <span
                className={
                  record.grade_passed ? "status good" : "status attention"
                }
              >
                {record.grade_passed
                  ? "Passed"
                  : record.grade_passed === false
                    ? "Failed"
                    : "Unscored"}
              </span>
              <div>
                <span>Reference policy</span>
                <small>{date(record.created_at)} ↗</small>
              </div>
            </Link>
          ))}
          {!records.length && (
            <p className="empty-state">No published evidence yet.</p>
          )}
        </section>
      )}
      <section className="evidence-manifest">
        <div>
          <span className="eyebrow">SERVICE-SUPPLIED MANIFEST</span>
          <h2>Raw, inspectable provenance.</h2>
          <p>
            This is the current evidence response, rendered without inventing
            benchmarks or release status.
          </p>
        </div>
        {evidence.error ? (
          <ServiceError message={evidence.error} />
        ) : (
          <pre tabIndex={0}>{JSON.stringify(evidence.data, null, 2)}</pre>
        )}
      </section>
      <aside className="scope-note">
        <strong>No release confidence claim</strong>
        <p>
          These are deterministic checks on synthetic scenarios. Model quality,
          statistical confidence intervals, production scale, uptime, and
          adoption remain unmeasured.
        </p>
      </aside>
    </div>
  );
}
