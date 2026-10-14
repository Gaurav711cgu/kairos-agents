import { displayLabel, sentenceText } from "@/lib/display";
import { cookies } from "next/headers";
import Link from "next/link";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedHistoryError } from "@/lib/evidence-mode";
import { reportDetail, Report } from "@/lib/workbench";
import { ReportPairs } from "@/components/ReportPairs";
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
    if (isRecordedEvidence()) throw new Error(recordedHistoryError);
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
  if (!report)
    return (
      <div className="page-shell">
        <div className="page-heading">
          <span className="eyebrow">Report unavailable</span>
          <h1>Report unavailable.</h1>
          <p role="alert">{error}</p>
          <Link className="button" href="/reports">
            All reports
          </Link>
        </div>
      </div>
    );
  const percent = (x: number) => (100 * x).toFixed(1) + "%";
  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">
          Evaluation / {displayLabel(report.split)} /{" "}
          {displayLabel(report.mode)}
        </span>
        <h1>
          {displayLabel(report.gate.verdict)}.<br />
          <em>Release comparison.</em>
        </h1>
        <p>
          {sentenceText(report.gate.reason)} {report.gate.n} retained paired
          tasks; {report.provider_failures} provider failures counted.
        </p>
      </div>
      <section className="report-verdict">
        <div>
          <span className="eyebrow">Paired success difference</span>
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
          <span className="eyebrow">Predeclared sample plan</span>
          <h3>{sentenceText(report.gate.plan.method)}</h3>
          <p>{report.gate.plan.sampling}</p>
          <p>
            Minimum independent tasks:{" "}
            {report.gate.plan.minimum_independent_tasks}. Full suite only; no
            optional stopping.
          </p>
          <a href="https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830">
            Hoeffding, 1963
          </a>
        </aside>
      </section>
      <section className="hard-checks">
        <span className="eyebrow">Hard invariants / Any failure blocks</span>
        {report.hard_checks.map((c) => (
          <div key={c.name}>
            <strong>{displayLabel(c.name)}</strong>
            <span className={"status " + (c.passed ? "good" : "attention")}>
              {c.passed ? "Passed" : "Failed"}
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
        Download all task inputs and raw outputs
      </a>
      <aside className="scope-note">
        <strong>Report limitations</strong>
        <ul>
          {report.limits.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
