"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { z } from "zod";
import { money } from "@/lib/kairos-api";
const proposalSchema = z
  .object({
    id: z.string(),
    run_id: z.string(),
    proposal: z
      .object({
        order_id: z.string(),
        amount_cents: z.number(),
        currency: z.string(),
        target: z.string(),
      })
      .passthrough(),
    version: z.number(),
    state: z.string(),
    approved_by: z.string().nullable().optional(),
    approval_expires_at: z.string().nullable().optional(),
  })
  .passthrough();
const runSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    grade_passed: z.boolean().nullable(),
    scenario_id: z.string(),
  })
  .passthrough();
type Proposal = z.infer<typeof proposalSchema>;
export function EffectWorkbench({ role }: { role: string }) {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [runs, setRuns] = useState<z.infer<typeof runSchema>[]>([]);
  const [run, setRun] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<unknown>(null);
  const keys = useRef(new Map<string, string>());
  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/api/workbench/effects", { cache: "no-store" });
      if (!r.ok) throw Error("Sandbox receipt service returned " + r.status);
      setProposals(
        z.object({ proposals: z.array(proposalSchema) }).parse(await r.json())
          .proposals,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sandbox unavailable.");
    }
  }, []);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(async () => {
      await refresh();
      try {
        const r = await fetch("/api/public-incidents");
        if (r.ok && live)
          setRuns(
            z
              .object({ incidents: z.array(runSchema) })
              .parse(await r.json())
              .incidents.filter(
                (x) =>
                  x.grade_passed && x.scenario_id === "late-order-standard",
              ),
          );
      } catch {
        if (live) setError("Eligible runs unavailable.");
      }
    }, 0);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [refresh]);
  async function mutate(path: string, body: unknown) {
    setBusy(true);
    setError("");
    const identity = path + JSON.stringify(body);
    const key = keys.current.get(identity) || crypto.randomUUID();
    keys.current.set(identity, key);
    try {
      const r = await fetch("/api/workbench/" + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": key },
        body: JSON.stringify(body),
      });
      const result = await r.json();
      if (!r.ok)
        throw Error(
          typeof result.detail === "string"
            ? result.detail
            : result.error || "Command rejected.",
        );
      setReceipt(result);
      keys.current.delete(identity);
      await refresh();
    } catch (e) {
      setError(
        (e instanceof Error ? e.message : "Command outcome unconfirmed.") +
          " Retry retains this operation identity.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="effect-workbench">
      <div className="section-top">
        <div>
          <span className="eyebrow">05 / APPROVAL AND SIDE EFFECTS</span>
          <h2>
            Authority binds
            <br />
            <em>to the proposal.</em>
          </h2>
        </div>
        <button className="text-button" onClick={() => void refresh()}>
          Refresh receipts ↻
        </button>
      </div>
      <p className="scope-note">
        Synthetic adjustment ledger only; no money moves. Approval binds a
        version and digest. Replay never dispatches. Forks require fresh
        approval. Response loss reconciles against the target receipt.
      </p>
      {error && (
        <p className="workbench-error" role="alert">
          {error}
        </p>
      )}
      <div className="effect-propose">
        <label htmlFor="effect-run">Passing positive reference execution</label>
        <select
          id="effect-run"
          value={run}
          onChange={(e) => setRun(e.target.value)}
        >
          <option value="">Choose a run in your tenant</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.title} · {r.id.slice(0, 8)}
            </option>
          ))}
        </select>
        <button
          className="button"
          disabled={busy || !run || role === "viewer"}
          onClick={() => void mutate("runs/" + run + "/proposal", {})}
        >
          Draft sandbox proposal ↗
        </button>
        <small>
          Visible published runs may belong to another tenant; server checks
          authority again.
        </small>
      </div>
      <div>
        {proposals.map((p) => (
          <article className="effect-proposal" key={p.id}>
            <div>
              <strong>
                {money(p.proposal.amount_cents)} · {p.proposal.order_id}
              </strong>
              <small>
                {p.proposal.target} · version {p.version}
              </small>
              <span className="status attention">{p.state}</span>
            </div>
            <div className="job-actions">
              {role === "admin" && (
                <>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      void mutate("effects/" + p.id + "/approve", {
                        version: p.version,
                      })
                    }
                  >
                    Approve version
                  </button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      void mutate("effects/" + p.id + "/revoke", {
                        version: p.version,
                      })
                    }
                  >
                    Revoke
                  </button>
                </>
              )}
              <button
                className="button"
                disabled={busy || role === "viewer"}
                onClick={() =>
                  void mutate("effects/" + p.id + "/dispatch", {
                    version: p.version,
                  })
                }
              >
                Dispatch / reconcile ↗
              </button>
            </div>
            <details className="raw-record">
              <summary>Bound proposal and approval</summary>
              <textarea
                readOnly
                aria-label="Proposal evidence"
                value={JSON.stringify(p, null, 2)}
              />
            </details>
          </article>
        ))}
        {!proposals.length && (
          <p className="empty-state">No sandbox proposals in this tenant.</p>
        )}
      </div>
      {receipt !== null && (
        <details className="raw-record" open>
          <summary>Latest command response and receipt</summary>
          <textarea
            readOnly
            aria-label="Effect command receipt"
            value={JSON.stringify(receipt, null, 2)}
          />
        </details>
      )}
    </section>
  );
}
