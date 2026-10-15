"""Offline experimental tests: no inference, Docker, credentials or source reads."""
import copy
import hashlib
import json
from unittest.mock import patch

import httpx
import pytest

from scripts.repair010.feedback010 import (
    FeedbackContextOverflow010, FeedbackInvestigator010, FeedbackWorker010,
    observations_from_record010, rejection_feedback010,
)
from kairos_api.investigations.model import LocalInvestigator
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.model_runtime import digest


def capture():
    source = "def example(value):\n    if value:\n        return value\n    return None\n"
    reference = {"path": "package/core.py", "source_digest": hashlib.sha256(source.encode()).hexdigest(),
                 "start_line": 10, "end_line": 13}
    reference["excerpt_id"] = digest({**reference, "text": source})
    result = {"reference": reference, "source": "original_snapshot", "text": "".join(
        f"{index}: {line}" for index, line in enumerate(source.splitlines(keepends=True), 10))}
    handle = "S" + reference["excerpt_id"][:12]
    context = {"reference_bindings": {handle: reference}, "source_catalog": [result]}
    request = {"action": "propose_patch", "model_seq": 3, "edits": [
        {"source_id": handle, "start_line": 11, "end_line": 12,
         "new": "11: if value:\n12: return value\n"}]}
    error = {"error": "Candidate Python syntax rejected at line 11: invalid syntax"}
    record = {"integrity": {"verified": True}, "steps": [
        {"seq": 1, "kind": "tool", "name": "initial_source", "state": "captured",
         "request": {"body": {"origin": "issue"}}, "result": {"body": result}},
        {"seq": 2, "kind": "context", "name": "selection", "state": "captured",
         "request": {"body": {}}, "result": {"body": context}},
        {"seq": 3, "kind": "model", "name": "dispatch", "state": "captured",
         "request": {"body": {}}, "result": {"body": {}}},
        {"seq": 4, "kind": "tool", "name": "propose_patch", "state": "captured",
         "request": {"body": request}, "result": {"body": error}},
    ]}
    observations = [{"action": "initial_source", "result": result},
                    {"action": "propose_patch", "result": error}]
    return record, observations


def restored():
    record, observations = capture()
    return observations_from_record010(record, observations)


def test_durable_recovery_retains_exact_request_and_original_dispatch_context():
    record, observations = capture()
    before = copy.deepcopy((record, observations))
    first = observations_from_record010(record, observations)
    recovered = observations_from_record010(copy.deepcopy(record), copy.deepcopy(observations))
    assert first == recovered
    assert first[-1]["request"] == record["steps"][-1]["request"]["body"]
    assert first[-1]["proposal_context"]["sequence"] == 2
    assert (record, observations) == before
    # A later context cannot retroactively authorize the rejected edit.
    future = copy.deepcopy(record["steps"][1]); future["seq"] = 5
    future["result"]["body"]["source_catalog"] = []
    record["steps"].append(future)
    assert observations_from_record010(record, observations) == first


def test_worker_adapter_changes_only_observations():
    record, observations = capture()
    state = (record, observations, "unchanged patch", {"passed": False}, True)
    worker = FeedbackWorker010(repository=object(), provider=object())
    with patch.object(InvestigationWorker, "_state", return_value=state):
        actual = worker._state({"configuration": "loop-v7"}, object())
        historical = worker._state({"configuration": "loop-v6"}, object())
    assert actual[0] is record
    assert actual[2:] == state[2:]
    assert actual[1][-1]["request"]["edits"][0]["new"] == "11: if value:\n12: return value\n"
    assert historical == state


def test_feedback_exact_replacement_rejection_indentation_and_prefixes():
    observations = restored()
    feedback = rejection_feedback010(observations)
    assert feedback["rejection_reason"] == observations[-1]["result"]["error"]
    edit = feedback["edits"][0]
    assert edit["replacement"] == observations[-1]["request"]["edits"][0]["new"]
    assert edit["coordinate_valid"] is True
    assert edit["captured_bounds"] == [10, 13]
    assert edit["original_indentation"] == [{"line": 11, "whitespace": "    "},
                                            {"line": 12, "whitespace": "        "}]
    assert edit["replacement_diagnostics"]["numbered_line_prefixes"] == [1, 2]
    assert edit["replacement_diagnostics"]["indentation"] == [
        {"line": 1, "whitespace": ""}, {"line": 2, "whitespace": ""}]


@pytest.mark.parametrize("start,end", [(9, 12), (11, 14), (12, 11), (True, 12)])
def test_out_of_bounds_coordinates_reported_without_correction(start, end):
    observations = restored()
    observations[-1]["request"]["edits"][0].update(start_line=start, end_line=end)
    feedback = rejection_feedback010(observations)
    edit = feedback["edits"][0]
    assert edit["coordinate_valid"] is False
    assert "escapes" in edit["coordinate_error"]
    assert edit["start_line"] == start and edit["end_line"] == end


