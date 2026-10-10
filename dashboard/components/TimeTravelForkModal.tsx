"use client";

import React, { useState } from "react";
import { GitFork, X, Check, ArrowRight } from "lucide-react";
import { AgentStep } from "@/lib/types";

interface TimeTravelForkModalProps {
  step: AgentStep;
  isOpen: boolean;
  onClose: () => void;
  onExecuteFork: (patchedQuery: string) => void;
}

export default function TimeTravelForkModal({
  step,
  isOpen,
  onClose,
  onExecuteFork,
}: TimeTravelForkModalProps) {
  const initialQuery =
    (step.decision.parameters.query as string) ||
    "SELECT c.name, SUM(o.amount) as total_spent FROM customers c JOIN orders o ON c.id = o.customer_id WHERE c.status = 'ACTIVE' GROUP BY c.id HAVING total_spent > 500 ORDER BY total_spent DESC;";

  const [patchQuery, setPatchQuery] = useState(initialQuery);
  const [isForking, setIsForking] = useState(false);

  if (!isOpen) return null;

  const handleFork = () => {
    setIsForking(true);
    setTimeout(() => {
      setIsForking(false);
      onExecuteFork(patchQuery);
      onClose();
    }, 700);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-lg border border-[#3f3f46] bg-[#141416] p-6 shadow-2xl font-mono">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#27272a]">
          <div className="flex items-center gap-2 text-zinc-100">
            <GitFork className="h-5 w-5 text-emerald-400" />
            <h3 className="text-base font-semibold">
              Time-Travel Fork at Step {step.seq}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-white hover:bg-[#27272a] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Fork Context Information */}
        <div className="py-4 space-y-3 text-xs">
          <div className="p-3 rounded border border-[#27272a] bg-[#18181b] space-y-1">
            <div className="text-zinc-400">
              Fork Point Parent Hash:{" "}
              <span className="text-zinc-200">{step.parentHash.slice(0, 32)}...</span>
            </div>
            <div className="text-zinc-400">
              Action Name:{" "}
              <span className="text-indigo-400 font-semibold">{step.decision.actionName}</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-zinc-300 font-medium">
              Patch Action Parameters (SQL Query Mutation):
            </label>
            <textarea
              rows={4}
              value={patchQuery}
              onChange={(e) => setPatchQuery(e.target.value)}
              className="w-full rounded border border-[#3f3f46] bg-[#0c0c0e] p-3 text-emerald-300 text-xs font-mono focus:border-emerald-500 focus:outline-none transition-colors"
              placeholder="Enter patched SQL query..."
            />
            <p className="text-[11px] text-zinc-500">
              Injecting this patch will truncate subsequent execution history from step {step.seq} onwards, compute new cryptographic parent-child event hashes, and run live invariant verification.
            </p>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="pt-4 border-t border-[#27272a] flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded border border-[#27272a] bg-[#18181b] text-xs font-medium text-zinc-300 hover:bg-[#222226] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleFork}
            disabled={isForking}
            className="px-4 py-2 rounded bg-emerald-600 text-xs font-semibold text-white hover:bg-emerald-500 transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            {isForking ? (
              <span>Forking &amp; Executing...</span>
            ) : (
              <>
                <span>Fork &amp; Re-Execute</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
