"""Independent ground-truth grader; never reads runner context or reason text."""
from kairos_api.scenarios import get_scenario


def grade_decision(scenario_id: str, decision: dict) -> dict:
    truth = get_scenario(scenario_id)
    if not truth["order_evidence_available"]:
        expected = None
    elif truth["policy_exception"] or truth["delay_minutes"] < 30:
        expected = 0
    else:
        expected = truth["order_total_cents"] // 5
    actual = decision.get("refund_cents")
    evidence_ids = decision.get("evidence_ids", [])
    shape_ok = ("refund_cents" in decision and (actual is None or (type(actual) is int and actual >= 0))
                and isinstance(decision.get("reason"), str) and bool(decision["reason"].strip())
                and isinstance(evidence_ids, list) and all(isinstance(x, str) for x in evidence_ids))
    amount_ok = shape_ok and actual == expected
    allowed = {"policy.base", "policy.evidence", "order.receipt", "policy.exception"}
    evidence_ok = shape_ok and bool(evidence_ids) and all(x in allowed for x in evidence_ids)
    if expected is None:
        evidence_ok = evidence_ok and "policy.evidence" in evidence_ids
    if truth["policy_exception"]:
        evidence_ok = evidence_ok and "policy.exception" in evidence_ids
    checks = [
        {"name": "decision_schema", "passed": shape_ok, "detail": "Draft amount must be nonnegative integer cents or explicit abstention."},
        {"name": "independent_policy_match", "passed": amount_ok,
         "detail": f"Synthetic source-of-truth expects {expected!r}; observed {actual!r}."},
        {"name": "evidence_reference", "passed": evidence_ok,
         "detail": "Decision must cite available policy/order identifiers, including applicable exceptions or abstention policy."},
    ]
    return {"passed": all(c["passed"] for c in checks), "expected_refund_cents": expected,
            "actual_refund_cents": actual, "checks": checks,
            "grader": "independent-synthetic-policy-v1"}
