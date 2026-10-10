"use client";
import { useState } from "react";
import Link from "next/link";
import { money, type Incident } from "@/lib/kairos-api";
export const ContextMoment = ({ incident }: { incident: Incident }) => {
  const [mode, setMode] = useState<"received" | "source">("received");
  const omitted = incident.context_blocks.filter((block) => !block.included);
  return (
    <section className="context-canvas" aria-label="Captured incident context">
      <div className="canvas-top">
        <span className="eyebrow">CAPTURED EXECUTION</span>
        <span
          className={incident.grade.passed ? "status good" : "status attention"}
        >
          {incident.grade.passed ? "Checks passed" : "Failure captured"}
        </span>
      </div>
      <div className="canvas-title">
        <span className="mono">{incident.scenario.order_id}</span>
        <h2>
          Same order.
          <br />
          <em>Missing context.</em>
        </h2>
        <p>{incident.task}</p>
      </div>
      <div className="segmented" aria-label="Context view">
        {(["received", "source"] as const).map((value) => (
          <button
            type="button"
            key={value}
            aria-pressed={mode === value}
            onClick={() => setMode(value)}
          >
            {value === "received"
              ? "What the runner saw"
              : "Full source context"}
          </button>
        ))}
      </div>
      <div className="context-strips">
        {incident.context_blocks.map((block) => (
          <div
            className={"context-strip " + (!block.included ? "omitted" : "")}
            key={block.id}
          >
            <div>
              <span className="block-mark" aria-hidden="true">
                {block.included ? "↳" : "−"}
              </span>
              <span>{block.label}</span>
              <small>
                {block.included
                  ? "Retained"
                  : mode === "received"
                    ? "Omitted"
                    : "Missing from request"}
              </small>
            </div>
            <p>
              {!block.included && mode === "received"
                ? "This evidence was absent from the captured context. Open full source context to inspect it."
                : block.content}
            </p>
          </div>
        ))}
      </div>
      <div className="outcome-strip">
        <div>
          <span className="eyebrow">PROPOSED</span>
          <strong>{money(incident.decision.refund_cents)}</strong>
        </div>
        <span className="outcome-connector" aria-hidden="true">
          →
        </span>
        <div>
          <span className="eyebrow">EXPECTED</span>
          <strong>{money(incident.grade.expected_refund_cents)}</strong>
        </div>
        <Link href={"/incidents/" + incident.id}>
          Inspect {incident.event_count} events ↗
        </Link>
      </div>
      <p className="canvas-caption">
        {omitted.length} omitted block{omitted.length === 1 ? "" : "s"} ·
        deterministic reference policy · synthetic scenario
      </p>
    </section>
  );
};
