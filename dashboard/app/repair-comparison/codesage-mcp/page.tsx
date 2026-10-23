import Link from "next/link";
import historical from "@/lib/swebench-pytest5221-mcp.json";

export const metadata = {
  title: "CodeSage context demonstration | Kairos",
  description: "An annotated repository-context demonstration with an explicitly handwritten example patch.",
};

export default function CodeSageMCPPage() {
  const capture = historical.codesage_augmented;
  return (
    <div className="page-shell reading-page">
      <header className="page-heading">
        <Link href="/repair-comparison">Back to repair comparisons</Link>
        <h1>CodeSage context demonstration</h1>
        <p>Inspect the repository context and a handwritten example change for <code>{historical.task_id}</code>.</p>
      </header>
      <article className="prose">
        {/* Section 1: Comparison Card */}
        <section>
          <h2>What was executed</h2>
          <p>The demonstration supplied the target symbol <code>{capture.target_symbol}</code> and retrieved its repository context. It parsed a separate handwritten example function. It did not apply a model-generated patch or run the defect regression.</p>
          <dl><dt>Patch origin</dt><dd>Handwritten example</dd><dt>Target selection</dt><dd>Annotated symbol supplied</dd><dt>Verified repair</dt><dd>Not established by this capture</dd></dl>
        </section>
        <section>
          <h2>Example change</h2>
          <p>This preserved diff is available for inspection. Syntax of a sample function does not establish that this diff applies or repairs the historical repository.</p>
          <pre tabIndex={0} aria-label="Handwritten example patch"><code>{capture.patch_diff}</code></pre>
        </section>
        <section>
          <h2>Current protocol checks</h2>
          <p>The updated stdio client negotiates initialization, uses request deadlines, validates response identifiers and reaps its owned child after transport failure. The server requires initialization and rejects an unavailable graph instead of returning another repository.</p>
          <p>Protocol checks and context inspection are separate from repair-effectiveness evaluation.</p>
          <Link href="/repair-comparison/batch-eval">Inspect retrieval provenance and scope</Link>
        </section>
      </article>
    </div>
  );
}
