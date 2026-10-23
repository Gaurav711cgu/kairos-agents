import { CurrentResult } from "@/components/CurrentResult";
import Link from "next/link";
import summary from "@/lib/pilot013-summary.json";
import bundle from "@/lib/pilot013-bundle.json";
import { investigationSchema } from "@/lib/investigation-contract";
import { CheckEvidence, PatchEvidence, StepEvidence } from "@/components/InvestigationEvidence";

export const metadata = { title: "A repair investigation, from source to checks" };
const record = investigationSchema.parse(bundle);
const patch = record.steps.find(step => step.name === "propose_patch")?.result?.body.patch;
const check = record.steps.find(step => step.name === "run_checks")?.result?.body;
if (typeof patch !== "string" || !check || check.passed !== true) throw new Error("Pilot evidence is incomplete");
const source = record.steps.filter(step => step.name === "initial_source");
const process = record.steps.filter(step => step.name !== "initial_source" && step.name !== "retrieval_selection012");
const labels: Record<string, string> = {
  selection: "Prepare the next model call", dispatch: "Capture the model response",
  read_file: "Read original source", propose_patch: "Validate the proposed patch", run_checks: "Run independent checks",
};

export default function PilotInvestigation() {
  return <div className="page-shell reading-page">
    <header className="page-heading">
      <span className="eyebrow">Repair investigation / Development evidence</span>
      <h1>From selected source<br /><em>to a checked repair.</em></h1>
      <p>A real pytest defect, a model-generated change and 22 passing tests. Follow the captured investigation in the order it happened.</p>
    </header>
      <CurrentResult historical />
    <div className="article-layout">
      <aside className="article-index">
        <span className="eyebrow">Inspect the work</span>
        <a href="#problem">The problem</a><a href="#source">Selected source</a>
        <a href="#change">The change</a><a href="#checks">Independent checks</a>
        <a href="#sequence">Execution timeline</a><a href="#meaning">Results and scope</a><Link href="/retrieval-training">Retrieval training</Link>
      </aside>
      <article className="prose">
        <section id="problem">
          <h2>Test collection imports unrelated package files.</h2>
          <p>When pytest collects a package, it can import its package marker even when the collection rules exclude it. The investigation checks how package collection mounts source objects.</p>
          <p><a href={summary.issue_url}>Original upstream issue</a> · <a href={summary.source_url}>Pinned source revision</a></p>
          <details className="raw-record"><summary>Read the original issue</summary><pre role="region" aria-label="Original issue text" tabIndex={0}>{record.task_snapshot.issue}</pre></details>
          <dl className="context-budget">
            <div><dt>Model calls</dt><dd>{summary.calls}</dd></div>
            <div><dt>Applied patches</dt><dd>{summary.patches}</dd></div>
            <div><dt>Elapsed time</dt><dd>{summary.elapsed_seconds.toFixed(1)} s</dd></div>
          </dl>
        </section>
        <section id="source">
          <h2>Retrieve source, then inspect it.</h2>
          <p>The pinned CodeRankEmbed encoder ranked original repository regions. Kairos captured six regions before the first model call. The model then requested four additional file excerpts. Registered maintainer entry hints were excluded from localization.</p>
          <p>Every edit points to a captured source handle and line range. Source hashes are checked before applying replacements; verification material stays outside source tools.</p>
          {source.map((step, index) => <details className="raw-record" key={step.seq}>
            <summary>Source region {index + 1}: {String(step.result?.body.path ?? "Original source")}</summary>
            <StepEvidence step={step} />
          </details>)}
          <a className="text-link" href="/api/pilot013/retrieval.json" download>Download source selection</a>
        </section>
        <section id="change">
          <h2>Remove the premature object mount.</h2>
          <p>The proposed change removes one call from package collection. The model authored this patch; Kairos validated it against the captured original source and checked it immediately.</p>
          <PatchEvidence patch={patch as string} />
          <a className="text-link" href="/api/pilot013/candidate.patch" download>Download model patch</a>
        </section>
        <section id="checks">
          <h2>Let the independent verifier decide.</h2>
          <CheckEvidence result={check as Record<string, unknown>} />
          <p>The existing qualified baseline and reference receipts precede this run. The candidate passed the registered regression and relevant existing tests in a disposable container. The original checkout remained unchanged.</p>
          <p>The verifier used a non-root user, no runtime network, two CPUs, 1 GiB memory and a 120-second check limit. These checks cover the registered behavior; they do not prove resistance to adversarial test forgery.</p>
          <div className="investigation-actions">
            <a className="text-link" href="/api/pilot013/checks.json" download>Download original check capture</a>
            <a className="text-link" href="/api/pilot013/bundle.json" download>Download complete investigation</a>
            <a className="text-link" href="/api/pilot013/receipt.json" download>Download provenance receipt</a>
          </div>
        </section>
        <section id="sequence">
          <h2>Inspect each captured step.</h2>
          <p>Selections, model actions, source reads, the patch and checks retain their recorded order. Opening a step reads saved evidence. It does not start inference or replay a tool.</p>
          {process.map(step => <details className="raw-record" key={step.seq}>
            <summary>Step {step.seq}: {labels[step.name] ?? step.name}</summary><StepEvidence step={step} />
          </details>)}
        </section>
        <section id="meaning">
          <p><Link className="text-link" href="/retrieval-training">Inspect retrieval training and held-out results</Link></p>
          <h2>One completed development repair.</h2>
          <p>This run completed end to end: five model calls, one applied patch and one independent check with 22 passing tests. It used a previously exposed development issue whose public text contains repair hints. It is separate from fresh validation and the earlier post-hoc candidate checks.</p>
          <p>Earlier 0/10 and 0/36 studies remain visible. This pilot establishes that the new path can complete this investigation; it does not establish loop superiority or broad repair effectiveness.</p>
          <details className="raw-record"><summary>Model, inference cost and provenance</summary>
            <p>Requested model: <code>{summary.requested_model}</code>. The provider did not return a resolved model identifier. Existing ChatGPT authentication was used; no API-key billing or paid fallback was enabled.</p>
            <p>{summary.input_tokens?.toLocaleString("en-US") ?? "Unavailable"} captured input tokens; {summary.output_tokens?.toLocaleString("en-US") ?? "unavailable"} captured output tokens. Harness calls are separate from opaque CLI-internal retries. Embedding/index preparation precedes the reported investigation time.</p>
            <p>Source revision: <code>{summary.source_revision}</code>. Captured <time dateTime={summary.recorded_at}>{summary.recorded_at}</time>. This is a reviewed static export of public-upstream development evidence, not a newly submitted browser job.</p>
          </details>
          <div className="investigation-actions"><Link className="text-link" href="/repair-workflow">Inspect earlier development candidates</Link><Link className="text-link" href="/advancement">Inspect frozen validation</Link><Link className="text-link" href="/workbench">Open the workbench</Link></div>
        </section>
      </article>
    </div>
  </div>;
}
