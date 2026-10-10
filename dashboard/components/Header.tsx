"use client";

import React from "react";
import { Activity, Database, GitFork, ShieldCheck } from "lucide-react";
import { INGEST_TELEMETRY } from "@/lib/sample-data";

export default function Header({
  activeRunMode,
  setActiveRunMode,
}: {
  activeRunMode: "baseline" | "candidate" | "forked";
  setActiveRunMode: (mode: "baseline" | "candidate" | "forked") => void;
}) {
  return (
    <header className="border-b border-[#27272a] bg-[#121214] px-6 py-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        {/* Title and Branding */}
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded border border-[#3f3f46] bg-[#18181b] text-xs font-mono font-bold tracking-wider text-zinc-100">
              KR
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-zinc-100 font-mono">
                KAIROS FOR AGENTS
              </h1>
              <p className="text-xs text-zinc-400">
                Immutable Event Log, Step-k Divergence Detector & Statistical Regression Gate
              </p>
            </div>
          </div>
        </div>

        {/* Trace Selector Buttons */}
        <div className="flex items-center gap-2 bg-[#18181b] p-1 rounded-md border border-[#27272a]">
          <button
            onClick={() => setActiveRunMode("baseline")}
            className={`px-3 py-1.5 text-xs font-mono rounded transition-colors ${
              activeRunMode === "baseline"
                ? "bg-zinc-100 text-zinc-950 font-semibold shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Baseline Run (Verified)
          </button>
          <button
            onClick={() => setActiveRunMode("candidate")}
            className={`px-3 py-1.5 text-xs font-mono rounded transition-colors ${
              activeRunMode === "candidate"
                ? "bg-amber-400 text-zinc-950 font-semibold shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Candidate Trace (Diverged)
          </button>
          <button
            onClick={() => setActiveRunMode("forked")}
            className={`px-3 py-1.5 text-xs font-mono rounded transition-colors ${
              activeRunMode === "forked"
                ? "bg-emerald-500 text-zinc-950 font-semibold shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Forked Trace (Patched @ k=2)
          </button>
        </div>

        {/* Live Go Ingest Status Badges */}
        <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded border border-[#27272a] bg-[#18181b] text-zinc-300">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-zinc-400">Go Ingest:</span>
            <span className="text-zinc-200 font-semibold">:8080 Active</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-[#27272a] bg-[#18181b] text-zinc-300">
            <Activity className="h-3.5 w-3.5 text-zinc-400" />
            <span className="text-zinc-400">Ring Buffer Drops:</span>
            <span className="text-emerald-400 font-semibold">0.00%</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-[#27272a] bg-[#18181b] text-zinc-300">
            <Database className="h-3.5 w-3.5 text-zinc-400" />
            <span className="text-zinc-400">Blob Dedupe:</span>
            <span className="text-indigo-400 font-semibold">{INGEST_TELEMETRY.blobDedupeRatio}x</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-[#27272a] bg-[#18181b] text-zinc-300">
            <ShieldCheck className="h-3.5 w-3.5 text-zinc-400" />
            <span className="text-zinc-400">Outbox:</span>
            <span className="text-emerald-400 font-semibold">100% Synced</span>
          </div>
        </div>
      </div>
    </header>
  );
}
