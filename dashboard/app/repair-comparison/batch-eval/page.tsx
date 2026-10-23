import Link from "next/link";
import historical from "@/lib/swebench-cohort15-eval.json";
import diagnostic from "@/lib/retrieval-development020.json";

export const metadata = {
  title: "Repository retrieval investigation | Kairos",
  description: "Inspect source provenance, issue-only context selection and the scope of recorded graph diagnostics.",
};

export default function BatchEvalPage() {
  return (
    <div className="page-shell reading-page">
      <header className="page-heading">
        <Link href="/repair-comparison">Back to repair comparisons</Link>
        <h1>Repository retrieval investigation</h1>
        <p>Compare how repository context is selected. Retrieval, patch generation and test-verified repair are separate measurements.</p>
      </header>
      <article className="prose">
        <section aria-labelledby="scope-title">
          <h2 id="scope-title">Source revisions must match</h2>
          <p>The existing four indexes contain installed Python packages. Their source revisions are not bound to the historical defect cases. This diagnostic is therefore excluded from benchmark scoring.</p>
          <p>The corrected runner uses issue text without annotated caller seeds, deterministic ranking and the same {diagnostic.token_budget_per_arm.toLocaleString()} model-token context cap for each arm. It records omitted chunks and performs no model or test execution.</p>
          <dl>
            <dt>Benchmark eligibility</dt><dd>Not eligible: case revisions are unbound</dd>
            <dt>Repair verification</dt><dd>Not executed by this retrieval diagnostic</dd>
            <dt>Timing scope</dt><dd>In-process ranking and token packing; MCP transport is measured separately</dd>
          </dl>
        </section>
        {/* Metric Stat Cards */}
        <section>
          <h2>Inspect the diagnostic cases</h2>
          <p>These identifiers are exposed development material. Symbol matches below are diagnostic observations, not recall scores on qualified source snapshots.</p>
          {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- Keyboard users must be able to scroll this labeled overflow region. */}
          <div className="pair-table-scroll" role="region" aria-label="Retrieval diagnostic cases" tabIndex={0}>
            <table className="pair-table">
              <thead><tr><th scope="col">Case</th><th scope="col">Lexical context tokens</th><th scope="col">Graph context tokens</th><th scope="col">Source qualification</th></tr></thead>
              <tbody>{diagnostic.cases.map((item) => <tr key={item.instance_id}>
                <th scope="row">{item.instance_id}</th>
                <td>{item.arms.lexical.context_tokens}</td><td>{item.arms.graph.context_tokens}</td><td>Revision not bound</td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>
        {/* Section 2: Failure Taxonomy */}
        <section>
          <h2>What the earlier capture measured</h2>
          <p>The preserved earlier receipt recorded {historical.summary.arm_b_codesage_mcp.localized_count}/{historical.cohort_size} target matches after supplying annotated caller names. It did not generate or execute repairs. Its ranks were assigned on a hit, and its fields named context tokens counted words.</p>
          <p>Those bytes remain preserved for audit. They do not establish a 100% repair rate, issue-only retrieval superiority or end-to-end MCP latency.</p>
        </section>
        {/* Section 3: Gravitas Invariants */}
        <section>
          <h2>What qualifies the next comparison</h2>
          <p>Bind each index to the case base revision, freeze issue-only retrieval and equal tokenizer budgets, then capture candidate patches and independent checks. Report actual ranked positions and keep all outcomes.</p>
          <Link href="/repair-comparison/codesage-mcp">Inspect the annotated context demonstration</Link>
        </section>
      </article>
    </div>
  );
}
