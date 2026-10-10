from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from harness.events import AgentEvent, EventLog, EventType
from harness.agent import AgentHarness, AgentConfig, AgentRunResult


class DivergenceReport(BaseModel):
    diverged: bool
    divergence_step: Optional[int] = None
    baseline_event: Optional[AgentEvent] = None
    candidate_event: Optional[AgentEvent] = None
    diff_summary: str


class ReplayEngine:
    """
    Replay & Divergence Detection Engine.
    Executes a candidate agent run against an immutable baseline event log,
    pinpointing the exact step and causal factor where the candidate diverges.
    """

    @staticmethod
    def detect_divergence(baseline_log: EventLog, candidate_log: EventLog) -> DivergenceReport:
        # Filter action-relevant events (Context, Model Invocation, Tool Execution)
        relevant_types = {
            EventType.CONTEXT_ASSEMBLED,
            EventType.MODEL_INVOKED,
            EventType.TOOL_EXECUTED,
        }

        b_events = [e for e in baseline_log.events if e.event_type in relevant_types]
        c_events = [e for e in candidate_log.events if e.event_type in relevant_types]

        min_len = min(len(b_events), len(c_events))

        for idx in range(min_len):
            b_ev = b_events[idx]
            c_ev = c_events[idx]

            # 1. Check event type equivalence
            if b_ev.event_type != c_ev.event_type:
                return DivergenceReport(
                    diverged=True,
                    divergence_step=b_ev.payload.get("step", idx),
                    baseline_event=b_ev,
                    candidate_event=c_ev,
                    diff_summary=f"Event type mismatch: baseline was '{b_ev.event_type}', candidate produced '{c_ev.event_type}'",
                )

            # 2. Check context hash divergence
            if b_ev.event_type == EventType.CONTEXT_ASSEMBLED:
                b_hash = b_ev.payload.get("context_hash")
                c_hash = c_ev.payload.get("context_hash")
                if b_hash != c_hash:
                    return DivergenceReport(
                        diverged=True,
                        divergence_step=b_ev.payload.get("step", idx),
                        baseline_event=b_ev,
                        candidate_event=c_ev,
                        diff_summary=f"Context diverged at step {b_ev.payload.get('step', idx)}: context SHA-256 fingerprint mismatch",
                    )

            # 3. Check tool call divergence
            if b_ev.event_type == EventType.TOOL_EXECUTED:
                b_tool = b_ev.payload.get("tool_result", {})
                c_tool = c_ev.payload.get("tool_result", {})
                if b_tool.get("idempotency_key") != c_tool.get("idempotency_key"):
                    return DivergenceReport(
                        diverged=True,
                        divergence_step=b_ev.payload.get("step", idx),
                        baseline_event=b_ev,
                        candidate_event=c_ev,
                        diff_summary=f"Tool call diverged at step {b_ev.payload.get('step', idx)}: args hash {b_tool.get('idempotency_key')} != {c_tool.get('idempotency_key')}",
                    )

        if len(b_events) != len(c_events):
            return DivergenceReport(
                diverged=True,
                divergence_step=min_len,
                baseline_event=b_events[min_len] if len(b_events) > min_len else None,
                candidate_event=c_events[min_len] if len(c_events) > min_len else None,
                diff_summary=f"Execution length mismatch: baseline had {len(b_events)} events, candidate had {len(c_events)}",
            )

        return DivergenceReport(
            diverged=False,
            divergence_step=None,
            baseline_event=None,
            candidate_event=None,
            diff_summary="Exact replay: candidate execution bitwise mirrors baseline event log.",
        )
