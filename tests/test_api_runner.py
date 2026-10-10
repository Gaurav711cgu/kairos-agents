"""Independent correctness and consistency tests; no database or model required."""
from copy import deepcopy

import pytest

from kairos_api.grading import grade_decision
from kairos_api.integrity import request_digest, verify_events
from kairos_api.runner import execute_scenario


@pytest.mark.parametrize("scenario,policy,expected,passed", [
    ("late-order-exception", "compact", 480, False),
    ("late-order-exception", "preserve", 0, True),
    ("late-order-standard", "compact", 360, True),
    ("insufficient-evidence", "compact", None, True),
])
def test_reference_policy_detects_exception_loss_and_abstains(scenario, policy, expected, passed):
    run = execute_scenario(scenario, policy)
    assert run["decision"]["refund_cents"] == expected
    assert run["grade_passed"] is passed
    assert run["configuration"]["model"] is None
    assert run["configuration"]["runner"] == "deterministic-reference-policy"
    assert verify_events(run["events"], run["event_count"], run["events"][-1]["event_hash"])
    assert run["events"][-1]["payload"]["external_effects"] == 0


def test_grader_does_not_trust_agent_claim_and_rejects_bool_as_amount():
    decision = {"refund_cents": 480, "reason": "I passed all checks", "evidence_ids": ["policy.base"]}
    assert not grade_decision("late-order-exception", decision)["passed"]
    decision["refund_cents"] = False
    assert not grade_decision("late-order-exception", decision)["passed"]


@pytest.mark.parametrize("mutation", ["edit", "truncate", "reorder", "cross-run", "head"])
def test_chain_detects_content_order_truncation_and_run_changes(mutation):
    run = execute_scenario("late-order-exception", "compact")
    events = deepcopy(run["events"])
    head = events[-1]["event_hash"]
    if mutation == "edit":
        events[2]["payload"]["blocks"][0]["content"] = "Forged policy"
    elif mutation == "truncate":
        events.pop()
    elif mutation == "reorder":
        events[1], events[2] = events[2], events[1]
    elif mutation == "cross-run":
        events[1]["run_id"] = "different-run"
    else:
        head = "f" * 64
    assert not verify_events(events, run["event_count"], head)


def test_fork_is_new_execution_with_parent_lineage_not_checkpoint_claim():
    first = execute_scenario("late-order-exception", "compact")
    fork = execute_scenario("late-order-exception", "preserve", first["id"])
    assert first["id"] != fork["id"]
    assert fork["lineage"] == {"parent_run_id": first["id"], "fork_seq": None, "mode": "fresh-isolated-scenario-rerun"}
    assert first["grade_passed"] is False and fork["grade_passed"] is True


def test_digest_ignores_dictionary_order_but_not_configuration():
    assert request_digest({"a": 1, "b": 2}) == request_digest({"b": 2, "a": 1})
    assert request_digest({"policy": "compact"}) != request_digest({"policy": "preserve"})


def test_abstention_requires_explicit_null_and_structured_evidence():
    decision = {"reason": "Missing evidence", "evidence_ids": ["policy.evidence"]}
    assert not grade_decision("insufficient-evidence", decision)["passed"]
    decision["refund_cents"] = None
    assert grade_decision("insufficient-evidence", decision)["passed"]
    decision["evidence_ids"] = "policy.evidence"
    assert not grade_decision("insufficient-evidence", decision)["passed"]


def test_chain_requires_expected_run_identity_even_if_every_event_is_consistent():
    run = execute_scenario("late-order-standard", "preserve")
    assert not verify_events(run["events"], run["event_count"], run["events"][-1]["event_hash"], "wrong-run")
