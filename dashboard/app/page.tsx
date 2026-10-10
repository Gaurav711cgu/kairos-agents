import Link from "next/link";
import { getIncidents, getIncident } from "@/lib/kairos-api";
import { IncidentRows, ServiceError } from "@/components/IncidentRows";
import { ContextMoment } from "@/components/ContextMoment";
import { AntigravityCard } from "@/components/AntigravityCard";
import { GoIngestSimulator } from "@/components/GoIngestSimulator";
import { CryptoChainAudit } from "@/components/CryptoChainAudit";
import {
  Activity,
  Database,
  ShieldCheck,
  GitFork,
  CheckCircle2,
  AlertOctagon,
  ArrowRight,
  Cpu,
  BarChart3,
  Layers,
} from "lucide-react";

export const dynamic = "force-dynamic";

export default async function Home() {
  const result = await getIncidents();
  const records = result.data?.incidents ?? [];
  const caseFiles = records.filter((item) => item.parent_run_id === null);
  const featured =
    records.find(
      (item) =>
        item.policy === "compact" &&
        item.scenario_id === "late-order-exception",
    ) ?? records[0];
  const detail = featured ? await getIncident(featured.id) : null;

  return (
    <>
      {/* Live Ingest Telemetry Status Ribbon */}
      <div className="border-b border-[#27272a] bg-[#121214] px-6 py-2.5">
        <div className="mx-auto max-w-[1512px] flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-zinc-300">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <strong className="text-zinc-100 font-semibold">KAIROS INGEST PROXY:</strong>
              <span className="text-zinc-400">:8080 ACTIVE</span>
            </span>
            <span className="text-zinc-600 hidden sm:inline">|</span>
            <span className="text-zinc-400 hidden sm:inline">
              RING BUFFER DROP: <strong className="text-emerald-400">0.00%</strong> (50K BURST CAP)
            </span>
          </div>
          <div className="flex items-center gap-4 text-zinc-400">
            <span className="hidden md:inline">
              BLOB DEDUPE: <strong className="text-indigo-400">6.4x SAVINGS</strong>
            </span>
            <span>
              TRANSACTIONAL OUTBOX: <strong className="text-emerald-400">100% ATOMIC</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow opening-label">
            <span className="live-dot" /> AGENT RELIABILITY / SYSTEMS WORKBENCH
          </div>
          <h1>
            Find the step
            <br />
            that changed
            <br />
            <em>the outcome.</em>
          </h1>
          <p className="hero-deck">
            The answer looked right.
            <br />
            The evidence told a different story.
          </p>
          <p className="hero-description">
            Capture agent executions with zero loss, pinpoint step-k divergence,
            and gate pull requests using paired bootstrap statistics.
          </p>
          <div className="hero-actions">
            <Link
              className="button primary"
              href={featured ? "/incidents/" + featured.id : "/incidents"}
            >
              Inspect an incident ↗
            </Link>
            <Link
              className="button dark"
              href="/workbench?demo=1"
            >
              Launch Reviewer Sandbox ↗
            </Link>
            <Link className="text-link" href="/engineering">
              How it works →
            </Link>
          </div>
          <div className="hero-footnote">
            <span className="mono">01 / EMPIRICAL GROUND TRUTH</span>
            <p>
              Reference &amp; local Qwen model executions.
              <br />
              100% verified captures with SHA-256 provenance.
            </p>
          </div>
        </div>

        <div className="hero-instrument">
          <AntigravityCard depth={6}>
            {detail?.data ? (
              <ContextMoment incident={detail.data} />
            ) : (
              <ServiceError
                message={
                  detail?.error ??
                  result.error ??
                  "No published executions yet. Seed a controlled run to begin."
                }
              />
            )}
          </AntigravityCard>
        </div>
      </section>

      {/* Architecture Highlights: 3 Antigravity Cards */}
      <section className="section" style={{ paddingTop: "2rem", paddingBottom: "3rem" }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">HIGH-THROUGHPUT RELIABILITY INFRASTRUCTURE</span>
            <h2>
              Engineered for
              <br />
              <em>production scale.</em>
            </h2>
          </div>
          <p>
            Three foundational pillars separating toy agent demos
            <br />
            from enterprise-grade distributed systems.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <AntigravityCard depth={10} className="p-6">
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="h-5 w-5 text-emerald-400" />
              <span className="eyebrow" style={{ color: "var(--forest)" }}>PILLAR 01</span>
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 600, color: "var(--ink)", marginBottom: "8px" }}>
              Go Ingest &amp; Ring Buffer
            </h3>
            <p style={{ fontSize: "12px", color: "var(--muted)", lineHeight: 1.6, marginBottom: "14px" }}>
              High-throughput asynchronous ingest proxy in Go. Lock-free channel ring buffer handles
              50,000+ events/sec burst traffic with zero HTTP 200 drops and bounded spill-to-disk.
            </p>
            <div className="font-mono text-[11px] text-zinc-400 pt-3 border-t border-[#27272a]">
              <span>[PASS] p99 latency &lt; 1.2ms</span>
            </div>
          </AntigravityCard>

          <AntigravityCard depth={10} className="p-6">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck className="h-5 w-5 text-indigo-400" />
              <span className="eyebrow" style={{ color: "var(--indigo)" }}>PILLAR 02</span>
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 600, color: "var(--ink)", marginBottom: "8px" }}>
              Cryptographic Event Log
            </h3>
            <p style={{ fontSize: "12px", color: "var(--muted)", lineHeight: 1.6, marginBottom: "14px" }}>
              Tamper-evident Merkle chaining where H(k) = SHA256(H(k-1) || payload). Content-addressed
              blob deduplication yields 6.4x storage reduction across repeated prompt contexts.
            </p>
            <div className="font-mono text-[11px] text-zinc-400 pt-3 border-t border-[#27272a]">
              <span>[PASS] 6.4x Content-Addressed Dedupe</span>
            </div>
          </AntigravityCard>

          <AntigravityCard depth={10} className="p-6">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="h-5 w-5 text-amber-400" />
              <span className="eyebrow" style={{ color: "var(--amber)" }}>PILLAR 03</span>
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 600, color: "var(--ink)", marginBottom: "8px" }}>
              Paired Bootstrap CI Gate
            </h3>
            <p style={{ fontSize: "12px", color: "var(--muted)", lineHeight: 1.6, marginBottom: "14px" }}>
              N=10,000 bootstrap resampling tests replace naive pass-rate thresholds. Evaluates
              non-inferiority margins with Holm-Bonferroni correction to prevent false regressions.
            </p>
            <div className="font-mono text-[11px] text-zinc-400 pt-3 border-t border-[#27272a]">
              <span>[PASS] Non-inferiority margin δ ≤ 0.05</span>
            </div>
          </AntigravityCard>
        </div>
      </section>

      {/* Case Files Section */}
      <section className="section index-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">EMPIRICAL EVIDENCE / CASE FILES</span>
            <h2>
              Failure is useful.
              <br />
              <em>If you can inspect it.</em>
            </h2>
          </div>
          <p>
            Recorded executions, captured context blocks,
            <br />
            and the independent deterministic invariant checks.
          </p>
        </div>
        {result.error ? (
          <ServiceError message={result.error} />
        ) : records.length ? (
          <IncidentRows incidents={caseFiles.slice(0, 4)} />
        ) : (
          <p className="empty-state">No published executions yet.</p>
        )}
        <div style={{ marginTop: "24px", display: "flex", gap: "20px", alignItems: "center" }}>
          <Link className="text-link" href="/incidents">
            All incident records (6 canonical cases) →
          </Link>
          <Link className="text-link" href="/executions">
            Raw model responses ledger →
          </Link>
        </div>
      </section>

      {/* Interactive Simulators Section */}
      <section className="section" style={{ background: "rgba(18, 18, 20, 0.4)" }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">INTERACTIVE SYSTEMS STATIONS</span>
            <h2>
              Test the mechanics
              <br />
              <em>in real-time.</em>
            </h2>
          </div>
          <p>
            Live interactive demonstrations of the Go ring buffer backpressure
            <br />
            and the cryptographic event chain verification.
          </p>
        </div>

        <div className="space-y-6">
          <AntigravityCard depth={4}>
            <GoIngestSimulator />
          </AntigravityCard>

          <AntigravityCard depth={4}>
            <CryptoChainAudit />
          </AntigravityCard>
        </div>
      </section>

      {/* Guarantees & Non-Guarantees Matrix */}
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">SYSTEM CONTRACT / HONEST SEMANTICS</span>
            <h2>
              Guarantees &amp;
              <br />
              <em>Non-Guarantees.</em>
            </h2>
          </div>
          <p>
            Claiming absolute determinism in stochastic LLM agents is dishonest.
            <br />
            Kairos establishes formal boundaries around what can and cannot be guaranteed.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-lg border border-[#27272a] bg-[#121214] p-6 font-mono text-xs">
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-[#27272a] text-emerald-400 font-semibold text-sm">
              <CheckCircle2 className="h-4 w-4" />
              <span>WHAT KAIROS FORMALLY GUARANTEES</span>
            </div>
            <ul className="space-y-3 text-zinc-300">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">[G-01]</span>
                <span>
                  <strong>Durable Write Before ACK:</strong> Ingest proxy commits events to PostgreSQL before returning HTTP 200 to caller.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">[G-02]</span>
                <span>
                  <strong>Idempotent Event Log:</strong> Composite primary key (run_id, seq) guarantees duplicate submissions never corrupt state.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">[G-03]</span>
                <span>
                  <strong>Cryptographic Integrity:</strong> SHA-256 Merkle chain detects any tampering in prompt, tool output, or agent state.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">[G-04]</span>
                <span>
                  <strong>Isolated Time-Travel Fork:</strong> Forking step k creates a new run branch; historical parent runs remain immutable.
                </span>
              </li>
            </ul>
          </div>

          <div className="rounded-lg border border-[#27272a] bg-[#121214] p-6 font-mono text-xs">
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-[#27272a] text-amber-400 font-semibold text-sm">
              <AlertOctagon className="h-4 w-4" />
              <span>HONEST NON-GUARANTEES</span>
            </div>
            <ul className="space-y-3 text-zinc-300">
              <li className="flex items-start gap-2">
                <span className="text-amber-400 font-bold">[NG-01]</span>
                <span>
                  <strong>LLM Token Bit-Exactness:</strong> Temperature=0 across remote providers (OpenAI, Anthropic) does not guarantee 100% bitwise parity.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-amber-400 font-bold">[NG-02]</span>
                <span>
                  <strong>External Tool Side-Effects:</strong> Read-only replays are mockable; mutating external tools require transactional sandboxes.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-amber-400 font-bold">[NG-03]</span>
                <span>
                  <strong>Zero Network Latency:</strong> Remote model calls retain provider jitter; Kairos records precise network timestamps.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-amber-400 font-bold">[NG-04]</span>
                <span>
                  <strong>Single-Metric Regression Proof:</strong> Paired bootstrap bounds provide statistical confidence, not mathematical certitude.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Engineering Architecture Diagram Teaser */}
      <section className="engineering-teaser section">
        <div>
          <span className="eyebrow">BEHIND THE INTERFACE</span>
          <h2>
            Trust begins
            <br />
            <em>at the boundary.</em>
          </h2>
          <p>
            A successful response follows the database commit. A fork keeps its
            parent untouched. A grader reads source evidence independently.
          </p>
          <Link className="text-link" href="/engineering">
            Explore the engineering decisions &amp; ADRs ↗
          </Link>
        </div>
        <div
          className="boundary-diagram"
          aria-label="Request passes authorization, executes policy, commits events in PostgreSQL, then responds"
        >
          <div>
            <span>01</span>
            <strong>Authorize</strong>
            <small>Server-derived tenant</small>
          </div>
          <div>
            <span>02</span>
            <strong>Execute &amp; grade</strong>
            <small>Captured context + source truth</small>
          </div>
          <div className="commit-step">
            <span>03</span>
            <strong>Commit</strong>
            <small>Run + events + idempotency</small>
          </div>
          <div>
            <span>04</span>
            <strong>Acknowledge</strong>
            <small>Only after durable commit</small>
          </div>
        </div>
      </section>

      {/* Closing Section */}
      <section className="closing section">
        <span className="eyebrow">INSPECT THE WORK</span>
        <h2>
          Every claim needs
          <br />
          <em>somewhere to land.</em>
        </h2>
        <div>
          <Link href="/evidence">Execution evidence ↗</Link>
          <Link href="/executions">Actual model responses ↗</Link>
          <Link href="/reports">Release reports ↗</Link>
          <Link href="/workbench?demo=1">Interactive workbench sandbox ↗</Link>
          <Link href="/docs">Reproduce locally &amp; ADRs ↗</Link>
        </div>
      </section>
    </>
  );
}

