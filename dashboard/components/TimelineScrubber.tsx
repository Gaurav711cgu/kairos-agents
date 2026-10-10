"use client";

import React, { useEffect, useState } from "react";
import { Play, Pause, SkipBack, SkipForward, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { AgentRun, AgentStep } from "@/lib/types";

interface TimelineScrubberProps {
  run: AgentRun;
  currentStepIndex: number;
  onSelectStep: (index: number) => void;
  onOpenForkModal: (stepIndex: number) => void;
}

export default function TimelineScrubber({
  run,
  currentStepIndex,
  onSelectStep,
  onOpenForkModal,
}: TimelineScrubberProps) {
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying) {
      timer = setInterval(() => {
        if (currentStepIndex >= run.steps.length - 1) {
          setIsPlaying(false);
        } else {
          onSelectStep(currentStepIndex + 1);
        }
      }, 1200);
    }
    return () => clearInterval(timer);
  }, [isPlaying, currentStepIndex, run.steps.length, onSelectStep]);

  const currentStep: AgentStep | undefined = run.steps[currentStepIndex];

  return (
    <div className="rounded-lg border border-[#27272a] bg-[#121214] p-5 shadow-sm">
      {/* Top Meta Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#27272a] gap-2">
        <div className="flex items-center gap-3">
          <div className="text-xs font-mono px-2 py-0.5 rounded bg-[#1f1f23] text-zinc-300 border border-[#2e2e33]">
            Run ID: <span className="text-zinc-100 font-semibold">{run.runId}</span>
          </div>
          <div className="text-xs font-mono text-zinc-400">
            {run.taskTitle}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-zinc-400">Status:</span>
          {run.status === "SUCCESS" && (
            <span className="flex items-center gap-1 text-emerald-400 font-semibold">
              <CheckCircle2 className="h-3.5 w-3.5" /> VERIFIED PASS
            </span>
          )}
          {run.status === "VERIFIER_FAILURE" && (
            <span className="flex items-center gap-1 text-red-400 font-semibold">
              <XCircle className="h-3.5 w-3.5" /> INVARIANT VIOLATION
            </span>
          )}
          {run.status === "REPLAY_DIVERGED" && (
            <span className="flex items-center gap-1 text-amber-400 font-semibold">
              <AlertTriangle className="h-3.5 w-3.5" /> REPLAY DIVERGED
            </span>
          )}
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-400">Latency: <span className="text-zinc-200">{run.totalLatencyMs}ms</span></span>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-400">Tokens: <span className="text-zinc-200">{run.totalTokens.toLocaleString()}</span></span>
        </div>
      </div>

      {/* Playback Controls & Progress Bar */}
      <div className="pt-4 pb-2 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSelectStep(Math.max(0, currentStepIndex - 1))}
            disabled={currentStepIndex === 0}
            className="p-1.5 rounded border border-[#27272a] bg-[#18181b] text-zinc-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Previous Step"
          >
            <SkipBack className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded border border-[#27272a] bg-[#18181b] text-zinc-300 hover:text-white transition-colors"
            title={isPlaying ? "Pause Scrubber" : "Play Sequence"}
          >
            {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button
            onClick={() => onSelectStep(Math.min(run.steps.length - 1, currentStepIndex + 1))}
            disabled={currentStepIndex === run.steps.length - 1}
            className="p-1.5 rounded border border-[#27272a] bg-[#18181b] text-zinc-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Next Step"
          >
            <SkipForward className="h-4 w-4" />
          </button>
        </div>

        {/* Step Slider Tracker */}
        <div className="flex-1 max-w-md mx-4">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 mb-1">
            <span>Step {currentStepIndex} of {run.steps.length - 1}</span>
            <span>{currentStep?.eventType || "N/A"}</span>
          </div>
          <input
            type="range"
            min="0"
            max={run.steps.length - 1}
            value={currentStepIndex}
            onChange={(e) => onSelectStep(Number(e.target.value))}
            className="w-full h-1.5 bg-[#27272a] rounded-lg appearance-none cursor-pointer accent-zinc-200"
          />
        </div>

        {/* Action Button: Fork from Step k */}
        <div>
          <button
            onClick={() => onOpenForkModal(currentStepIndex)}
            className="px-3 py-1.5 rounded border border-[#3f3f46] bg-[#1e1e24] text-xs font-mono text-zinc-200 hover:bg-[#27272a] hover:text-white transition-colors flex items-center gap-1.5"
          >
            <span>Fork at Step {currentStepIndex}</span>
          </button>
        </div>
      </div>

      {/* Visual Timeline Nodes */}
      <div className="mt-4 pt-3 border-t border-[#1e1e22] grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-2.5">
        {run.steps.map((step, idx) => {
          const isSelected = idx === currentStepIndex;
          const isDivergent = !!step.divergedFromBaseline;

          return (
            <button
              key={step.seq}
              onClick={() => onSelectStep(idx)}
              className={`text-left p-3 rounded-md border transition-all text-xs font-mono relative ${
                isSelected
                  ? isDivergent
                    ? "border-amber-400 bg-[#241a12] ring-1 ring-amber-400"
                    : "border-zinc-300 bg-[#1f1f23] ring-1 ring-zinc-300"
                  : isDivergent
                  ? "border-amber-900/60 bg-[#181410] hover:border-amber-700/80"
                  : "border-[#27272a] bg-[#18181b] hover:border-[#3f3f46]"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-zinc-200">k = {step.seq}</span>
                {isDivergent ? (
                  <span className="text-[10px] uppercase font-bold text-amber-400 bg-amber-950/70 border border-amber-800/80 px-1.5 py-0.2 rounded">
                    Diverged
                  </span>
                ) : (
                  <span className="text-[10px] text-zinc-500">
                    {step.decision.verifierPassed ? "OK" : "ERR"}
                  </span>
                )}
              </div>

              <div className="text-[11px] font-medium text-zinc-300 truncate">
                {step.eventType}
              </div>

              <div className="text-[10px] text-zinc-500 mt-1 truncate">
                {step.decision.actionName}
              </div>
            </button>
          );
        })}
      </div>

      {/* Divergence Notification Alert Banner */}
      {currentStep?.divergedFromBaseline && (
        <div className="mt-4 p-3 rounded border border-amber-800/80 bg-amber-950/30 text-amber-200 text-xs font-mono flex items-start gap-2.5">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-amber-300">
              REPLAY DIVERGENCE DETECTED AT STEP {currentStep.seq}
            </div>
            <div className="text-zinc-300 mt-0.5">
              {currentStep.divergenceReason}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
