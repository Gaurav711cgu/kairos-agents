"use client";

import React, { useState } from "react";
import { Shield, Check, X, Copy, Eye, GitCompare } from "lucide-react";
import { AgentStep } from "@/lib/types";

interface ContextDiffViewProps {
  step: AgentStep;
  baselineStep?: AgentStep;
}

export default function ContextDiffView({ step, baselineStep }: ContextDiffViewProps) {
  const [activeTab, setActiveTab] = useState<"context_decision" | "replay_diff">("context_decision");
  const [copiedKey, setCopiedKey] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const tokenPercentage = Math.min(
    100,
    Math.round((step.context.totalTokens / step.context.maxTokenBudget) * 100)
  );

  return (
    <div className="rounded-lg border border-[#27272a] bg-[#121214] p-5 shadow-sm">
      {/* Tab Switcher & Step Metadata */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#27272a] gap-3">
        <div className="flex items-center gap-3">
          <div className="text-sm font-semibold font-mono text-zinc-100 flex items-center gap-2">
            <span>Step {step.seq} Inspector</span>
            <span className="text-xs px-2 py-0.5 rounded bg-[#1e1e24] text-zinc-300 border border-[#2e2e33]">
              {step.eventType}
            </span>
          </div>
          <span className="text-xs font-mono text-zinc-500">
            Hash: {step.eventHash.slice(0, 16)}...
          </span>
        </div>

        {/* Mode Selector */}
        <div className="flex items-center gap-1.5 bg-[#18181b] p-1 rounded border border-[#27272a]">
          <button
            onClick={() => setActiveTab("context_decision")}
            className={`px-2.5 py-1 text-xs font-mono rounded flex items-center gap-1.5 transition-colors ${
              activeTab === "context_decision"
                ? "bg-zinc-200 text-zinc-950 font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Eye className="h-3.5 w-3.5" />
            <span>Context & Decision</span>
          </button>
          <button
            onClick={() => setActiveTab("replay_diff")}
            className={`px-2.5 py-1 text-xs font-mono rounded flex items-center gap-1.5 transition-colors ${
              activeTab === "replay_diff"
                ? "bg-zinc-200 text-zinc-950 font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <GitCompare className="h-3.5 w-3.5" />
            <span>Baseline Diff</span>
          </button>
        </div>
      </div>

      {/* Main Panel Content */}
      {activeTab === "context_decision" ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 pt-4">
          {/* Left Column: Context Snapshot ("What the model saw") */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400">
                Input Context Snapshot
              </span>
              <div className="text-[11px] font-mono text-zinc-400 flex items-center gap-2">
                <span>Tokens:</span>
                <span className="text-zinc-200 font-medium">
                  {step.context.totalTokens} / {step.context.maxTokenBudget} ({tokenPercentage}%)
                </span>
              </div>
            </div>

            {/* Token Budget Meter */}
            <div className="w-full bg-[#1e1e24] h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full transition-[width] duration-300 ease-out ${
                  tokenPercentage > 85
                    ? "bg-red-500"
                    : tokenPercentage > 60
                    ? "bg-amber-400"
                    : "bg-emerald-500"
                }`}
                style={{ width: `${tokenPercentage}%` }}
              />
            </div>

            {/* System Prompt Box */}
            <div className="rounded border border-[#27272a] bg-[#18181b] p-3 text-xs font-mono">
              <div className="text-zinc-500 mb-1 text-[11px] uppercase tracking-wider">
                System Directive & Invariants
              </div>
              <div className="text-zinc-300 leading-relaxed">
                {step.context.systemPrompt}
              </div>
            </div>

            {/* Schema Tables Available */}
            <div className="rounded border border-[#27272a] bg-[#18181b] p-3 text-xs font-mono">
              <div className="text-zinc-500 mb-1 text-[11px] uppercase tracking-wider">
                Active Relational Schema In-Context
              </div>
              <div className="flex flex-wrap gap-2">
                {step.context.schemaTables.map((t) => (
                  <span
                    key={t}
                    className="px-2 py-0.5 rounded bg-[#27272a] text-zinc-200 text-xs border border-[#3f3f46]"
                  >
                    table: {t}
                  </span>
                ))}
              </div>
            </div>

            {/* Episodic Memory Log */}
            <div className="rounded border border-[#27272a] bg-[#18181b] p-3 text-xs font-mono flex-1">
              <div className="text-zinc-500 mb-1.5 text-[11px] uppercase tracking-wider">
                Episodic Scratchpad / Context History
              </div>
              <ul className="space-y-1.5 text-zinc-300">
                {step.context.episodicMemory.map((mem, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-zinc-600 select-none">{i + 1}.</span>
                    <span className="leading-relaxed">{mem}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Right Column: Model Decision & Committed Effect */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400">
                Action Decision & Invariant Verification
              </span>
              <div className="flex items-center gap-1.5 text-xs font-mono">
                {step.decision.verifierPassed ? (
                  <span className="flex items-center gap-1 text-emerald-400 font-semibold bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/60">
                    <Check className="h-3.5 w-3.5" /> VERIFIER PASS
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-red-400 font-semibold bg-red-950/40 px-2 py-0.5 rounded border border-red-800/60">
                    <X className="h-3.5 w-3.5" /> VERIFIER FAIL
                  </span>
                )}
              </div>
            </div>

            {/* Emitted Tool Action */}
            <div className="rounded border border-[#27272a] bg-[#18181b] p-3 text-xs font-mono">
              <div className="flex items-center justify-between mb-2">
                <span className="text-zinc-500 text-[11px] uppercase tracking-wider">
                  Emitted Action
                </span>
                <span className="font-semibold text-indigo-400 bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-800/50">
                  {step.decision.actionName}
                </span>
              </div>

              {/* Action Parameters Code Block */}
              <div className="mt-2 text-zinc-300">
                <div className="text-[11px] text-zinc-500 mb-1">Parameters:</div>
                <pre className="p-2.5 rounded bg-[#101012] border border-[#222226] overflow-x-auto text-[11px] text-emerald-300 leading-relaxed font-mono">
                  {JSON.stringify(step.decision.parameters, null, 2)}
                </pre>
              </div>

              {/* SHA-256 Idempotency Key */}
              <div className="mt-3 pt-2.5 border-t border-[#222226] flex items-center justify-between text-[11px]">
                <span className="text-zinc-500">SHA-256 Idempotency Key:</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-zinc-400 font-mono">
                    {step.decision.idempotencyKey.slice(0, 20)}...
                  </span>
                  <button
                    onClick={() => copyToClipboard(step.decision.idempotencyKey)}
                    className="p-1 hover:text-white text-zinc-500 transition-colors"
                    title="Copy full key"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                  {copiedKey && <span className="text-[10px] text-emerald-400">Copied</span>}
                </div>
              </div>
            </div>

            {/* Execution Output */}
            <div className="rounded border border-[#27272a] bg-[#18181b] p-3 text-xs font-mono">
              <div className="text-zinc-500 mb-1.5 text-[11px] uppercase tracking-wider">
                Execution Output / Response
              </div>
              <pre className="p-2.5 rounded bg-[#101012] border border-[#222226] overflow-x-auto text-[11px] text-zinc-300 max-h-40 font-mono">
                {JSON.stringify(step.decision.executionOutput, null, 2)}
              </pre>
            </div>

            {/* Deterministic Verifier Invariant Details */}
            {step.decision.verifierDetails && (
              <div
                className={`rounded border p-3 text-xs font-mono ${
                  step.decision.verifierPassed
                    ? "border-emerald-900/60 bg-emerald-950/20 text-emerald-300"
                    : "border-red-900/60 bg-red-950/20 text-red-300"
                }`}
              >
                <div className="flex items-center gap-1.5 font-semibold text-[11px] uppercase tracking-wider mb-1">
                  <Shield className="h-3.5 w-3.5" />
                  <span>Deterministic Invariant Evaluation</span>
                </div>
                <div className="text-xs leading-relaxed">
                  {step.decision.verifierDetails}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Replay Diff View */
        <div className="pt-4 flex flex-col gap-4">
          <div className="text-xs font-mono text-zinc-400">
            Comparing Step {step.seq} against Baseline Trace ({baselineStep ? baselineStep.eventHash.slice(0, 16) : "None"}).
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Baseline Reference */}
            <div className="p-4 rounded border border-[#27272a] bg-[#18181b] font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[#27272a] mb-3">
                <span className="font-semibold text-emerald-400">Baseline Step {step.seq} (Ground Truth)</span>
                <span className="text-[11px] text-zinc-500">{baselineStep?.decision.actionName}</span>
              </div>
              <div className="text-[11px] text-zinc-500 mb-1">Generated Query:</div>
              <pre className="p-3 rounded bg-[#101012] border border-emerald-900/50 text-emerald-300 text-xs overflow-x-auto whitespace-pre-wrap">
                {baselineStep
                  ? (baselineStep.decision.parameters.query as string) || JSON.stringify(baselineStep.decision.parameters, null, 2)
                  : "No corresponding baseline step recorded."}
              </pre>
              <div className="mt-3 text-[11px] text-zinc-400">
                Idempotency Fingerprint: <span className="text-zinc-200">{baselineStep?.decision.idempotencyKey.slice(0, 16)}</span>
              </div>
            </div>

            {/* Current Trace */}
            <div className="p-4 rounded border border-[#27272a] bg-[#18181b] font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[#27272a] mb-3">
                <span className={`font-semibold ${step.divergedFromBaseline ? "text-amber-400" : "text-zinc-200"}`}>
                  Current Trace Step {step.seq} {step.divergedFromBaseline ? "(Divergent)" : "(Matched)"}
                </span>
                <span className="text-[11px] text-zinc-500">{step.decision.actionName}</span>
              </div>
              <div className="text-[11px] text-zinc-500 mb-1">Generated Query:</div>
              <pre
                className={`p-3 rounded text-xs overflow-x-auto whitespace-pre-wrap border ${
                  step.divergedFromBaseline
                    ? "bg-[#211512] border-amber-900/70 text-amber-300"
                    : "bg-[#101012] border-[#222226] text-zinc-300"
                }`}
              >
                {(step.decision.parameters.query as string) || JSON.stringify(step.decision.parameters, null, 2)}
              </pre>
              <div className="mt-3 text-[11px] text-zinc-400">
                Idempotency Fingerprint: <span className="text-zinc-200">{step.decision.idempotencyKey.slice(0, 16)}</span>
              </div>
            </div>
          </div>

          {step.divergedFromBaseline && (
            <div className="p-3.5 rounded border border-amber-800/80 bg-amber-950/20 text-xs font-mono text-amber-300">
              <div className="font-bold mb-1">Divergence Root Cause Analysis:</div>
              <p className="text-zinc-300">
                The candidate trace diverged because the SQL generator referenced column <code className="text-amber-300 font-bold bg-[#18181b] px-1 py-0.5 rounded">c.is_active = 1</code> instead of checking the database column <code className="text-emerald-400 font-bold bg-[#18181b] px-1 py-0.5 rounded">c.status = &apos;ACTIVE&apos;</code>.
                In strict replay mode, the fingerprint hash did not match the recorded baseline response, forcing live execution which resulted in an invariant violation.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
