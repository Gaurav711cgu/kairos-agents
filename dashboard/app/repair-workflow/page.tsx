import Link from "next/link";
import captures from "@/lib/repair010-results.json";
import { CheckEvidence, PatchEvidence } from "@/components/InvestigationEvidence";

export const metadata = { title: "Repair workflow follow-up" };

type Candidate = { case: string; title: string; patch: string; checks: Record<string, unknown> };
type Attempt = {
  experiment: string; case: string; outcome: string; calls: number;
  patches: number; checks: number; elapsed_seconds: number | null;
};
const evidence = captures as {
  results: Candidate[]; attempts: Attempt[]; recorded_at: string;
};
const outcomes: Record<string, string> = {
  environment_failure: "Environment failure",
  invalid_response: "Response rejected by the adapter",
  invalid_patch: "Patch rejected",
  failed_checks: "Checks failed",
  unknown_dispatch: "Dispatch outcome unknown",
};

export default function RepairWorkflow() {
  return <div className="page-shell reading-page">
    <header className="page-heading">
      <span className="eyebrow">Repair workflow / Development follow-up</span>
      <h1>A captured patch.<br /><em>Checked independently.</em></h1>
      <p>Two model-generated development candidates passed subsequent independent checks. Inspect the actual changes, test output and original attempt outcomes.</p>
    </header>
    <div className="article-layout">
      <aside className="article-index">
        <span className="eyebrow">Follow the evidence</span>
        <a href="#results">Candidate checks</a>
        <a href="#attempts">Original attempts</a>
        <a href="#workflow">Try a reviewed task</a>
        <a href="#scope">What this establishes</a>
      </aside>
      <article className="prose">
        <section id="results">
          <h2>Two captured candidates passed their checks.</h2>
          <p>The pytest candidate passed 22 registered tests; the Django candidate passed four. Both came from previously exposed development cases. These are post-hoc candidate checks, kept separate from completed investigations and fresh validation.</p>
          <p>The original version 2 adapter rejected the responses because of its metadata handling. The captured patch text was preserved and checked afterward without another model call or a hand-written replacement.</p>
          {evidence.results.map(candidate => <section key={candidate.case} aria-label={candidate.title}>
            <h3>{candidate.title}</h3>
            <p><code>{candidate.case}</code> · Captured development candidate</p>
            <PatchEvidence patch={candidate.patch} />
            <CheckEvidence result={candidate.checks} />
            <div className="investigation-actions">
              <a className="text-link" href={`/api/repair010/${candidate.case}/candidate.patch`} download>Download candidate patch</a>
              <a className="text-link" href={`/api/repair010/${candidate.case}/checks.json`} download>Download candidate checks</a>
              <a className="text-link" href={`/api/repair010/${candidate.case}/original-model-response.json`} download>Download original model response</a>
            </div>
          </section>)}
        </section>
        <section id="attempts">
          <h2>Keep the original outcomes visible.</h2>
          <p>Version 3 corrected the adapter issue, then stopped at the subscription usage limit. Its dispatch outcome remains unknown and was not resent. This follow-up has no completed end-to-end repair success to report.</p><p>Next step: run a newly reviewed task with GPT-6.1-Sol after normal quota returns, then freeze the next evaluation. This path uses the existing laptop and subscription; no new hardware or API billing is required.</p>
          <details className="raw-record">
            <summary>Inspect every captured attempt</summary>
            {/* The horizontally scrollable ledger needs keyboard focus. */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            <div className="pair-table-scroll" role="region" aria-label="Development attempt ledger" tabIndex={0}>
              <table className="pair-table">
                <thead><tr><th scope="col">Attempt</th><th scope="col">Recorded outcome</th><th scope="col">Execution</th></tr></thead>
                <tbody>{evidence.attempts.map((attempt, index) => <tr key={`${attempt.experiment}-${attempt.case}-${index}`}>
                  <th scope="row">{attempt.case}<br />{attempt.experiment}</th>
                  <td>{outcomes[attempt.outcome] ?? attempt.outcome}</td>
                  <td>{attempt.calls} calls · {attempt.patches} patches · {attempt.checks} checks<br />{typeof attempt.elapsed_seconds === "number" ? `${attempt.elapsed_seconds.toFixed(1)} seconds` : "Elapsed time unavailable"}</td>
                </tr>)}</tbody>
              </table>
            </div>
          </details>
          <a className="text-link" href="/api/repair010/attempts.json" download>Download complete attempt ledger</a>
        </section>
        <section id="workflow">
          <h2>Investigate another reviewed Python defect.</h2>
          <p>The optional local CLI accepts a newly registered unresolved task. It does not require a maintainer repair. A trusted operator prepares a pinned source snapshot, approved source paths and reviewed test recipe before execution.</p>
          <ol>
            <li><strong>Prepare the task.</strong> Capture a failing regression and passing relevant existing tests against the same source and environment. Keep the verifier outside source tools.</li>
            <li><strong>Validate registration.</strong> Supply the manifest, case root and task ID. Kairos checks source and verifier hashes, complete baseline receipts, paths and storage limits.</li>
            <li><strong>Run one bounded investigation.</strong> The optional Codex adapter requests GPT-6.1-Sol through an existing local ChatGPT login. Kairos captures the issue, source, rejected edits and check feedback, with at most six CLI dispatches, two candidates, two checks and ten minutes.</li>
            <li><strong>Read the result.</strong> A saved receipt reports the observed outcome, patch, checks, source-isolation result and evidence hashes. Uncertain dispatches stay unknown. The original checkout remains unchanged.</li>
          </ol>
          <details className="raw-record"><summary>Show the local commands</summary><pre>{[
            "python3 -m scripts.study010 doctor",
            "",
            "python3 -m scripts.study010 validate-task --manifest /path/to/reviewed/registry.json --case-root /path/to/prepared/cases --task-id reviewed-defect",
            "",
            "python3 -m scripts.study010 run --manifest /path/to/reviewed/registry.json --case-root /path/to/prepared/cases --task-id reviewed-defect --runtime .runtime/study010/reviewed-defect",
            "",
            "python3 -m scripts.study010 report --runtime .runtime/study010/reviewed-defect",
          ].join("\n")}</pre></details>
          <p>These commands run locally after preparation. This page displays saved evidence; it does not submit a browser job. The authenticated workbench keeps its existing pinned local-model provider. The optional CLI has a different model profile and uses subscription capacity; internal provider retries are not measured as individual requests.</p>
          <Link className="text-link" href="/docs">Open the setup and verification guide</Link>
        </section>
        <section id="scope">
          <h2>A stronger mechanism needs fresh evidence.</h2>
          <p>Exact rejected edits now survive context reconstruction. Source-bound replacements and independent checks apply to registered tasks rather than a list of case-specific fixes. That removes observed workflow waste; it does not make every future defect repairable.</p>
          <p>The frozen local-model v7 study, completed on 13 October 2026, remains 0/10 across five qualified cases. It describes that model and configuration, not an overall score for these later candidates. Public historical source may have appeared in training data, and benchmark setup supplied entry files from known repair paths. A new held-out study is needed to measure the optional workflow.</p>
          <p>Candidate code shares the reviewed test environment. These checks do not establish adversarial test-forgery resistance, broad repository support or autonomous repair reliability.</p>
          <p>Evidence captured: <time dateTime={evidence.recorded_at}>{evidence.recorded_at}</time>.</p>
          <div className="investigation-actions"><Link className="text-link" href="/advancement">Inspect the frozen local-model study</Link><Link className="text-link" href="/engineering">Read the engineering decisions</Link></div>
        </section>
      </article>
    </div>
  </div>;
}
