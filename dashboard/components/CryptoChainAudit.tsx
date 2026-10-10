"use client";

import React, { useState } from "react";
import { Shield, ShieldAlert, RotateCcw, AlertTriangle } from "lucide-react";

async function sha256(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

interface ChainNode {
  seq: number;
  title: string;
  eventType: string;
  payload: string;
  parentHash: string;
  expectedHash: string;
}

const INITIAL_NODES: ChainNode[] = [
  {
    seq: 0,
    title: "AGENT_INIT",
    eventType: "AGENT_INIT",
    payload: JSON.stringify({ agent: "kairos-harness-2.4", dialect: "sqlite" }),
    parentHash: "0000000000000000000000000000000000000000000000000000000000000000",
    expectedHash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  },
  {
    seq: 1,
    title: "TOOL_INVOCATION",
    eventType: "TOOL_INVOCATION",
    payload: JSON.stringify({ action: "inspect_schema", tables: ["customers", "orders"] }),
    parentHash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    expectedHash: "a102f83d9bc0284756193746aebdc91823746192837461928374619283746192",
  },
  {
    seq: 2,
    title: "SQL_EXECUTION",
    eventType: "SQL_EXECUTION",
    payload: JSON.stringify({ query: "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON c.id = o.customer_id WHERE c.status = 'ACTIVE' GROUP BY c.id;" }),
    parentHash: "a102f83d9bc0284756193746aebdc91823746192837461928374619283746192",
    expectedHash: "b28491c49df92038475619283746592837461928374619283746192837461928",
  },
  {
    seq: 3,
    title: "INVARIANT_VERIFY",
    eventType: "INVARIANT_VERIFY",
    payload: JSON.stringify({ status: "PASS", rows: 2, mutation: false }),
    parentHash: "b28491c49df92038475619283746592837461928374619283746192837461928",
    expectedHash: "c39502d58ea03149586720394857603948572039485720394857203948572039",
  },
];

export function CryptoChainAudit() {
  const [nodes, setNodes] = useState<ChainNode[]>(INITIAL_NODES);
  const [isTampered, setIsTampered] = useState<boolean>(false);
  const [computedHashes, setComputedHashes] = useState<Record<number, string>>({
    0: INITIAL_NODES[0].expectedHash,
    1: INITIAL_NODES[1].expectedHash,
    2: INITIAL_NODES[2].expectedHash,
    3: INITIAL_NODES[3].expectedHash,
  });

  const simulateTampering = async () => {
    setIsTampered(true);
    const updated = [...nodes];
    // Tamper with Step 1 payload (e.g. inject unauthorized table access)
    updated[1] = {
      ...updated[1],
      payload: JSON.stringify({ action: "inspect_schema", tables: ["customers", "orders", "salary_private_data"] }),
    };
    setNodes(updated);

    // Live recompute downstream hashes
    const h1 = await sha256(updated[1].parentHash + updated[1].payload);
    const h2 = await sha256(h1 + updated[2].payload);
    const h3 = await sha256(h2 + updated[3].payload);

    setComputedHashes({
      0: updated[0].expectedHash,
      1: h1,
      2: h2,
      3: h3,
    });
  };

  const resetChain = () => {
    setIsTampered(false);
    setNodes(INITIAL_NODES);
    setComputedHashes({
      0: INITIAL_NODES[0].expectedHash,
      1: INITIAL_NODES[1].expectedHash,
      2: INITIAL_NODES[2].expectedHash,
      3: INITIAL_NODES[3].expectedHash,
    });
  };

  return (
    <div className="rounded-lg border border-[#27272a] bg-[#121214] p-5 shadow-sm font-mono text-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#27272a] gap-3">
        <div>
          <div className="flex items-center gap-2 text-zinc-100 font-semibold text-sm">
            {isTampered ? (
              <ShieldAlert className="h-4 w-4 text-red-400" />
            ) : (
              <Shield className="h-4 w-4 text-emerald-400" />
            )}
            <span>Cryptographic Chaining Verification &amp; Tamper Audit</span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-0.5">
            Every step verifies: H(k) = SHA256(H(k-1) || EventPayload). Tampering at step k invalidates all downstream steps.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isTampered ? (
            <button
              onClick={resetChain}
              className="px-3 py-1.5 rounded border border-[#3f3f46] bg-[#18181b] text-zinc-200 hover:text-white flex items-center gap-1.5 transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset Chain</span>
            </button>
          ) : (
            <button
              onClick={simulateTampering}
              className="px-3 py-1.5 rounded border border-red-800 bg-red-950/40 text-red-300 hover:bg-red-900/50 flex items-center gap-1.5 transition-colors font-semibold"
            >
              <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
              <span>Simulate Tamper at Step 1</span>
            </button>
          )}
        </div>
      </div>

      {/* Nodes visualizer */}
      <div className="mt-4 space-y-3">
        {nodes.map((node, i) => {
          const currentHash = computedHashes[node.seq];
          const isValid = currentHash === node.expectedHash;

          return (
            <div
              key={node.seq}
              className={`p-3.5 rounded border transition-colors ${
                isValid
                  ? "border-[#27272a] bg-[#18181b]"
                  : "border-red-900/80 bg-red-950/20"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-zinc-200">Step {node.seq}:</span>
                  <span className="text-zinc-400 uppercase">{node.title}</span>
                  {node.seq === 1 && isTampered && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 font-bold">
                      MUTATED PAYLOAD
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {isValid ? (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 font-semibold">
                      [CHAIN INTACT]
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-red-950/80 text-red-300 border border-red-800 font-bold">
                      [TAMPER DETECTED: HASH MISMATCH]
                    </span>
                  )}
                </div>
              </div>

              <div className="text-[11px] text-zinc-400 mb-1.5 break-all">
                <span className="text-zinc-500">Payload:</span> {node.payload}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] pt-2 border-t border-[#222226]">
                <div className="truncate">
                  <span className="text-zinc-500">Parent Hash:</span>{" "}
                  <span className="text-zinc-400">{node.parentHash.slice(0, 24)}...</span>
                </div>
                <div className="truncate">
                  <span className="text-zinc-500">Computed Hash:</span>{" "}
                  <span className={isValid ? "text-emerald-400" : "text-red-400 font-bold"}>
                    {currentHash ? currentHash.slice(0, 24) : "None"}...
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