@pytest.mark.parametrize("mutation,expected", [
    ("unknown_handle", "absent"), ("source_digest", "malformed"),
    ("excerpt", "digest changed"), ("missing_region", "missing"),
    ("malicious_path", "approved source path"), ("numbering", "numbering"),
])
def test_invalid_source_authority_is_explicit(mutation, expected):
    observations = restored()
    latest = observations[-1]
    edit = latest["request"]["edits"][0]
    context = latest["proposal_context"]
    reference = context["reference_bindings"][edit["source_id"]]
    if mutation == "unknown_handle":
        edit["source_id"] = "S000000000000"
    elif mutation == "source_digest":
        reference["source_digest"] = "stale"
    elif mutation == "excerpt":
        context["source_catalog"][0]["text"] = context["source_catalog"][0]["text"].replace(
            "return None", "return False")
    elif mutation == "missing_region":
        context["source_catalog"] = []
    elif mutation == "malicious_path":
        reference["path"] = "../../private/reference.patch"
    elif mutation == "numbering":
        context["source_catalog"][0]["text"] = "wrong source numbering"
    edit = rejection_feedback010(observations)["edits"][0]
    assert edit["coordinate_valid"] is False
    assert expected in edit["coordinate_error"]


def test_oversized_replacement_is_omitted_whole_with_exact_hash_and_bytes():
    observations = restored()
    authored = "    value = 'é'\n" * 3000
    observations[-1]["request"]["edits"][0]["new"] = authored
    feedback = rejection_feedback010(observations, maximum_bytes=2400)
    assert "replacement" not in feedback["edits"][0]
    omission = next(item for item in feedback["omissions"] if item["field"] == "edits.0.replacement")
    assert omission["sha256"] == hashlib.sha256(authored.encode()).hexdigest()
    assert omission["bytes"] == len(authored.encode())
    assert len(json.dumps(feedback, ensure_ascii=False).encode()) < 2600
    assert feedback["rejection_reason"] == observations[-1]["result"]["error"]


def test_missing_request_is_not_invented_and_success_supersedes_old_rejection():
    observations = restored()
    observations[-1].pop("request")
    assert rejection_feedback010(observations)["request_unavailable"] is True
    observations.append({"action": "propose_patch", "result": {"patch": "accepted"}})
    assert rejection_feedback010(observations) is None


def test_untrusted_or_mismatched_record_rejected():
    record, observations = capture()
    record["integrity"]["verified"] = False
    with pytest.raises(ValueError, match="verified durable"):
        observations_from_record010(record, observations)
    record["integrity"]["verified"] = True
    with pytest.raises(ValueError, match="tool history"):
        observations_from_record010(record, observations[:-1])


def test_feedback_reads_no_source_or_hidden_material_and_does_not_edit_candidate():
    observations = restored()
    before = copy.deepcopy(observations)
    with patch("builtins.open", side_effect=AssertionError("filesystem access forbidden")):
        feedback = rejection_feedback010(observations)
    assert feedback["edits"][0]["replacement"] == before[-1]["request"]["edits"][0]["new"]
    assert observations == before


def base_prepared():
    selection = {"issue": "public defect", "source_blocks": [{"source_id": "S000000000000"}]}
    request = {"messages": [{"role": "system", "content": "existing system"},
                             {"role": "user", "content": json.dumps(selection)}],
               "max_tokens": 1024, "chat_template_kwargs": {"enable_thinking": False},
               "response_format": {"unchanged": True}, "temperature": 0}
    context = {"selection": selection, "omissions": [], "rendered_input_tokens": 900,
               "reference_bindings": {"unchanged": "authority"}}
    return request, context


def test_provider_preserves_generation_schema_authority_and_measures_final_prompt():
    provider = FeedbackInvestigator010()
    request, context = base_prepared()
    original = copy.deepcopy((request, context))
    with patch.object(LocalInvestigator, "prepare", return_value=(request, context)), \
            patch.object(provider, "_measure_messages010", return_value=1800) as measure:
        actual, captured = provider.prepare({}, "loop-v7", restored(), {"calls_remaining": 4})
    assert (request, context) == original
    assert actual["response_format"] == request["response_format"]
    assert actual["max_tokens"] == 1024 and actual["temperature"] == 0
    assert captured["reference_bindings"] == context["reference_bindings"]
    assert captured["rendered_input_tokens"] == 1800
    assert json.loads(actual["messages"][-1]["content"])["rejected_proposal_feedback010"]["edits"][0]["replacement"]
    assert measure.call_args.args[0] == actual["messages"]
    assert captured["selection"]["source_blocks"] == context["selection"]["source_blocks"]


