import { CurrentResult } from "@/components/CurrentResult";
import Link from "next/link";
import currentCohort from "@/lib/study007-cohort.json";

export const metadata = { title: "Your first investigation" };

const inspection = [
  { title: "Choose a completed investigation", action: "Open a case that matches the behavior you want to inspect.", system: "Kairos loads the original issue, source revision and captured artifacts. It checks their hashes and references.", result: "You receive an inspectable trace immediately, without local setup." },
  { title: "Understand the proposed change", action: "Read the issue, then open the source and patch views.", system: "Original source stays separate from the proposed candidate. Before and after views highlight changed lines.", result: "You can see what changed and where. A plausible patch still has to pass checks." },
  { title: "Read the observed checks", action: "Open the check step. Read the verdict, test count and failures.", system: "Registered checks run independently of model prose. Missing tests, environment errors and failed existing tests prevent a verified repair.", result: "You learn whether this candidate earned a repair outcome. The verdict includes the captured test output." },
  { title: "Compare and take the evidence", action: "Compare strategies, then download the patch and evidence bundle.", system: "Kairos shows additional calls, captured tokens and timing. Downloads preserve the captured bytes and their integrity checks.", result: "You receive a patch for human review and an inspectable record. Downloads do not change your repository." },
];

const execution = [
  { title: "Sign in and select a registered case", text: "A live local installation checks your workspace and role. Operators select a registered case and versioned configuration. Arbitrary repository URLs are not accepted." },
  { title: "Submit once; follow actual progress", text: "The browser saves a stable command identity. PostgreSQL commits the receipt before acknowledging it. A lost acknowledgement can be retried with the same identity. Queue limits produce explicit rejections." },
  { title: "Inspect, propose and check", text: "When the pinned inference server and worker are running, the worker claims one job. It captures source and context, proposes bounded edits and runs registered checks in disposable containers. The live control plane starts with inference off." },
  { title: "Receive the observed outcome", text: "A verified repair requires the regression and relevant existing tests to pass. You may instead receive failed checks, an invalid patch, an environment failure, a timeout or an unknown dispatch. Each outcome includes the captured steps, checks and stop reason." },
];

export default function HowItWorks() {
  return <div className="page-shell reading-page">
    <header className="page-heading"><span className="eyebrow">Start here</span><h1>From a defect<br /><em>to an inspectable result.</em></h1><p>What you do, what Kairos runs and what you receive. Begin with a saved investigation; use the private workbench for a new attempt.</p></header>
      <CurrentResult />
    <div className="article-layout">
      <aside className="article-index"><span className="eyebrow">Your path</span><a href="#inspect">Inspect a saved result</a><a href="#run">Run a new attempt</a><a href="#controls">Other actions</a><a href="#outcomes">Did it work?</a></aside>
      <article className="prose">
        <section id="inspect"><h2>Inspect a saved result.</h2><p>This is the first path for a reviewer. Open each step for the expected behavior.</p>
          {inspection.map((step, index) => <details className="journey-step" key={step.title}><summary><span aria-hidden="true">{index + 1}. </span>{step.title}</summary><div><p><strong>You:</strong> {step.action}</p><p><strong>Kairos:</strong> {step.system}</p><p><strong>Result:</strong> {step.result}</p></div></details>)}
          <div className="investigation-actions"><Link className="text-link" href={`/investigations/${currentCohort.featured_id}`}>Inspect the development repair</Link><Link className="text-link" href="/investigations">Browse all investigations</Link></div>
        </section>
        <section id="run"><h2>Run a new attempt.</h2><p>The local workbench runs a registered case through the model and independent checks. Its setup guide connects the authenticated stack, prepared source, pinned model and worker.</p>
          <ol>{execution.map(step => <li key={step.title}><h3>{step.title}</h3><p>{step.text}</p></li>)}</ol>
          <Link className="text-link" href="/workbench">Open the workbench</Link>
          <aside className="scope-note"><h3>Browser-verified live execution</h3><p>A browser-submitted Django development investigation completed in 35.1 seconds. The local model made two calls, proposed one candidate and passed all four registered tests. The tested path included sign-in, submission, progress, source/context inspection, evidence downloads, replay and logout.</p><p>This is an exposed development case with an issue-provided repair hint, kept separate from frozen validation.</p><a className="text-link" href="/live-workflow/receipt.json" download>Download live workflow receipt</a></aside>
        </section>
        <section id="controls"><h2>Manage an investigation.</h2>
          <p><strong>Cancel:</strong> stop queued work or fence later commits. Already-started inference cannot be undone.</p>
          <p><strong>Fork:</strong> start a fresh attempt linked to its parent. It has its own receipt and budgets.</p>
          <p><strong>Replay:</strong> inspect saved steps. Replay sends no model calls and executes no tools.</p>
          <p><strong>Publish:</strong> an administrator makes a private record publicly inspectable. Other roles cannot publish.</p>
          <p><strong>Retry:</strong> reuse the same command identity after an uncertain submission. An unknown model dispatch is preserved without being sent again.</p>
        </section>
        <section id="outcomes"><h2>What you receive.</h2><p>An inspection gives you the original source, proposed change, check results and downloadable evidence. A new investigation returns its observed outcome. Kairos marks a repair verified after the registered regression and relevant existing tests pass.</p><p>The recorded Django repair passed its declared checks. Earlier frozen local-model studies were 0/10 (v7, five qualified Django and pytest cases), 0/10 (v5) and 0/36 (older study); the current hosted-model results are on the Benchmark page. Both unsuccessful comparisons remain available beside the earned demonstrations.</p><p>Browser journeys exercise the user actions, roles, errors, downloads, keyboard controls and mobile layout. Their receipts record the actual interaction results. The separate repair study reports each model attempt and its verification outcome.</p><div className="investigation-actions"><Link className="text-link" href="/follow-up">Read every follow-up outcome</Link><Link className="text-link" href="/docs">Run the checks yourself</Link><Link className="text-link" href="/repair-workflow">Inspect the repair workflow follow-up</Link><Link className="text-link" href="/repair-investigation">Follow the completed pytest investigation</Link></div></section>
      </article>
    </div>
  </div>;
}
