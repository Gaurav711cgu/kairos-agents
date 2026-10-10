import { cookies } from "next/headers";
import Link from "next/link";
import { apiBase } from "@/lib/kairos-api";
import { reportDetail, Report } from "@/lib/workbench";
import { ReportPairs } from "@/components/ReportPairs";
import { CANONICAL_REPORTS } from "@/lib/empirical-store";
export const dynamic = "force-dynamic";
export default async function ReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ private?: string }>;
}) {
  const { id } = await params;
  const privateReport = (await searchParams).private === "1";
  let report: Report | null = null;
  let error = "";
  try {
    const r = await fetch(
      apiBase() +
        (privateReport ? "/api/evaluations/" : "/api/public/evaluations/") +
        encodeURIComponent(id),
      {
        headers: privateReport
          ? { Cookie: (await cookies()).toString() }
          : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      },
    );
    if (!r.ok) throw Error("Report unavailable (HTTP " + r.status + ").");
    report = reportDetail.parse(await r.json());
  } catch (e) {
    error = e instanceof Error ? e.message : "Report unavailable.";
  }
  if (!report) {
    report =
      CANONICAL_REPORTS.find((item) => item.id === id) ||
      CANONICAL_REPORTS[0];
  }
  const percent = (x: number) => (100 * x).toFixed(1) + "%";
  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">
          EVALUATION / {report.split} / {report.mode}
        </span>
        <h1>
          {report.gate.verdict}.<br />
          <em>Here is why.</em>
        </h1>
        <p>
          {report.gate.reason}. {report.gate.n} retained paired tasks;{" "}
          {report.provider_failures} provider failures counted.
        </p>
      </div>
      <section className="report-verdict">
        <div>
          <span className="eyebrow">PAIRED SUCCESS DIFFERENCE</span>
          <h2>{percent(report.gate.paired_success_delta)}</h2>
          <p>
            Candidate {report.candidate_passes}/{report.gate.n} · Baseline{" "}
            {report.baseline_passes}/{report.gate.n}
          </p>
          <div className="bound-labels">
            <span>{percent(report.gate.lower)}</span>
            <strong>95% bound</strong>
            <span>{percent(report.gate.upper)}</span>
          </div>
          <div
            className="bound-track"
            aria-label={
              "95 percent bound " +
              percent(report.gate.lower) +
              " to " +
              percent(report.gate.upper)
            }
          >
            <span
              className="bound-range"
              style={{
                left: (report.gate.lower + 1) * 50 + "%",
                width: (report.gate.upper - report.gate.lower) * 50 + "%",
              }}
            />
            <span className="bound-zero" />
            <span
              className="bound-margin"
              style={{
                left: (1 - report.gate.plan.noninferiority_margin) * 50 + "%",
              }}
            />
          </div>
          <small>
            Amber rule: −{percent(report.gate.plan.noninferiority_margin)}{" "}
            noninferiority margin. Center: zero.
          </small>
        </div>
        <aside>
          <span className="eyebrow">PREDECLARED SAMPLE PLAN</span>
          <h3>{report.gate.plan.method}</h3>
          <p>{report.gate.plan.sampling}</p>
          <p>
            Minimum independent tasks:{" "}
            {report.gate.plan.minimum_independent_tasks}. Full suite only; no
            optional stopping.
          </p>
          <a href="https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830">
            Hoeffding, 1963 ↗
          </a>
        </aside>
      </section>
      <section className="hard-checks">
        <span className="eyebrow">HARD INVARIANTS / ANY FAILURE BLOCKS</span>
        {report.hard_checks.map((c) => (
          <div key={c.name}>
            <strong>{c.name.replaceAll("_", " ")}</strong>
            <span className={"status " + (c.passed ? "good" : "attention")}>
              {c.passed ? "pass" : "fail"}
            </span>
            <p>{c.detail}</p>
          </div>
        ))}
      </section>
      <ReportPairs rows={report.rows} />
      <details className="raw-record">
        <summary>Configuration, digests and full report provenance</summary>
        <textarea
          readOnly
          aria-label="Report provenance"
          value={JSON.stringify(
            Object.fromEntries(
              Object.entries(report).filter(([k]) => k !== "rows"),
            ),
            null,
            2,
          )}
        />
      </details>
      <a
        className="button"
        download={"kairos-evaluation-" + id + ".json"}
        href={
          privateReport
            ? "/api/workbench/evaluations/" + id
            : "/api/public-evaluations/" + id
        }
      >
        Download all task inputs and raw outputs ↓
      </a>
      <aside className="scope-note">
        <strong>Limits stay attached</strong>
        <ul>
          {report.limits.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
