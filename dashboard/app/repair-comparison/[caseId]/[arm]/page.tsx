import Link from "next/link";
import { notFound } from "next/navigation";
import catalog from "@/lib/comparison014-downloads.json";
import report from "@/lib/comparison014-report.json";
import { comparisonRecordSchema } from "@/lib/comparison014-record";
import { CheckEvidence, PatchEvidence, StepEvidence } from "@/components/InvestigationEvidence";

interface PageProps {
  params: Promise<{ caseId: string; arm: string }>;
}

export async function generateStaticParams() {
  const params: { caseId: string; arm: string }[] = [];
  for (const caseItem of report.cases) {
    if (!caseItem.qualified) continue;
    for (const arm of ["baseline", "loop", "drafts"]) {
      params.push({ caseId: caseItem.instance_id, arm });
    }
  }
  return params;
}

export async function generateMetadata({ params }: PageProps) {
  const { caseId, arm } = await params;
  return { title: `${caseId} (${arm}) repair investigation` };
}

export default async function RepairComparisonDetailPage({ params }: PageProps) {
  const { caseId, arm } = await params;
  const key = `${caseId}-${arm}`;
  const files = (catalog as Record<string, Record<string, { base64: string }>>)[key];

  if (!files || !files["bundle.json"]) {
    notFound();
  }

  const rawBundle = Buffer.from(files["bundle.json"].base64, "base64").toString("utf-8");
  const parsedBundle = JSON.parse(rawBundle);
  const record = comparisonRecordSchema.parse(parsedBundle);

  const patch = files["candidate.patch"]
    ? Buffer.from(files["candidate.patch"].base64, "base64").toString("utf-8")
    : null;

  const checksRaw = files["checks.json"]
    ? Buffer.from(files["checks.json"].base64, "base64").toString("utf-8")
    : null;
  const checkResult = checksRaw ? JSON.parse(checksRaw) : null;

  const sourceSteps = record.steps.filter((s) => s.name === "initial_source");
  const processSteps = record.steps.filter(
    (s) => s.name !== "initial_source" && s.name !== "retrieval_selection012"
  );

  const labels: Record<string, string> = {
    selection: "Prepare next model call",
    dispatch: "Capture model response",
    read_file: "Read original source",
    propose_patch: "Validate proposed patch",
    run_checks: "Run independent checks",
    draft_candidate: "Generate candidate draft",
    draft_selection: "Select verified candidate",
  };

  const caseSummary = report.cases.find((c) => c.instance_id === caseId);
  const armSummary = (caseSummary?.arms as Record<string, {
    outcome: string;
    verified: boolean;
    calls: number;
    checks: number;
    elapsed_seconds: number;
    input_tokens: number;
    output_tokens: number;
  }>)?.[arm];

  return (
    <div className="page-shell reading-page">
      <header className="page-heading">
        <span className="eyebrow">
          <Link href="/repair-comparison">← Back to Comparison Overview</Link>
        </span>
        <h1>
          {caseId}
          <br />
          <em>Strategy: {arm}</em>
        </h1>
        <p>
          Verdict: <strong>{armSummary?.verified ? "Verified repair" : armSummary?.outcome || "Completed"}</strong> ·
          Split: <strong>{caseSummary?.split}</strong> · Repo: <strong>{caseSummary?.repository}</strong>
        </p>
      </header>

      <div className="article-layout">
        <aside className="article-index">
          <span className="eyebrow">Inspect the attempt</span>
          <a href="#issue">Original issue</a>
          {sourceSteps.length > 0 && <a href="#source">Retrieved source</a>}
          {patch && <a href="#patch">Proposed patch</a>}
          {checkResult && <a href="#checks">Check execution</a>}
          <a href="#steps">Recorded timeline</a>
          <a href="#downloads">Artifact downloads</a>
        </aside>

        <article className="prose">
          <section id="issue">
            <h2>Upstream issue description</h2>
            <details className="raw-record" open>
              <summary>Read issue statement</summary>
              <pre role="region" aria-label="Issue statement text" tabIndex={0}>
                {record.task_snapshot.issue}
              </pre>
            </details>
            <dl className="context-budget">
              <div>
                <dt>Strategy</dt>
                <dd>{arm}</dd>
              </div>
              <div>
                <dt>Model calls</dt>
                <dd>{armSummary?.calls ?? record.model_calls}</dd>
              </div>
              <div>
                <dt>Checks</dt>
                <dd>{armSummary?.checks ?? record.check_count}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{(armSummary?.elapsed_seconds ?? 0).toFixed(1)} s</dd>
              </div>
              {armSummary && (
                <>
                  <div>
                    <dt>Input tokens</dt>
                    <dd>{armSummary.input_tokens.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Output tokens</dt>
                    <dd>{armSummary.output_tokens.toLocaleString()}</dd>
                  </div>
                </>
              )}
            </dl>
          </section>

          {sourceSteps.length > 0 && (
            <section id="source">
              <h2>Initial AST source context</h2>
              <p>
                Retrieved {sourceSteps.length} initial source regions from the repository before model dispatch.
              </p>
              {sourceSteps.map((step, idx) => (
                <details className="raw-record" key={step.seq}>
                  <summary>
                    Region {idx + 1}: {String(step.result?.body.path ?? "Original source")}
                  </summary>
                  <StepEvidence step={step} />
                </details>
              ))}
            </section>
          )}

          {patch && (
            <section id="patch">
              <h2>Proposed model patch</h2>
              <p>
                Unified diff candidate generated by the model for this attempt.
              </p>
              <PatchEvidence patch={patch} />
              <div className="investigation-actions">
                <a className="text-link" href={`/api/comparison014/${key}/candidate.patch`} download>
                  Download candidate.patch
                </a>
              </div>
            </section>
          )}

          {checkResult && (
            <section id="checks">
              <h2>Independent verification checks</h2>
              <CheckEvidence result={checkResult as Record<string, unknown>} />
              <div className="investigation-actions">
                <a className="text-link" href={`/api/comparison014/${key}/checks.json`} download>
                  Download checks.json
                </a>
              </div>
            </section>
          )}

          <section id="steps">
            <h2>Recorded step sequence</h2>
            <p>Chronological sequence of all interactions, tool calls, and verifier evaluations.</p>
            {processSteps.map((step) => (
              <details className="raw-record" key={step.seq}>
                <summary>
                  Step {step.seq}: {labels[step.name] ?? step.name}
                </summary>
                <StepEvidence step={step} />
              </details>
            ))}
          </section>

          <section id="downloads">
            <h2>Download captured artifacts</h2>
            <div className="investigation-actions">
              <a className="text-link" href={`/api/comparison014/${key}/bundle.json`} download>
                Download complete investigation bundle (JSON)
              </a>
              <a className="text-link" href={`/api/comparison014/${key}/receipt.json`} download>
                Download qualification receipt (JSON)
              </a>
            </div>
          </section>
        </article>
      </div>
    </div>
  );
}
