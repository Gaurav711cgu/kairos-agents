"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Incident, money } from "@/lib/kairos-api";
export const IncidentInspector = ({
  incident,
  canFork,
}: {
  incident: Incident;
  canFork: boolean;
}) => {
  const router = useRouter();
  const [selected, setSelected] = useState(incident.events[0]?.seq ?? 0);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const submitting = useRef(false);
  const commandKey = useRef<{ runId: string; key: string } | null>(null);
  const filtered = incident.events.filter((event) =>
    (event.title + " " + event.summary + " " + event.event_type)
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const selectedIndex = Math.max(
    0,
    filtered.findIndex((item) => item.seq === selected),
  );
  const windowStart = Math.max(0, selectedIndex - 40);
  const visibleEvents = filtered.slice(windowStart, windowStart + 80);
  const event = incident.events.find((item) => item.seq === selected);
  useEffect(() => {
    const onPop = () => {
      const value = Number(
        new URLSearchParams(window.location.search).get("event"),
      );
      setSelected(
        incident.events.some((item) => item.seq === value)
          ? value
          : (incident.events[0]?.seq ?? 0),
      );
    };
    onPop();
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [incident.events]);
  const select = (seq: number) => {
    setSelected(seq);
    const url = new URL(window.location.href);
    url.searchParams.set("event", String(seq));
    window.history.replaceState(null, "", url);
  };
  const fork = async () => {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setMessage("");
    try {
      const storageKey = "kairos-pending-fork:" + incident.id;
      if (!commandKey.current || commandKey.current.runId !== incident.id)
        commandKey.current = {
          runId: incident.id,
          key: sessionStorage.getItem(storageKey) || crypto.randomUUID(),
        };
      // Store before dispatch. If storage is unavailable, do not send a command
      // whose identity cannot survive a reload after an uncertain response.
      sessionStorage.setItem(storageKey, commandKey.current.key);
      const response = await fetch("/api/local-fork/" + incident.id, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": commandKey.current.key,
        },
        body: JSON.stringify({ policy: "preserve" }),
      });
      const body = await response.json();
      if (!response.ok) {
        setMessage(
          body.error ??
            "The fork could not be created. Inspect the service before retrying.",
        );
        return;
      }
      if (typeof body.id !== "string")
        throw new Error("Unsupported fork response");
      sessionStorage.removeItem(storageKey);
      commandKey.current = null;
      router.push("/incidents/" + encodeURIComponent(body.id));
    } catch {
      setMessage(
        "No confirmed response was received. The run may exist; inspect case files before submitting again.",
      );
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };
  return (
    <>
      <div className="inspector-grid">
        <section className="timeline" aria-label="Execution timeline">
          <div className="panel-heading">
            <span className="eyebrow">01 / EVENT LOG</span>
            <span className="mono">{incident.events.length}</span>
          </div>
          <label className="search-label">
            Filter captured events
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search events…"
              type="search"
            />
          </label>
          <div className="timeline-list">
            {visibleEvents.map((item) => (
              <button
                onKeyDown={(e) => {
                  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
                  const index = filtered.findIndex(
                    (item) => item.seq === selected,
                  );
                  const next =
                    filtered[
                      Math.max(
                        0,
                        Math.min(
                          filtered.length - 1,
                          index + (e.key === "ArrowDown" ? 1 : -1),
                        ),
                      )
                    ];
                  if (next) {
                    e.preventDefault();
                    select(next.seq);
                    window.requestAnimationFrame(() =>
                      document.getElementById("event-" + next.seq)?.focus(),
                    );
                  }
                }}
                id={"event-" + item.seq}
                key={item.seq}
                onClick={() => select(item.seq)}
                aria-current={selected === item.seq ? "step" : undefined}
              >
                <span className="event-seq">
                  {String(item.seq).padStart(2, "0")}
                </span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.event_type.replaceAll("_", " ")}</small>
                </span>
                <span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
          {filtered.length > 80 && (
            <div className="pair-pagination">
              <button
                className="text-button"
                disabled={selectedIndex === 0}
                onClick={() =>
                  select(filtered[Math.max(0, selectedIndex - 80)].seq)
                }
              >
                ← Earlier
              </button>
              <button
                className="text-button"
                disabled={selectedIndex >= filtered.length - 1}
                onClick={() =>
                  select(
                    filtered[Math.min(filtered.length - 1, selectedIndex + 80)]
                      .seq,
                  )
                }
              >
                Later →
              </button>
            </div>
          )}
          {!filtered.length && (
            <p className="empty-state">No events match this filter.</p>
          )}
          <p className="keyboard-hint">
            ↑ ↓ move between events · selection saved in URL
            {filtered.length > 80 && (
              <>
                {" "}
                · {windowStart + 1}–
                {Math.min(windowStart + 80, filtered.length)} of{" "}
                {filtered.length} rendered
              </>
            )}
          </p>
        </section>
        <section className="event-detail" aria-label="Selected event">
          <div className="panel-heading">
            <span className="eyebrow">02 / INSPECT</span>
            <span className="mono">STEP {selected}</span>
          </div>
          {event && (
            <>
              <h2>{event.title}</h2>
              <p className="event-summary">{event.summary}</p>
              <details className="raw-record">
                <summary>Captured event payload</summary>
                <pre>{JSON.stringify(event.payload, null, 2)}</pre>
              </details>
            </>
          )}
          <h3 className="subheading">Context supplied to the runner</h3>
          <div className="inspect-context">
            {incident.context_blocks.map((block) => (
              <article
                key={block.id}
                className={block.included ? "included" : "excluded"}
              >
                <div>
                  <h4>{block.label}</h4>
                  <span
                    className={
                      block.included ? "status good" : "status attention"
                    }
                  >
                    {block.included ? "Retained" : "Omitted"}
                  </span>
                </div>
                <p>{block.content}</p>
                <small>
                  Source: {block.source} · {block.id}
                </small>
              </article>
            ))}
          </div>
          <p className="fine-print">
            Readable context rendering. The event payload contains captured
            structured data; this view does not expose hidden model reasoning.
          </p>
        </section>
        <aside className="verdict-pane">
          <span className="eyebrow">03 / INDEPENDENT VERDICT</span>
          <div
            className={
              "verdict " + (incident.grade.passed ? "passed" : "failed")
            }
          >
            <span>{incident.grade.passed ? "[PASS]" : "[FAIL]"}</span>
            <h2>
              {incident.grade.passed ? "Checks passed." : "Evidence disagrees."}
            </h2>
          </div>
          <dl className="outcome-list">
            <div>
              <dt>Proposed refund</dt>
              <dd>{money(incident.decision.refund_cents)}</dd>
            </div>
            <div>
              <dt>Expected refund</dt>
              <dd>{money(incident.grade.expected_refund_cents)}</dd>
            </div>
          </dl>
          <p>{incident.decision.reason}</p>
          <ul className="grade-checks">
            {incident.grade.checks.map((check) => (
              <li key={check.name}>
                <span aria-hidden="true">
                  {check.passed ? "[OK]" : "[FAIL]"}
                </span>
                <div>
                  <strong>{check.name.replaceAll("_", " ")}</strong>
                  <p>{check.detail}</p>
                  <small>{check.passed ? "Passed" : "Failed"}</small>
                </div>
              </li>
            ))}
          </ul>
          <div className="fork-panel">
            <span className="eyebrow">ONE CONTROLLED INTERVENTION</span>
            <h3>Keep the policy context.</h3>
            <p>
              Run this scenario again with all policy blocks retained. The
              original record stays intact.
            </p>
            <button
              className="button primary"
              onClick={fork}
              disabled={busy || !canFork}
            >
              {busy ? "Creating isolated run…" : "Run with preserved context ↗"}
            </button>
            <p className="fine-print">
              {canFork
                ? "Local developer action. Fresh reference-policy execution; not checkpoint resume. No payment tools."
                : "Mutation disabled in this viewer. Enable local developer mode to create a fresh run."}
            </p>
            {message && (
              <p role="alert" className="action-error">
                {message}
              </p>
            )}
          </div>
        </aside>
      </div>
      <section className="record-provenance">
        <div>
          <span className="eyebrow">RECORD PROVENANCE</span>
          <p>{incident.provenance}</p>
          <span className="mono">{incident.id}</span>
        </div>
        <div>
          <span className="eyebrow">INTEGRITY SCOPE</span>
          <p>{incident.integrity.scope}</p>
          <strong>
            {incident.integrity.verified
              ? "Local event chain verified"
              : "Integrity check did not pass"}
          </strong>
        </div>
        <div>
          <span className="eyebrow">LINEAGE</span>
          {incident.lineage.parent_run_id ? (
            <Link href={"/incidents/" + incident.lineage.parent_run_id}>
              Inspect parent execution ↗
            </Link>
          ) : (
            <p>Original controlled execution.</p>
          )}
          <p className="fine-print">
            Policy {incident.configuration.policy_version} · Model:{" "}
            {incident.configuration.model ?? "none — reference policy"}
          </p>
        </div>
      </section>
    </>
  );
};
