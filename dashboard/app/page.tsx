"use client";

import React, { useState } from "react";
import Header from "@/components/Header";
import TimelineScrubber from "@/components/TimelineScrubber";
import ContextDiffView from "@/components/ContextDiffView";
import StatisticalDistributionVisualizer from "@/components/StatisticalDistributionVisualizer";
import TimeTravelForkModal from "@/components/TimeTravelForkModal";
import { BASELINE_RUN, CANDIDATE_DIVERGENT_RUN, FORKED_RUN } from "@/lib/sample-data";
import { AgentRun } from "@/lib/types";

export default function Home() {
  const [activeRunMode, setActiveRunMode] = useState<"baseline" | "candidate" | "forked">("candidate");
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(2);
  const [forkModalOpen, setForkModalOpen] = useState<boolean>(false);
  const [forkStepTarget, setForkStepTarget] = useState<number>(2);

  const getActiveRun = (): AgentRun => {
    switch (activeRunMode) {
      case "baseline":
        return BASELINE_RUN;
      case "candidate":
        return CANDIDATE_DIVERGENT_RUN;
      case "forked":
        return FORKED_RUN;
    }
  };

  const activeRun = getActiveRun();
  const currentStep = activeRun.steps[Math.min(currentStepIndex, activeRun.steps.length - 1)];
  const baselineStep = BASELINE_RUN.steps[Math.min(currentStepIndex, BASELINE_RUN.steps.length - 1)];

  const handleOpenFork = (stepIdx: number) => {
    setForkStepTarget(stepIdx);
    setForkModalOpen(true);
  };

  const handleExecuteFork = (_patchedQuery: string) => {
    // Switch to forked mode
    setActiveRunMode("forked");
    setCurrentStepIndex(2);
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-[#f4f4f5] flex flex-col font-sans">
      {/* Top Telemetry Header */}
      <Header
        activeRunMode={activeRunMode}
        setActiveRunMode={(mode) => {
          setActiveRunMode(mode);
          setCurrentStepIndex(mode === "candidate" ? 2 : 0);
        }}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Banner with Architecture Context */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-lg border border-[#27272a] bg-[#121214]">
          <div className="space-y-1">
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-400">
              Active Evaluation Workload: SQLite Relational Text-to-SQL
            </div>
            <div className="text-sm font-semibold text-zinc-100 font-mono">
              {activeRun.taskTitle}
            </div>
            <div className="text-xs text-zinc-400 max-w-3xl">
              Prompt: &quot;{activeRun.taskPrompt}&quot;
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono px-3 py-1 rounded bg-[#1c1c20] text-zinc-300 border border-[#2e2e34]">
              {activeRunMode === "baseline" && "Viewing Ground Truth Baseline Trace"}
              {activeRunMode === "candidate" && "Viewing Candidate Divergent Trace (No Verifier)"}
              {activeRunMode === "forked" && "Viewing Branched Trace Forked at Step k=2"}
            </span>
          </div>
        </div>

        {/* 1. Interactive Timeline Scrubber */}
        <TimelineScrubber
          run={activeRun}
          currentStepIndex={currentStepIndex}
          onSelectStep={(idx) => setCurrentStepIndex(idx)}
          onOpenForkModal={handleOpenFork}
        />

        {/* 2. Step Inspector & Context-Decision Diff */}
        <ContextDiffView
          step={currentStep}
          baselineStep={baselineStep}
        />

        {/* 3. Paired Bootstrap Statistical Regression Gate */}
        <StatisticalDistributionVisualizer />

        {/* Architectural Guarantees Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div className="p-4 rounded-lg border border-[#27272a] bg-[#121214] space-y-2 font-mono text-xs">
            <div className="text-zinc-200 font-semibold uppercase tracking-wider">
              1. Cryptographic Chaining
            </div>
            <p className="text-zinc-400 leading-relaxed">
              Every step embeds SHA-256 hash of previous step, context state, emitted action, and verifier result. Tampering with any historical step immediately breaks downstream validity.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-[#27272a] bg-[#121214] space-y-2 font-mono text-xs">
            <div className="text-zinc-200 font-semibold uppercase tracking-wider">
              2. Strict Replay &amp; Forking
            </div>
            <p className="text-zinc-400 leading-relaxed">
              Replay compares request fingerprints. When code changes diverge, Kairos halts replay and branches into live execution at step k without re-running earlier idempotent tools.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-[#27272a] bg-[#121214] space-y-2 font-mono text-xs">
            <div className="text-zinc-200 font-semibold uppercase tracking-wider">
              3. Paired Bootstrap CI Gate
            </div>
            <p className="text-zinc-400 leading-relaxed">
              No naive 5% drop thresholds. Evaluates paired resamples across 10,000 iterations and triggers CI failure only if the 95% bootstrap CI upper bound is strictly below zero.
            </p>
          </div>
        </div>
      </main>

      {/* Time-Travel Fork Modal */}
      <TimeTravelForkModal
        step={activeRun.steps[forkStepTarget] || currentStep}
        isOpen={forkModalOpen}
        onClose={() => setForkModalOpen(false)}
        onExecuteFork={handleExecuteFork}
      />
    </div>
  );
}
