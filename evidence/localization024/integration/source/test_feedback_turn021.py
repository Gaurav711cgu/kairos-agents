"""Mocked-generation checks for one bounded 021 feedback turn; no model, no Docker."""
import json

import pytest

from kairos_api.investigations.context_v7 import source_block
from scripts.feedback_turn021 import MAX_FEEDBACK_TURNS, next_turn021, validate021
from scripts.repair010.feedback010 import FeedbackContextOverflow010
from scripts.source_edit_protocol021 import messages
from test_coding_context014 import make_workspace

TEXT = 'def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n'
ISSUE = 'total() in package/value.py returns the wrong sum'


@pytest.fixture
def case(tmp_path):
    w = make_workspace(tmp_path, TEXT, ISSUE)
    regions = [w.read_original('package/value.py', 1, 5)]
    handle = source_block(regions[0])['source_id']
    yield w, regions, handle, messages(ISSUE, [source_block(r) for r in regions])
    w.close()


def action(handle, start, end, new):
    return json.dumps({'action': 'propose_patch', 'edits': [{'source_id': handle, 'start_line': start, 'end_line': end, 'new': new}]})


def test_accepted_edit_gets_no_feedback_turn(case):
    w, regions, handle, first = case
    text = action(handle, 4, 4, '        result += value * 1\n')
    verdict = validate021(w, text, regions)
    assert verdict['accepted'] and verdict['patch'].startswith('--- a/package/value.py')
    assert next_turn021(first, regions, verdict) is None


def test_indentation_rejection_returns_exact_feedback_without_a_correction(case):
    w, regions, handle, first = case
    text = action(handle, 4, 4, 'result += value\n')  # first line lost its indentation
    verdict = validate021(w, text, regions)
    assert not verdict['accepted'] and 'syntax rejected' in verdict['reason']
    second = next_turn021(first, regions, verdict)
    # Same two-message protocol shape; turn-one payload kept, one feedback key added.
    assert [m['role'] for m in second] == ['system', 'user'] and second[0] == first[0]
    payload, original = json.loads(second[1]['content']), json.loads(first[1]['content'])
    assert {k: v for k, v in payload.items() if k != 'rejected_attempt'} == original
    feedback = payload['rejected_attempt']['feedback']
    edit = feedback['edits'][0]
    assert edit['coordinate_valid'] and edit['original_indentation'][0]['whitespace'] == '        '
    assert edit['replacement_diagnostics']['indentation'][0]['whitespace'] == ''
    assert 'corrected' not in json.dumps(feedback) and feedback['rejection_reason'] == verdict['reason']


def test_unparseable_output_still_gets_bounded_reason(case):
    w, regions, _, first = case
    verdict = validate021(w, 'not json', regions)
    assert not verdict['accepted'] and verdict['stage'] == 'parse'
    feedback = json.loads(next_turn021(first, regions, verdict)[1]['content'])['rejected_attempt']['feedback']
    assert feedback['request_unavailable'] is True and feedback['edits'] == []


def test_range_outside_captured_excerpt_is_reported_as_coordinates(case):
    w, regions, handle, first = case
    text = action(handle, 4, 9, '        result += value\n')
    verdict = validate021(w, text, regions)
    assert not verdict['accepted']
    edit = json.loads(next_turn021(first, regions, verdict)[1]['content'])['rejected_attempt']['feedback']['edits'][0]
    assert edit['coordinate_valid'] is False and 'escapes' in edit['coordinate_error']


def test_retry_limit_is_one_feedback_turn(case):
    w, regions, handle, first = case
    text = action(handle, 4, 4, 'result += value\n')
    verdict = validate021(w, text, regions)
    assert MAX_FEEDBACK_TURNS == 1
    second = next_turn021(first, regions, verdict)
    # A prompt that already carries feedback never earns another turn, whatever the caller claims.
    assert next_turn021(second, regions, verdict) is None


def test_feedback_respects_byte_budget(case):
    w, regions, handle, first = case
    text = action(handle, 4, 4, 'x' * 9000 + '\n')
    verdict = validate021(w, text, regions)
    content = next_turn021(first, regions, verdict, maximum_bytes=1500)[1]['content']
    added = len(content.encode()) - len(first[1]['content'].encode())
    assert len(json.loads(content)['rejected_attempt']['feedback']['omissions']) >= 1 and added < 2000


def test_prompt_token_cap_fails_closed(case):
    w, regions, handle, first = case
    text = action(handle, 4, 4, 'result += value\n')
    verdict = validate021(w, text, regions)
    counter = type('Counter', (), {'apply_chat_template': lambda self, m, **_: [0] * sum(len(x['content']) for x in m)})()
    with pytest.raises(FeedbackContextOverflow010):
        next_turn021(first, regions, verdict, tokenizer=counter, maximum_prompt_tokens=10)
    assert next_turn021(first, regions, verdict, tokenizer=counter, maximum_prompt_tokens=10**6)


def test_validation_never_changes_original_source(case):
    w, regions, handle, _ = case
    validate021(w, action(handle, 4, 4, 'result += value\n'), regions)
    validate021(w, action(handle, 4, 4, '        result += value * 1\n'), regions)
    assert (w.registry.directory(w.case) / 'source/package/value.py').read_text() == TEXT


def test_deeply_nested_output_is_a_parse_rejection_not_a_crash(case):
    w, regions, _, _ = case
    verdict = validate021(w, '[' * 60000, regions)
    assert not verdict['accepted'] and verdict['stage'] == 'parse'
