"""Contract and offline classification checks; not model-quality observations."""
import pytest
from kairos_api.model_runtime import BlobStore, classify_and_grade, model_request
from kairos_api.scenarios import get_scenario, assemble_context


def classify(scenario,raw,policy="preserve"):
    return classify_and_grade(scenario,assemble_context(get_scenario(scenario),policy),{"raw_response":raw})


def test_deterministic_arithmetic_and_independent_truth():
    result = classify("late-order-standard",'{"disposition":"refund","reason":"Late","evidence_ids":["policy.base","order.receipt"]}')
    assert result["decision"]["refund_cents"] == 360 and result["grade"]["passed"]
    failure = classify("late-order-exception",'{"disposition":"refund","reason":"Late","evidence_ids":["policy.base","order.receipt"]}',"compact")
    assert failure["decision"]["refund_cents"] == 480 and not failure["grade"]["passed"]
    abstain = classify("insufficient-evidence",'{"disposition":"abstain","reason":"Missing","evidence_ids":["policy.evidence","order.receipt"]}')
    assert abstain["decision"]["refund_cents"] is None and abstain["grade"]["passed"]


@pytest.mark.parametrize("raw",[
    "```json\n{}\n```", "{}", "[]",'{"disposition":"refund","reason":"x","evidence_ids":["invented"]}',
    '{"disposition":"refund","reason":"x","evidence_ids":[]}',
    '{"disposition":"refund","reason":"x","evidence_ids":["policy.base"],"refund_cents":999}',
    '{"disposition":"unknown","reason":"x","evidence_ids":["policy.base"]}',
    '{"disposition":"zero","reason":"","evidence_ids":["policy.base"]}',
    '{"disposition":"zero","reason":"x","evidence_ids":["policy.base","policy.base"]}',
])
def test_strict_unrepaired_output_failures(raw):
    result = classify("late-order-standard",raw)
    assert result["decision"] is None and not result["grade"]["passed"] and result["parse_error"]


def test_omitted_exception_never_enters_model_request():
    blocks = assemble_context(get_scenario("late-order-exception"),"compact")
    request = model_request(blocks)
    assert "[policy.exception]" not in request["messages"][1]["content"]
    assert request["max_tokens"] == 128 and request["temperature"] == 0


def test_content_addressed_blob_atomic_capture_and_corruption(tmp_path):
    store = BlobStore(tmp_path)
    first = store.put({"raw_response":"exact\n spacing"})
    assert first == store.put({"raw_response":"exact\n spacing"})
    assert store.get(first["sha256"])["raw_response"] == "exact\n spacing"
    with pytest.raises(ValueError):
        store.get("../secret")
    (tmp_path/first["sha256"]).write_text("changed")
    with pytest.raises(ValueError,match="mismatch"):
        store.get(first["sha256"])


def test_reason_bound_and_required_disposition_provenance():
    import json
    long_reason = json.dumps({"disposition":"zero","reason":"x"*2001,"evidence_ids":["policy.exception"]})
    assert classify("late-order-exception",long_reason)["parse_error"]
    assert classify("late-order-exception",'{"disposition":"zero","reason":"Exception","evidence_ids":["order.receipt"]}')["parse_error"]
    assert classify("insufficient-evidence",'{"disposition":"abstain","reason":"Missing","evidence_ids":["order.receipt"]}')["parse_error"]


@pytest.mark.parametrize("raw",[
    '{"disposition":"refund","disposition":"zero","reason":"x","evidence_ids":["policy.base"]}',
    '{"disposition":"zero","reason":"x","evidence_ids":["policy.base"],"extra":NaN}',
])
def test_duplicate_and_nonfinite_json_rejected(raw):
    assert classify("late-order-standard",raw)["parse_error"]
