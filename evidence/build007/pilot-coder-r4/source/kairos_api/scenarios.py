"""Synthetic, versioned fixtures; grader reads these independently of context."""
from copy import deepcopy

SCENARIOS = {
    "late-order-exception": {
        "order_id": "SYN-1042", "order_total_cents": 2400, "delay_minutes": 47,
        "policy_exception": True, "order_evidence_available": True,
        "title": "The exception that disappeared",
        "summary": "Compaction drops a policy exception from a late-order review.",
    },
    "late-order-standard": {
        "order_id": "SYN-1043", "order_total_cents": 1800, "delay_minutes": 42,
        "policy_exception": False, "order_evidence_available": True,
        "title": "A straightforward late-order review",
        "summary": "A standard delayed order qualifies for a bounded draft adjustment.",
    },
    "insufficient-evidence": {
        "order_id": "SYN-1044", "order_total_cents": None, "delay_minutes": None,
        "policy_exception": False, "order_evidence_available": False,
        "title": "When evidence runs out",
        "summary": "Missing order evidence must produce abstention, not an invented amount.",
    },
}


def get_scenario(scenario_id: str) -> dict:
    return deepcopy(SCENARIOS[scenario_id])


def assemble_context(scenario: dict, policy: str) -> list[dict]:
    blocks = [
        {"id": "policy.base", "label": "Late-order policy", "source": "synthetic-policy-v1",
         "content": "If verified delay is at least 30 minutes, draft a 20% refund rounded down to cents. Never execute payment.",
         "included": True},
        {"id": "policy.evidence", "label": "Evidence requirement", "source": "synthetic-policy-v1",
         "content": "If order amount or delay evidence is unavailable, abstain and request manual review.",
         "included": True},
        {"id": "order.receipt", "label": "Order receipt", "source": "synthetic-order-service-v1",
         "content": (f"Order {scenario['order_id']}: total_cents={scenario['order_total_cents']}; delay_minutes={scenario['delay_minutes']}; "
                     f"evidence_available={scenario['order_evidence_available']}"), "included": True},
    ]
    if scenario["policy_exception"]:
        blocks.append({
            "id": "policy.exception", "label": "Prior compensation exception",
            "source": "synthetic-policy-v1",
            "content": "This order already received compensation. Draft refund must be 0 cents; do not compensate twice.",
            "included": policy == "preserve",
        })
    return blocks
