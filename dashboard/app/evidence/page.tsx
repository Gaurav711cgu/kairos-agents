import { displayLabel } from "@/lib/display";
import Link from "next/link";
import { getEvidence, getIncidents, date } from "@/lib/kairos-api";
import { ServiceError } from "@/components/IncidentRows";

export const dynamic = "force-dynamic";

export default async function Evidence() {
  const [evidence, runs] = await Promise.all([getEvidence(), getIncidents()]);
  const records = runs.data?.incidents ?? [];
  const metrics = [
    { label: "Published reference runs", key: "run_count" },
    { label: "Recorded reference events", key: "event_count" },
    { label: "Passing reference runs", key: "passing_runs" },
    { label: "Failing reference runs", key: "failing_runs" },
  ];
  return (
    <div className="page-shell space-y-8">
      <div className="page-heading">
        <span className="eyebrow">Evidence / Records before claims</span>
        <h1>
          Published runs.
          <br />
          <em>Results and limitations.</em>
        </h1>
        <p>
          The current investigation ledger contains real repository cases, accepted and rejected patches, and independent check output. Historical synthetic records remain below.
        </p>
      </div>
      <section className="scope-note"><h2>Real repository investigations</h2><p>The newer frozen study contains 36 attempts on twelve cases and no verified repairs. The original comparison repaired one distinct Django case with both strategies. That recorded repair was reproduced against 110 tests, with one skip.</p><Link className="text-link" href="/investigations">Open the attempt ledger</Link></section>
      <section aria-label="Historical synthetic database snapshot">
        {evidence.error ? (
          <ServiceError message={evidence.error} />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics.map((metric) => (
              <div className="antigravity-card p-5" key={metric.key}>
                <span className="eyebrow">{metric.label}</span>
                <strong className="block text-3xl font-mono mt-3">
                  {typeof evidence.data?.[metric.key] === "number"
                    ? String(evidence.data[metric.key])
                    : "Unavailable"}
                </strong>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-zinc-400 mt-3">
          Counts describe published reference runs in this database snapshot.
          They are not benchmark sample sizes.
        </p>
      </section>
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Link href="/executions" className="antigravity-card p-6">
          <span className="eyebrow">Local model / Durable jobs</span>
          <h2 className="text-xl font-semibold my-3">
            Read the failed responses.
          </h2>
          <p className="text-sm text-zinc-400">
            The initial six durable Qwen jobs passed zero independent grades.
            Four chose the wrong policy outcome, one failed its citation check,
            and one returned invalid JSON. Inspect each captured request,
            response and verdict.
          </p>
          <span className="text-link block mt-4">Open execution ledger</span>
        </Link>
        <Link href="/reports" className="antigravity-card p-6">
          <span className="eyebrow">Release / Task-level reports</span>
          <h2 className="text-xl font-semibold my-3">
            Review the evaluation results.
          </h2>
          <p className="text-sm text-zinc-400">
            The 32-task development batch contains three passing tasks, 12
            captured responses and 20 provider errors. Deterministic 1,024-task
            calibrations exercise the bound; they are separate from model
            quality evidence.
          </p>
          <span className="text-link block mt-4">
            Inspect and download reports
          </span>
        </Link>
      </section>
      <section>
        <div className="flex flex-wrap justify-between gap-3 mb-3">
          <span className="eyebrow">Published reference executions</span>
          <span className="text-xs font-mono text-zinc-400">
            {records.length} available records
          </span>
        </div>
        {runs.error ? (
          <ServiceError message={runs.error} />
        ) : records.length ? (
          <div className="evidence-table">
            <div className="table-head">
              <span>Recorded execution</span>
              <span>Independent grade</span>
              <span>Source record</span>
            </div>
            {records.map((record) => (
              <Link
                href={"/incidents/" + record.id}
                key={record.id}
                className="antigravity-card"
              >
                <div>
                  <strong>{record.title}</strong>
                  <small>
                    {displayLabel(record.policy)} · {record.event_count} events
                    · {displayLabel(record.scenario_id)}
                  </small>
                </div>
                <span
                  className={
                    record.grade_passed ? "status good" : "status attention"
                  }
                >
                  {record.grade_passed === true
                    ? "Passed"
                    : record.grade_passed === false
                      ? "Failed"
                      : "Unscored"}
                </span>
                <div>
                  <span>{displayLabel(record.provenance)}</span>
                  <small>{date(record.created_at)} · Inspect</small>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="empty-state">No published reference executions yet.</p>
        )}
      </section>
      <aside className="scope-note">
        <strong>Evidence scope</strong>
        <p>
          Earlier order-support task data is synthetic; repository investigations use real historical defects. Hash checks establish local
          correspondence, not immutable history. Hosted deployment, real
          customer adoption and model release qualification remain unverified.
          API failures display an unavailable state.
        </p>
      </aside>
    </div>
  );
}
