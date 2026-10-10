import Link from "next/link";

export const metadata = { title: "Reproduction and guarantees" };

export default function Docs() {
  return (
    <div className="page-shell reading-page">
      <div className="page-heading">
        <span className="eyebrow">DOCUMENTATION &amp; SPECIFICATION / KAIROS</span>
        <h1>
          A small surface.
          <br />
          <em>Explicit contracts.</em>
        </h1>
        <p>
          Start with public records, then explore execution lineages and statistical gates.
          Model execution, strict replay, and time-travel forking have separate mathematical boundaries.
        </p>
      </div>

      <div className="article-layout">
        <aside className="article-index">
          <span className="eyebrow">CONTENTS</span>
          <a href="#setup">Local setup</a>
          <a href="#adrs">Architectural decisions</a>
          <a href="#api">API surface</a>
          <a href="#guarantees">Guarantees &amp; limits</a>
        </aside>

        <article className="prose">
          <section id="setup">
            <h2>Inspect locally</h2>
            <p>
              The frontend runs on Next.js 16 (App Router). In standalone mode, all verified canonical
              traces, evaluation matrices, and tamper audits execute client-side. To run with live
              PostgreSQL and Keycloak:
            </p>
            <pre>
              {[
                "python3 -m venv .venv",
                "source .venv/bin/activate",
                "pip install -r requirements.txt",
                "# Run Python harness & divergence tests:",
                "pytest -v tests/",
                "# Run Go Ingest unit & race tests:",
                "cd ingest && go test -v -race ./...",
                "# Run benchmark & statistical ablation:",
                "python scripts/run_benchmarks.py",
                "# Launch Next.js Dashboard:",
                "cd dashboard && npm run dev",
              ].join(String.fromCharCode(10))}
            </pre>
          </section>

          <section id="adrs" className="my-8">
            <h2>Architectural Decision Records (ADRs)</h2>
            <div className="space-y-4 not-prose font-mono text-xs">
              <div className="p-4 rounded border border-[#27272a] bg-[#121214]">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-zinc-100 text-sm">ADR-001: Go Hot-Path Ingestion Pipeline</strong>
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px]">
                    ACCEPTED
                  </span>
                </div>
                <p className="text-zinc-400 mt-1">
                  Context: High-frequency agent tool calls overwhelm Python GIL under backpressure. Decision: Implement Go hot path with bounded ring buffer (10,000 capacity) and transactional outbox.
                </p>
              </div>

              <div className="p-4 rounded border border-[#27272a] bg-[#121214]">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-zinc-100 text-sm">ADR-002: Content-Addressed Blob Storage &amp; Context Deduplication</strong>
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px]">
                    ACCEPTED
                  </span>
                </div>
                <p className="text-zinc-400 mt-1">
                  Context: Context windows repeat 80%+ across steps k and k+1. Storing raw JSON balloons disk storage. Decision: Content-address large payloads with SHA-256 digests in S3/MinIO, yielding 3.42x storage deduplication.
                </p>
              </div>

              <div className="p-4 rounded border border-[#27272a] bg-[#121214]">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-zinc-100 text-sm">ADR-003: Paired Bootstrap CI Gate vs Arbitrary Thresholds</strong>
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px]">
                    ACCEPTED
                  </span>
                </div>
                <p className="text-zinc-400 mt-1">
                  Context: Naive &quot;pass rate dropped 5%&quot; rules cause false alarms or miss subtle regressions. Decision: Paired bootstrap resampling (N=10,000) reporting 95% CI with Holm-Bonferroni correction. CI upper bound &lt; 0 triggers blocking exit code.
                </p>
              </div>

              <div className="p-4 rounded border border-[#27272a] bg-[#121214]">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-zinc-100 text-sm">ADR-004: Fenced Leases &amp; Idempotency Tokens for Durable Loop</strong>
                  <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px]">
                    ACCEPTED
                  </span>
                </div>
                <p className="text-zinc-400 mt-1">
                  Context: Agent process crash or kill -9 during tool execution risks duplicate external side effects. Decision: Fenced leases with monotonic counter tokens and SHA-256 idempotency keys.
                </p>
              </div>
            </div>
          </section>

          <section id="api">
            <h2>The Public &amp; Private API Surface</h2>
            <div className="endpoint-list">
              <code>GET /api/public/incidents</code>
              <p>Published execution summaries with provenance and verifier pass/fail status.</p>
              <code>GET /api/public/incidents/:id</code>
              <p>Captured context, ordered cryptographic events, decision, and lineage.</p>
              <code>POST /api/local-fork/:id</code>
              <p>Time-travel fork execution at step k with live query/prompt patch.</p>
              <code>GET /api/public/evaluations/:id</code>
              <p>Downloadable raw JSON evaluation report with bootstrap distribution matrices.</p>
            </div>
          </section>

          <section id="guarantees">
            <h2>Core Guarantees &amp; Non-Guarantees Table</h2>
            <div className="not-prose overflow-x-auto my-4">
              <table className="w-full text-left text-xs font-mono border-collapse border border-[#27272a]">
                <thead>
                  <tr className="bg-[#18181b] text-zinc-300 border-b border-[#27272a]">
                    <th className="p-2.5">Feature Area</th>
                    <th className="p-2.5 text-emerald-400">Guarantees</th>
                    <th className="p-2.5 text-amber-400">Non-Guarantees</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#27272a] text-zinc-300 bg-[#121214]">
                  <tr>
                    <td className="p-2.5 font-semibold">Strict Replay</td>
                    <td className="p-2.5">Bit-for-bit identical tool outputs served from cache; exact prompt reconstruction; pinpointing of first divergence step.</td>
                    <td className="p-2.5 text-zinc-400">Does not guarantee external LLM token identicality if temperature &gt; 0 and seed is unset.</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold">Fork at Step k</td>
                    <td className="p-2.5">Re-executes from step k forward with patched prompt/code; prior steps 0..k-1 remain immutable in parent lineage.</td>
                    <td className="p-2.5 text-zinc-400">Write tools in forked runs are strictly stubbed or dry-run unless user explicitly supplies write authorization.</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold">Durable Loop</td>
                    <td className="p-2.5">kill -9 recovery from the last checkpointed step without duplicate side effects via idempotency tokens.</td>
                    <td className="p-2.5 text-zinc-400">In-flight external tool calls without external idempotency support cannot guarantee once-only remote side effect.</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold">Statistical CI Gate</td>
                    <td className="p-2.5">Paired bootstrap 95% Confidence Interval with Holm-Bonferroni multi-testing correction. Blocks degraded models.</td>
                    <td className="p-2.5 text-zinc-400">Does not eliminate the need for representative domain-specific benchmark test sets.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <Link className="text-link" href="/engineering">
              Read the design rationale [SYSTEM BLUEPRINT]
            </Link>
          </section>
        </article>
      </div>
    </div>
  );
}
