"""Executable deterministic reference policy, explicitly not an LLM evaluation."""
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from kairos_api.grading import grade_decision
from kairos_api.integrity import GENESIS_HASH, hash_event
from kairos_api.scenarios import assemble_context, get_scenario


def reference_decision(context: list[dict], scenario: dict) -> dict:
    """Policy sees included blocks; the independent grader sees complete truth."""
    ids = {block["id"] for block in context if block["included"]}
    if not scenario["order_evidence_available"]:
        return {"refund_cents": None, "reason": "Abstain: verified order evidence unavailable; manual review required.",
                "evidence_ids": ["policy.evidence", "order.receipt"]}
    if "policy.exception" in ids:
        return {"refund_cents": 0, "reason": "Prior compensation exception prohibits an additional draft refund.",
                "evidence_ids": ["policy.base", "policy.exception", "order.receipt"]}
    amount = scenario["order_total_cents"] // 5 if scenario["delay_minutes"] >= 30 else 0
    return {"refund_cents": amount, "reason": "Apply base delay policy to included context; no exception was present.",
            "evidence_ids": ["policy.base", "order.receipt"]}


def execute_scenario(scenario_id: str, policy: str, parent_run_id: str | None = None) -> dict:
    start = perf_counter()
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    scenario = get_scenario(scenario_id)
    blocks = assemble_context(scenario, policy)
    decision = reference_decision(blocks, scenario)
    grade = grade_decision(scenario_id, decision)
    events: list[dict] = []

    def record(event_type: str, title: str, summary: str, payload: dict) -> None:
        event = {"run_id": run_id, "seq": len(events) + 1, "event_type": event_type,
                 "title": title, "summary": summary, "created_at": datetime.now(timezone.utc).isoformat(),
                 "payload": payload, "prev_hash": events[-1]["event_hash"] if events else GENESIS_HASH}
        event["event_hash"] = hash_event(event)
        events.append(event)

    record("run.started", "Controlled run started", "Execute a synthetic order-support task with no external side effects.",
           {"scenario_id": scenario_id, "policy": policy, "runner": "deterministic-reference-policy", "parent_run_id": parent_run_id})
    record("tool.result", "Synthetic order evidence loaded", "Read the versioned local fixture; no live merchant account accessed.",
           {"tool": "synthetic.order.lookup", "result": scenario})
    record("context.assembled", "Context assembled", "Capture every policy and order block before compaction.", {"blocks": blocks})
    omitted = [b["id"] for b in blocks if not b["included"]]
    record("context.selected", "Context policy applied", f"{policy} policy omitted {len(omitted)} block(s).",
           {"policy": policy, "included_ids": [b["id"] for b in blocks if b["included"]],
            "omitted_ids": omitted, "reason": "Reference compactor drops exception blocks." if omitted else "All available evidence retained."})
    record("decision.drafted", "Draft adjustment produced", decision["reason"], decision)
    record("grade.completed", "Independent grader completed", "Complete synthetic truth is compared with the draft.", grade)
    record("run.stopped", "Loop stopped", "One bounded read-only policy pass; no payment tools or model calls.",
           {"reason": "manual_review" if not grade["passed"] or decision["refund_cents"] is None else "draft_complete",
            "steps": 1, "external_effects": 0, "model_calls": 0})
    return {
        "id": run_id, "slug": run_id, "title": scenario["title"], "summary": scenario["summary"],
        "scenario_id": scenario_id, "policy": policy,
        "status": "failed" if not grade["passed"] else ("abstained" if decision["refund_cents"] is None else "passed"),
        "created_at": created_at, "event_count": len(events),
        "provenance": "Synthetic scenario; executed deterministic reference policy; no LLM or external effects.",
        "parent_run_id": parent_run_id, "grade_passed": grade["passed"],
        "task": "Review a delayed synthetic order and draft an adjustment. Respect prior compensation and abstain when evidence is missing.",
        "scenario": scenario, "context_blocks": blocks, "events": events, "decision": decision, "grade": grade,
        "duration_ms": round((perf_counter() - start) * 1000, 3),
        "configuration": {"runner": "deterministic-reference-policy", "model": None, "policy_version": "synthetic-policy-v1",
                          "external_effects": False, "model_calls": 0},
        "lineage": {"parent_run_id": parent_run_id, "fork_seq": None,
                    "mode": "fresh-isolated-scenario-rerun" if parent_run_id else "initial-controlled-run"},
    }
