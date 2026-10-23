"""F024 offline harness with mocked generations only; no model, Colab or Docker."""
import json

from kairos_api.investigations.context_v7 import source_block
from scripts.f024 import ENVELOPE_TOKENS, TURN1_MAX_NEW, TURN2_MAX_NEW, classify, preflight, turn2
from scripts.feedback_turn021 import validate021
from scripts.source_edit_protocol021 import messages
from test_coding_context014 import make_workspace

TEXT = 'def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n'


class Counter:
    def apply_chat_template(self, m, **_):
        return [0] * (sum(len(x['content']) for x in m) // 4)


def edit(handle, new):
    return json.dumps({'action': 'propose_patch', 'edits': [{'source_id': handle, 'start_line': 4, 'end_line': 4, 'new': new}]})


def test_preflight_is_conservative_and_fails_closed():
    assert ENVELOPE_TOKENS == 3539 and TURN2_MAX_NEW == 512 and TURN1_MAX_NEW == 1024
    assert preflight(2515, TURN1_MAX_NEW) and not preflight(2516, TURN1_MAX_NEW)
    assert preflight(3027, TURN2_MAX_NEW) and not preflight(3028, TURN2_MAX_NEW)


def test_classification_separates_failure_classes(tmp_path):
    w = make_workspace(tmp_path, TEXT, 'total() is wrong')
    regions = [w.read_original('package/value.py', 1, 5)]
    h = source_block(regions[0])['source_id']
    try:
        assert classify(validate021(w, edit(h, '        result += value * 1\n'), regions)) == 'accepted'
        assert classify(validate021(w, edit(h, 'result += value\n'), regions)) == 'syntax_indentation'
        assert classify(validate021(w, edit(h, '        result += (value\n'), regions)) == 'syntax_other'
        assert classify(validate021(w, edit(h, '        result += value\n'), regions)) == 'no_change'
        assert classify(validate021(w, 'nope', regions)) == 'parse'
        assert classify(validate021(w, edit('S000000000000', 'x\n'), regions)) == 'parse'
    finally:
        w.close()


def test_turn2_only_for_rejected_fitting_jobs(tmp_path):
    w = make_workspace(tmp_path, TEXT, 'total() is wrong')
    regions = [w.read_original('package/value.py', 1, 5)]
    h = source_block(regions[0])['source_id']
    first = messages('total() is wrong', [source_block(r) for r in regions])
    jobs = [{'job_id': 'a/issue/t1', 'messages': first}, {'job_id': 'b/issue/t1', 'messages': first}, {'job_id': 'c/issue/t1', 'messages': first}]
    jobs.append({'job_id': 'd/issue/t1', 'messages': first})
    captures = {'a/issue/t1': edit(h, '        result += value * 1\n'), 'b/issue/t1': edit(h, 'result += value\n'), 'c/issue/t1': None,
                'd/issue/t1': 'not json'}
    try:
        planned, ledger = turn2(jobs, captures, lambda job: (w, regions), Counter())
        # Parser rejections are intended feedback targets too (schema errors were 6/27 historically).
        assert [j['job_id'] for j in planned] == ['b/issue/t2', 'd/issue/t2']
        assert ledger == {'a/issue/t1': 'accepted', 'b/issue/t1': 'syntax_indentation', 'c/issue/t1': 'generation_missing', 'd/issue/t1': 'parse'}
        assert planned[0]['max_new_tokens'] == TURN2_MAX_NEW and 'rejected_attempt' in planned[0]['messages'][1]['content']
    finally:
        w.close()