def test_provider_oversized_rendered_feedback_fails_explicitly_without_silent_truncation():
    provider = FeedbackInvestigator010()
    prepared = base_prepared()
    prepared[1]["selection"]["current_candidate"] = None
    with patch.object(LocalInvestigator, "prepare", return_value=prepared), \
            patch.object(provider, "_measure_messages010", return_value=3041):
        with pytest.raises(FeedbackContextOverflow010, match="3041 input.*1024 output.*32 reserve"):
            provider.prepare({}, "loop-v7", restored(), {})


def test_initial_prompt_unchanged_until_rejection_and_non_v7_refused():
    provider = FeedbackInvestigator010()
    request, context = base_prepared()
    with patch.object(LocalInvestigator, "prepare", return_value=(request, context)), \
            patch.object(provider, "_measure_messages010") as measure:
        actual, captured = provider.prepare({}, "loop-v7", [], {})
    assert actual == request and not measure.called
    assert captured["experimental_protocol"]
    with pytest.raises(ValueError, match="only supports"):
        provider.prepare({}, "loop-v6", [], {})


def test_only_optional_complete_parent_fields_removed_before_feedback_overflow():
    provider = FeedbackInvestigator010()
    request, context = base_prepared()
    context["selection"].update(recent_tools=[{"action": "search", "matches": ["old"]}],
                                 current_candidate={"patch_digest": "keep", "edits": ["old candidate"]},
                                 budgets={"calls_remaining": 3}, latest_verification={"passed": False})
    with patch.object(LocalInvestigator, "prepare", return_value=(request, context)), \
            patch.object(provider, "_measure_messages010", side_effect=[4000, 3500, 2000]):
        actual, captured = provider.prepare({}, "loop-v7", restored(), {})
    selection = json.loads(actual["messages"][-1]["content"])
    assert selection["current_candidate"] == {"patch_digest": "keep"}
    assert selection["recent_tools"] == []
    assert selection["source_blocks"] == context["selection"]["source_blocks"]
    assert selection["budgets"] == {"calls_remaining": 3}
    assert selection["latest_verification"] == {"passed": False}
    assert selection["rejected_proposal_feedback010"]["edits"][0]["replacement"].startswith("11: ")
    assert [item["field"] for item in captured["omissions"]] == ["recent_tools", "current_candidate.edits"]
    assert all("sha256" in item for item in captured["omissions"])


def test_measurement_uses_rendered_chat_template_and_real_tokenizer_endpoint():
    provider = FeedbackInvestigator010()
    calls = []
    def response(request):
        calls.append((request.url.path, json.loads(request.content)))
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": "rendered complete chat"})
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": [1, 2, 3]})
        raise AssertionError("No inference dispatch is permitted")
    original_client = httpx.Client
    with patch("scripts.repair010.feedback010.httpx.Client", side_effect=lambda **kwargs: original_client(
            transport=httpx.MockTransport(response), **kwargs)):
        count = provider._measure_messages010(
            [{"role": "user", "content": "complete JSON"}],
            {"chat_template_kwargs": {"enable_thinking": False}})
    assert count == 3
    assert calls[0][0] == "/apply-template"
    assert calls[0][1]["add_generation_prompt"] is True
    assert calls[1] == ("/tokenize", {"content": "rendered complete chat", "add_special": True})


def test_existing_v7_prepare_and_feedback_adapter_integrate_without_inference():
    calls = []
    def response(request):
        calls.append(request.url.path)
        body = json.loads(request.content)
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": json.dumps(body["messages"])})
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": list(range(1800))})
        raise AssertionError("Inference must not run in an offline test")
    original_client = httpx.Client
    provider = FeedbackInvestigator010()
    case = {"id": "offline-public-example", "issue": "example(value) should retain its public behavior.",
            "revision": "public-source-revision", "approved_prefix": "package"}
    budgets = {"calls_remaining": 4, "patches_remaining": 2, "checks_remaining": 2}
    with patch("scripts.repair010.feedback010.httpx.Client", side_effect=lambda **kwargs: original_client(
            transport=httpx.MockTransport(response), **kwargs)):
        request, context = provider.prepare(case, "loop-v7", restored(), budgets)
    assert calls == ["/apply-template", "/tokenize", "/apply-template", "/tokenize"]
    selection = json.loads(request["messages"][-1]["content"])
    assert selection["source_blocks"] and selection["budgets"]["calls_remaining"] == 4
    assert selection["latest_error"]["error"] == selection["rejected_proposal_feedback010"]["rejection_reason"]
    assert selection["rejected_proposal_feedback010"]["edits"][0]["coordinate_valid"] is True
    assert request["max_tokens"] == 1024
    assert context["rendered_input_tokens"] == 1800
    assert context["reference_bindings"]
