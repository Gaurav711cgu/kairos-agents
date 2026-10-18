import Link from "next/link";
import batchReceipt from "@/lib/swebench-cohort15-eval.json";

export const metadata = {
  title: "SWE-bench Lite: 15-Case Comparative Evaluation (CodeSage MCP vs Baseline)",
  description: "Statistical evaluation comparing naive lexical retrieval against 2-hop topological Graph-RAG across 15 SWE-bench instances",
};

interface CaseResult {
  instance_id: string;
  repo: string;
  ground_truth_target: string;
  arm_a_baseline: {
    localized: boolean;
    rank: number;
    context_tokens: number;
    outcome: string;
  };
  arm_b_codesage_mcp: {
    localized: boolean;
    rank: number;
    context_tokens: number;
    latency_ms: number;
    call_chain: string;
    outcome: string;
  };
}

export default function BatchEvalPage() {
  const cases = batchReceipt.cases as CaseResult[];
  const summary = batchReceipt.summary;

  return (
    <div className="page-shell reading-page">
      <header className="page-heading">
        <span className="eyebrow">
          <Link href="/repair-comparison">← Back to Comparison Overview</Link>
        </span>
        <h1>
          SWE-bench Lite: 15-Case Batch Evaluation
          <br />
          <em>Arm A (Naive Lexical) vs. Arm B (CodeSage Graph-RAG MCP)</em>
        </h1>
        <p>
          Controlled statistical benchmark evaluating context starvation and localization recall
          across 15 standard candidate instances from SWE-bench Lite.
          Demonstrates how deterministic 2-hop topological call graphs overcome lexical starvation
          by delivering <strong>+{summary.delta.recall_gain_pct}%</strong> higher localization recall ({(summary.arm_b_codesage_mcp.recall_rate_pct / Math.max(1, summary.arm_a_baseline.recall_rate_pct)).toFixed(1)}x multiplier)
          within strictly bounded context windows (max 20 nodes).
        </p>
      </header>

      {/* Metric Stat Cards */}
      <section style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        gap: "16px",
        margin: "24px 0"
      }}>
        <div style={{
          background: "rgba(239, 68, 68, 0.08)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: "8px",
          padding: "16px"
        }}>
          <div style={{ fontSize: "0.8rem", color: "#f87171", textTransform: "uppercase" }}>Arm A: Baseline Recall</div>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#ef4444" }}>
            {summary.arm_a_baseline.recall_rate_pct}%
          </div>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
            {summary.arm_a_baseline.localized_count} / {batchReceipt.cohort_size} localized ({summary.arm_a_baseline.starvation_count} starved)
          </div>
        </div>

        <div style={{
          background: "rgba(16, 185, 129, 0.08)",
          border: "1px solid rgba(16, 185, 129, 0.3)",
          borderRadius: "8px",
          padding: "16px"
        }}>
          <div style={{ fontSize: "0.8rem", color: "#34d399", textTransform: "uppercase" }}>Arm B: CodeSage MCP Recall</div>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#10b981" }}>
            {summary.arm_b_codesage_mcp.recall_rate_pct}%
          </div>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
            {summary.arm_b_codesage_mcp.localized_count} / {batchReceipt.cohort_size} localized ({summary.arm_b_codesage_mcp.starvation_count} starved)
          </div>
        </div>

        <div style={{
          background: "rgba(99, 102, 241, 0.08)",
          border: "1px solid rgba(99, 102, 241, 0.3)",
          borderRadius: "8px",
          padding: "16px"
        }}>
          <div style={{ fontSize: "0.8rem", color: "#818cf8", textTransform: "uppercase" }}>Absolute Recall Gain</div>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#6366f1" }}>
            +{summary.delta.recall_gain_pct}%
          </div>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
            {(summary.arm_b_codesage_mcp.recall_rate_pct / Math.max(1, summary.arm_a_baseline.recall_rate_pct)).toFixed(1)}x increase over naive lexical baseline ({summary.arm_b_codesage_mcp.recall_rate_pct}% vs {summary.arm_a_baseline.recall_rate_pct}%)
          </div>
        </div>

        <div style={{
          background: "rgba(245, 158, 11, 0.08)",
          border: "1px solid rgba(245, 158, 11, 0.3)",
          borderRadius: "8px",
          padding: "16px"
        }}>
          <div style={{ fontSize: "0.8rem", color: "#fbbf24", textTransform: "uppercase" }}>Mean Retrieval Latency</div>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#f59e0b" }}>
            {summary.arm_b_codesage_mcp.mean_latency_ms} ms
          </div>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
            Empirical 2-hop traversal over {batchReceipt.provenance.total_graph_edges_indexed.toLocaleString()} SQLite edges
          </div>
        </div>
      </section>

      <div className="article-layout">
        <aside className="article-index">
          <span className="eyebrow">On this page</span>
          <a href="#matrix">15-Case Matrix</a>
          <a href="#taxonomy">Why Agents Starve</a>
          <a href="#invariants">Gravitas Invariants</a>
          <Link href="/repair-comparison">All 19 Cases Matrix</Link>
          <Link href="/repair-comparison/codesage-mcp">pytest-5221 Deep Dive</Link>
        </aside>

        <article className="prose">
          {/* Section 1: Detailed 15-Case Cohort Matrix */}
          <section id="matrix">
            <h2>Controlled Cohort Results (15 Instances)</h2>
            <div className="pair-table-scroll" role="region" aria-label="15-case comparison">
              <table className="pair-table" style={{ minWidth: 0, fontSize: "0.85rem" }}>
                <thead>
                  <tr>
                    <th scope="col">Instance ID</th>
                    <th scope="col">Repository</th>
                    <th scope="col">Target Symbol</th>
                    <th scope="col" style={{ color: "#ef4444" }}>Arm A: Baseline</th>
                    <th scope="col" style={{ color: "#10b981" }}>Arm B: CodeSage MCP</th>
                    <th scope="col">Tokens (A vs B)</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.instance_id}>
                      <th scope="row" style={{ fontFamily: "monospace" }}>
                        {c.instance_id}
                      </th>
                      <td>{c.repo.split("/")[1]}</td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                        {c.ground_truth_target.split("::")[1]}
                      </td>
                      <td>
                        {c.arm_a_baseline.localized ? (
                          <span className="outcome-badge badge-pass">Localized</span>
                        ) : (
                          <span className="outcome-badge badge-fail" title="Context starvation (0 target regions)">
                            Starvation
                          </span>
                        )}
                      </td>
                      <td>
                        {c.arm_b_codesage_mcp.localized ? (
                          <span className="outcome-badge badge-pass" title={c.arm_b_codesage_mcp.call_chain}>
                            2-Hop Graph
                          </span>
                        ) : (
                          <span className="outcome-badge badge-fail" title="Unresolved in 2 hops">
                            Unresolved
                          </span>
                        )}
                      </td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                        {c.arm_a_baseline.context_tokens} → <strong>{c.arm_b_codesage_mcp.context_tokens}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Section 2: Failure Taxonomy */}
          <section id="taxonomy">
            <h2>Why Naive Coding Agents Starve on SWE-bench</h2>
            <p>
              In real-world software defects, issue reports describe <strong>symptoms, user commands, or CLI flags</strong>
              (e.g., <code>pytest --fixtures</code> or <code>socket.error wrapped inappropriately</code>).
              They rarely mention the private internal helper functions where the actual bug resides
              (e.g., <code>_showfixtures_main</code>, <code>_diff_text</code>, or <code>_endpoint_from_view_func</code>).
            </p>
            <ul>
              <li>
                <strong>Lexical & Vector Search Breakdown:</strong> BM25 and cosine distance match words in the prompt against function names.
                Because the private target symbol is unmentioned, lexical rankers return irrelevant files or abort with 0 regions.
              </li>
              <li>
                <strong>Topological Resolution Advantage:</strong> CodeSage MCP identifies the high-level entry symbol
                (e.g., <code>showfixtures</code>) and immediately expands its directed call chain to find the actual defect site,
                bypassing semantic drift entirely.
              </li>
            </ul>
          </section>

          {/* Section 3: Gravitas Invariants */}
          <section id="invariants">
            <h2>Gravitas Reliability Invariants</h2>
            <ul>
              {batchReceipt.gravitas_invariants_satisfied.map((inv: string, idx: number) => (
                <li key={idx}>{inv}</li>
              ))}
            </ul>
          </section>
        </article>
      </div>
    </div>
  );
}
