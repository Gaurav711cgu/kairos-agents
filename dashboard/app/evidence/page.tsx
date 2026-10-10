import Link from "next/link";
import { getEvidence, getIncidents, date } from "@/lib/kairos-api";
import { ServiceError } from "@/components/IncidentRows";
import StatisticalDistributionVisualizer from "@/components/StatisticalDistributionVisualizer";

export const dynamic = "force-dynamic";

export default async function Evidence() {
  const [_evidence, runs] = await Promise.all([getEvidence(), getIncidents()]);
  const records = runs.data?.incidents ?? [];

  return (
    <div className="page-shell space-y-8">
      <div className="page-heading">
        <span className="eyebrow">EMPIRICAL EVIDENCE / MATHEMATICALLY GROUNDED AUDIT</span>
        <h1>
          Inspect the proof.
          <br />
          <em>Keep the limits.</em>
        </h1>
        <p>
          Execution results come directly from executed tests and SQLite database runs.
          Source records remain inspectable beside each verdict.
        </p>
      </div>

      {/* 1. Interactive Paired Bootstrap Hypothesis Testing Visualizer */}
      <section className="mb-8">
        <StatisticalDistributionVisualizer />
      </section>

      {/* 2. Recorded Executions Table */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <span className="eyebrow text-zinc-300">INDIVIDUAL EXECUTION TRACES</span>
          <span className="text-xs font-mono text-zinc-400">{records.length} records available</span>
        </div>

        {runs.error ? (
          <ServiceError message={runs.error} />
        ) : (
          <div className="evidence-table">
            <div className="table-head">
              <span>Recorded execution</span>
              <span>Independent checks</span>
              <span>Provenance</span>
            </div>
            {records.map((record) => (
              <Link href={"/incidents/" + record.id} key={record.id} className="antigravity-card">
                <div>
                  <strong>{record.title}</strong>
                  <small>
                    {record.policy} context · {record.event_count} events · {record.scenario_id}
                  </small>
                </div>
                <span
                  className={
                    record.grade_passed ? "status good" : "status attention"
                  }
                >
                  {record.grade_passed
                    ? "[PASS]"
                    : record.grade_passed === false
                      ? "[FAIL]"
                      : "[UNSCORED]"}
                </span>
                <div>
                  <span>{record.provenance}</span>
                  <small>{date(record.created_at)} [INSPECT]</small>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Raw Evaluation Downloads */}
      <section className="p-4 rounded-lg border border-[#27272a] bg-[#121214] font-mono text-xs">
        <div className="text-zinc-200 font-semibold mb-2 uppercase tracking-wider">
          Download Raw Evaluation &amp; Execution Manifests (JSON)
        </div>
        <div className="flex flex-wrap gap-3">
          <a
            href="/api/public-evaluations/rep-paired-bootstrap-verifier"
            download
            className="px-3 py-1.5 rounded border border-[#3f3f46] bg-[#18181b] text-zinc-300 hover:text-white hover:border-zinc-400 transition-colors flex items-center gap-1.5"
          >
            <span>Bootstrap Evaluation (rep-paired-bootstrap-verifier.json)</span>
          </a>
          <a
            href="/api/public-evaluations/rep-compaction-efficiency"
            download
            className="px-3 py-1.5 rounded border border-[#3f3f46] bg-[#18181b] text-zinc-300 hover:text-white hover:border-zinc-400 transition-colors flex items-center gap-1.5"
          >
            <span>Compaction Audit (rep-compaction-efficiency.json)</span>
          </a>
        </div>
      </section>
    </div>
  );
}
