import Link from "next/link";
import report from "@/lib/comparison014-report.json";

export const metadata = { title: "Repair comparison: baseline, loop, and drafts" };

interface CaseResult {
  outcome: string;
  verified: boolean;
  calls: number;
  checks: number;
  elapsed_seconds: number;
}

interface CaseItem {
  instance_id: string;
  repository: string;
  split: string;
  qualified: boolean;
  arms: Record<string, CaseResult>;
}

const outcomeLabels: Record<string, string> = {
  verified_repair: "Verified",
  no_patch: "No patch",
  invalid_patch: "Invalid patch",
  environment_failure: "Env failure",
  exhausted_budget: "Exhausted",
};

function OutcomeBadge({ arm, result, caseId }: { arm: string; result?: CaseResult; caseId: string }) {
  if (!result) return <span className="outcome-badge-empty">—</span>;
  const label = outcomeLabels[result.outcome] || result.outcome;
  const isPass = result.verified;
  return (
    <Link
      href={`/repair-comparison/${caseId}/${arm}`}
      className={`outcome-badge ${isPass ? "badge-pass" : "badge-fail"}`}
    >
      <span className="badge-text">{label}</span>
      <span className="badge-meta">{result.calls}c · {result.elapsed_seconds.toFixed(0)}s</span>
    </Link>
  );
}

export default function RepairComparisonPage() {
  const cases = (report.cases as CaseItem[]).filter(c => c.qualified);
  const holdoutSummary = report.summary.holdout;
  const devSummary = report.summary.development;

  return (
    <div className="page-shell reading-page">
      <header className="page-heading">
        <span className="eyebrow">Repair comparison / Measurement 014</span>
        <h1>Three repair strategies.<br /><em>57 recorded attempts.</em></h1>
        <p>
          Compare single-call baseline, bounded loop and independent drafts across 19 qualified defects
          in Django and pytest under identical context and verifier budgets.
        </p>
      </header>

      <div className="article-layout">
        <aside className="article-index">
          <span className="eyebrow">Inspect the comparison</span>
          <a href="#summary">Strategy summary</a>
          <a href="#matrix">Attempt matrix</a>
          <a href="#downloads">Downloads & proofs</a>
          <Link href="/repair-investigation">Single investigation</Link>
          <Link href="/retrieval-training">Retrieval training</Link>
        </aside>

        <article className="prose">
          <section id="summary">
            <h2>Holdout outcomes and resource cost</h2>
            <p>
              Across 12 held-out issues, the bounded loop verified <strong>7 of 12 repairs</strong>,
              compared to <strong>1 of 12</strong> for single-call baseline and <strong>1 of 12</strong> for
              independent drafts. Loop used 35 model calls and 12 checks; baseline used 9 calls and 1 check.
            </p>
            <div className="pair-table-scroll" role="region" aria-label="Strategy summary table">
              <table className="pair-table" aria-label="Strategy summary table" style={{ minWidth: 0 }}>
                <caption>Held-out split (12 cases) versus Development split (7 cases)</caption>
                <thead>
                  <tr>
                    <th scope="col">Strategy</th>
                    <th scope="col">Holdout verified</th>
                    <th scope="col">Dev verified</th>
                    <th scope="col">Holdout calls</th>
                    <th scope="col">Holdout checks</th>
                    <th scope="col">Holdout time</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">Baseline (single-call)</th>
                    <td><strong>{holdoutSummary.baseline.verified} / 12</strong></td>
                    <td>{devSummary.baseline.verified} / 7</td>
                    <td>{holdoutSummary.baseline.calls}</td>
                    <td>{holdoutSummary.baseline.checks_captured}</td>
                    <td>{holdoutSummary.baseline.elapsed_seconds.toFixed(0)} s</td>
                  </tr>
                  <tr>
                    <th scope="row">Bounded Loop</th>
                    <td><strong>{holdoutSummary.loop.verified} / 12</strong></td>
                    <td>{devSummary.loop.verified} / 7</td>
                    <td>{holdoutSummary.loop.calls}</td>
                    <td>{holdoutSummary.loop.checks_captured}</td>
                    <td>{holdoutSummary.loop.elapsed_seconds.toFixed(0)} s</td>
                  </tr>
                  <tr>
                    <th scope="row">Independent Drafts</th>
                    <td><strong>{holdoutSummary.drafts.verified} / 12</strong></td>
                    <td>{devSummary.drafts.verified} / 7</td>
                    <td>{holdoutSummary.drafts.calls}</td>
                    <td>{holdoutSummary.drafts.checks_captured}</td>
                    <td>{holdoutSummary.drafts.elapsed_seconds.toFixed(0)} s</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section id="matrix">
            <h2>All 19 qualified candidate cases</h2>
            <p>
              Select any cell to inspect the full recorded investigation: exact AST context retrieved,
              model patch diff, test suite output, and token counts.
            </p>
            <div className="pair-table-scroll" role="region" aria-label="19 cases comparison matrix">
              <table className="pair-table" aria-label="19 cases comparison matrix" style={{ minWidth: 0 }}>
                <thead>
                  <tr>
                    <th scope="col">Instance ID</th>
                    <th scope="col">Repo</th>
                    <th scope="col">Split</th>
                    <th scope="col">Baseline</th>
                    <th scope="col">Bounded Loop</th>
                    <th scope="col">Drafts</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.instance_id}>
                      <th scope="row" style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>
                        {c.instance_id}
                      </th>
                      <td>{c.repository.split("/")[1]}</td>
                      <td>{c.split === "holdout" ? "Held-out" : "Dev"}</td>
                      <td>
                        <OutcomeBadge arm="baseline" result={c.arms.baseline} caseId={c.instance_id} />
                      </td>
                      <td>
                        <OutcomeBadge arm="loop" result={c.arms.loop} caseId={c.instance_id} />
                      </td>
                      <td>
                        <OutcomeBadge arm="drafts" result={c.arms.drafts} caseId={c.instance_id} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="downloads">
            <h2>Download captured evidence</h2>
            <p>
              All 57 attempts are hash-bound to their original verification logs. No live Docker or
              inference runs when browsing this archive.
            </p>
            <div className="investigation-actions">
              <a className="text-link" href="/api/comparison014/attempts.json" download>
                Download full comparison report (JSON)
              </a>
              <a className="text-link" href="/api/comparison014/receipt.json" download>
                Download qualification receipt (JSON)
              </a>
            </div>
          </section>
        </article>
      </div>
    </div>
  );
}
