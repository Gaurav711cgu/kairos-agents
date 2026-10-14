import { displayLabel, sentenceText } from "@/lib/display";
import Link from "next/link";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedHistoryError } from "@/lib/evidence-mode";
import { reportSummary } from "@/lib/workbench";
import { z } from "zod";

export const dynamic = "force-dynamic";

export default async function Reports() {
  let reports: z.infer<typeof reportSummary>[] = [];
  let error = "";
  try {
    if (isRecordedEvidence()) throw new Error(recordedHistoryError);
    const r = await fetch(apiBase() + "/api/public/evaluations", {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (!r.ok) throw Error("Source unavailable (HTTP " + r.status + ").");
    if (r.ok) {
      reports = z
        .object({ reports: z.array(reportSummary) })
        .parse(await r.json()).reports;
    }
  } catch (failure) {
    error = failure instanceof Error ? failure.message : "Source unavailable.";
  }

  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">Release reports / Empirical evidence</span>
        <h1>
          Compare results.
          <br />
          <em>Review the release rule.</em>
        </h1>
        <p>
          Per-task pairs, predeclared margins, and raw verifiable outputs.
          Deterministic calibration stays separate from model observations.
        </p>
      </div>

      {error && (
        <p className="workbench-error" role="alert">
          {error}
        </p>
      )}
      {!error && !reports.length && (
        <p className="empty-state">No published records yet.</p>
      )}
      <div className="report-index">
        {reports.map((r) => (
          <Link
            className="report-row antigravity-card"
            key={r.id}
            href={"/reports/" + r.id}
          >
            <div>
              <strong>{displayLabel(r.mode)}</strong>
              <small>
                {r.gate.n} task pairs · {displayLabel(r.split)} · 95% bound [
                {r.gate.lower.toFixed(3)}, {r.gate.upper.toFixed(3)}]
              </small>
            </div>
            <span
              className={
                "status " + (r.gate.verdict === "pass" ? "good" : "attention")
              }
            >
              {displayLabel(r.gate.verdict)}
            </span>
            <p>{sentenceText(r.gate.reason)}</p>
          </Link>
        ))}
      </div>

      <aside className="scope-note">
        <strong>Evaluation scope</strong>
        <p>
          The release rule uses paired Hoeffding bounds, a predeclared 10
          percentage point margin, and at least 1,024 independent synthetic task
          draws. Hard invariant failures block release. A pass applies only to
          this synthetic task distribution; it does not establish production
          safety.
        </p>
      </aside>
    </div>
  );
}
