"use client";

import React, { useState } from "react";
import { Activity, Database, Server, RefreshCw } from "lucide-react";

export function GoIngestSimulator() {
  const [trafficRate, setTrafficRate] = useState<number>(24000); // events per sec
  const capacity = 10000;

  // Compute ring buffer utilization based on input rate vs Go consumer drain speed (50,000/sec)
  const drainRate = 50000;
  const utilizationPercent = Math.min(
    100,
    Math.max(5, Math.round((trafficRate / drainRate) * 45))
  );

  const isBackpressure = trafficRate > drainRate;
  const drops = isBackpressure ? Math.round((trafficRate - drainRate) * 0.12) : 0;
  const p99LatencyUs = Math.round(42 + (utilizationPercent / 100) * 140);

  return (
    <div className="rounded-lg border border-[#27272a] bg-[#121214] p-5 shadow-sm font-mono text-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#27272a] gap-2">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wide">
            Go Ingest Pipeline &amp; Lock-Free Ring Buffer Telemetry
          </h3>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-zinc-400">Go Runtime:</span>
          <span className="text-zinc-200 font-semibold">:8080 Active (Zero-CGO)</span>
        </div>
      </div>

      {/* Traffic Rate Slider */}
      <div className="py-4 border-b border-[#222226]">
        <div className="flex items-center justify-between mb-2">
          <label className="text-zinc-300 font-medium">
            Simulate Incoming Ingest Load:
          </label>
          <span className="text-indigo-400 font-bold text-sm">
            {trafficRate.toLocaleString()} events/sec
          </span>
        </div>
        <input
          type="range"
          min="5000"
          max="120000"
          step="5000"
          value={trafficRate}
          onChange={(e) => setTrafficRate(Number(e.target.value))}
          className="w-full h-1.5 bg-[#27272a] rounded-lg appearance-none cursor-pointer accent-indigo-500"
        />
        <div className="flex justify-between text-[10px] text-zinc-500 mt-1">
          <span>5k/s (Normal)</span>
          <span>50k/s (Sustained Go Drain Rate)</span>
          <span>120k/s (Backpressure Burst)</span>
        </div>
      </div>

      {/* Real-Time Telemetry Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 py-4">
        <div className="p-3 rounded border border-[#27272a] bg-[#18181b]">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
            Ring Buffer Fill
          </div>
          <div className={`text-lg font-bold ${utilizationPercent > 80 ? "text-amber-400" : "text-zinc-200"}`}>
            {utilizationPercent}%
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            {Math.round((utilizationPercent / 100) * capacity).toLocaleString()} / {capacity.toLocaleString()} slots
          </div>
        </div>

        <div className="p-3 rounded border border-[#27272a] bg-[#18181b]">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
            Drop Rate Under Load
          </div>
          <div className={`text-lg font-bold ${drops > 0 ? "text-red-400" : "text-emerald-400"}`}>
            {drops > 0 ? `${drops.toLocaleString()} drops/s` : "0.00%"}
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            {drops > 0 ? "Backpressure Shedding" : "Zero Data Loss"}
          </div>
        </div>

        <div className="p-3 rounded border border-[#27272a] bg-[#18181b]">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
            p99 Ingest Latency
          </div>
          <div className="text-lg font-bold text-indigo-400">
            {p99LatencyUs} &micro;s
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            Hot-path bounded buffer
          </div>
        </div>

        <div className="p-3 rounded border border-[#27272a] bg-[#18181b]">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
            Blob Storage Dedupe
          </div>
          <div className="text-lg font-bold text-emerald-400">
            3.42x
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            67.3% disk footprint saved
          </div>
        </div>
      </div>

      {/* Architecture Invariants Box */}
      <div className="mt-2 p-3.5 rounded border border-[#27272a] bg-[#18181b] space-y-2">
        <div className="flex items-center gap-1.5 text-zinc-300 font-semibold">
          <Database className="h-3.5 w-3.5 text-indigo-400" />
          <span>Single-Transaction Atomicity Guarantee</span>
        </div>
        <p className="text-zinc-400 leading-relaxed text-[11px]">
          Every event write executes within one ACID database transaction:
          <code className="text-zinc-200 bg-[#121214] px-1 py-0.5 rounded ml-1">
            INSERT INTO steps (run_id, seq...) ON CONFLICT (run_id, seq) DO NOTHING;
          </code>{" "}
          and synchronously writes to <code className="text-zinc-200 bg-[#121214] px-1 py-0.5 rounded">transactional_outbox</code>.
          This eliminates phantom writes, split-brain duplicates, and outbox desynchronization.
        </p>
      </div>
    </div>
  );
}
