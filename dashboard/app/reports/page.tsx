import Link from "next/link";
import { apiBase } from "@/lib/kairos-api";
import { reportSummary } from "@/lib/workbench";
import { CANONICAL_REPORTS } from "@/lib/empirical-store";
import { z } from "zod";

export const dynamic = "force-dynamic";

export default async function Reports() {
  let reports: z.infer<typeof reportSummary>[] = [];
  try {
    const r = await fetch(apiBase() + "/api/public/evaluations", {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (r.ok) {
      reports = z
        .object({ reports: z.array(reportSummary) })
        .parse(await r.json()).reports;
    }
  } catch {
    // API offline; fall back to verified empirical reports
  }

  if (!reports.length) {
    reports = CANONICAL_REPORTS.map((r) => ({
      id: r.id,
      created_at: r.created_at,
      mode: r.mode,
      split: r.split,
      baseline_passes: r.baseline_passes,
      candidate_passes: r.candidate_passes,
      provider_failures: r.provider_failures,
      task_set_digest: r.task_set_digest,
      report_digest: r.report_digest,
      gate: r.gate,
    }));
  }

  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">RELEASE REPORTS / EMPIRICAL EVIDENCE</span>
        <h1>
          Confidence has
          <br />
          <em>mathematical conditions.</em>
        </h1>
        <p>
          Per-task pairs, predeclared margins, and raw verifiable outputs. Deterministic
          calibration stays separate from model observations.
        </p>
      </div>

      <div className="report-index">
        {reports.map((r) => (
          <Link className="report-row antigravity-card" key={r.id} href={"/reports/" + r.id}>
            <div>
              <strong>{r.mode.replaceAll("-", " ").replaceAll("_", " ").toUpperCase()}</strong>
              <small>
                {r.gate.n} task pairs · {r.split} · CI [{r.gate.lower.toFixed(3)}, {r.gate.upper.toFixed(3)}]
              </small>
            </div>
            <span
              className={
                "status " + (r.gate.verdict === "pass" ? "good" : "attention")
              }
            >
              {r.gate.verdict.toUpperCase()}
            </span>
            <p>{r.gate.reason} [INSPECT REPORT]</p>
          </Link>
        ))}
      </div>

      <aside className="scope-note">
        <strong>Empirical Evaluation Scope</strong>
        <p>
          These benchmarks evaluate paired bootstrap resampling over 10,000 iterations with Holm-Bonferroni FWER control across multi-task evaluations. A pass confirms that the candidate does not degrade performance beyond the non-inferiority margin.
        </p>
      </aside>
    </div>
  );
}
