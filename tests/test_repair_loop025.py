"""Bounded SEARCH/REPLACE repair loop on synthetic defects with a scripted (mock) model.

Mock replies are written by the test author; passing here proves the loop mechanics, never model skill.
"""
import json
from uuid import uuid4

from test_coding_context014 import make_workspace
from scripts.repair_loop025 import run_loop, subprocess_check

BUGGY = 'import os\n\n\ndef add(a, b):\n    return a - b\n\n\ndef home():\n    return os.sep\n'
PUBLIC = 'import package.value as v\nassert v.add(2, 3) == 5, v.add(2, 3)\n'  # visible to the model too
REGIONS = [{'path': 'package/value.py', 'start_line': 1, 'end_line': 9}]


def block(search, replace):
    return f'Fix.\npackage/value.py\n<<<<<<< SEARCH\n{search}=======\n{replace}>>>>>>> REPLACE\n'


GOOD = block('    return a - b\n', '    return a + b\n')


def scripted(*replies):
    seen = []

    def model(messages):
        seen.append([dict(m) for m in messages])
        return replies[len(seen) - 1]
    model.seen = seen
    return model


def loop(tmp_path, model, **kwargs):
    w = make_workspace(tmp_path / uuid4().hex, BUGGY, 'add returns the wrong value')
    receipts = tmp_path / 'receipts.jsonl'
    try:
        result = run_loop(model, w, 'add(2, 3) should be 5', REGIONS, subprocess_check(PUBLIC), receipts, **kwargs)
        candidate = (w.root / 'package/value.py').read_text()
        original = (w.registry.directory(w.case) / 'source/package/value.py').read_text()
    finally:
        w.close()
    assert original == BUGGY  # the original snapshot is never written
    return result, candidate, [json.loads(line) for line in receipts.read_text().splitlines()]


def test_first_try_fix_is_accepted_after_the_public_check(tmp_path):
    result, candidate, receipts = loop(tmp_path, scripted(GOOD))
    assert result['status'] == 'accepted' and result['calls'] == 1
    assert 'return a + b' in candidate and '+    return a + b' in result['patch']
    assert receipts[-1]['kind'] == 'accepted'


def test_feedback_is_a_separate_user_message_after_the_model_reply(tmp_path):
    model = scripted(block('return a - c\n', 'x\n'), GOOD)
    result, _, _ = loop(tmp_path, model)
    second = model.seen[1]
    assert result['status'] == 'accepted' and result['calls'] == 2
    assert [m['role'] for m in second] == ['system', 'user', 'assistant', 'user']
    assert second[2]['content'] == block('return a - c\n', 'x\n')
    assert 'no match' in second[3]['content']


def test_check_failure_rolls_back_and_feeds_the_error(tmp_path):
    wrong = block('    return a - b\n', '    return a * b\n')
    model = scripted(wrong, GOOD)
    result, candidate, receipts = loop(tmp_path, model)
    assert result['status'] == 'accepted' and 'AssertionError: 6' in model.seen[1][3]['content']
    assert [r['kind'] for r in receipts] == ['check_failed', 'accepted']
    assert 'a + b' in candidate


def test_dropped_import_is_rejected_before_execution(tmp_path):
    model = scripted(block('import os\n', ''), GOOD)
    result, _, receipts = loop(tmp_path, model)
    assert 'removes names still referenced: os' in model.seen[1][3]['content']
    assert receipts[0]['kind'] == 'rejected'


def test_at_most_three_corrections(tmp_path):
    bad = [block(f'no{i}\n', 'x\n') for i in range(5)]
    result, candidate, receipts = loop(tmp_path, scripted(*bad))
    assert result['status'] == 'exhausted' and result['calls'] == 4 and len(receipts) == 4
    assert candidate == BUGGY  # rolled back


def test_identical_reply_stops_early(tmp_path):
    bad = block('nothing\n', 'x\n')
    result, _, _ = loop(tmp_path, scripted(bad, bad, GOOD))
    assert result['status'] == 'repeated' and result['calls'] == 2


def test_missing_blocks_get_format_feedback(tmp_path):
    model = scripted('I think add is wrong.', GOOD)
    result, _, _ = loop(tmp_path, model)
    assert result['status'] == 'accepted' and 'SEARCH/REPLACE' in model.seen[1][3]['content']


def test_bounded_read_widens_scope_without_line_numbers(tmp_path):
    narrow = [{'path': 'package/value.py', 'start_line': 8, 'end_line': 9}]
    w = make_workspace(tmp_path / 'w', BUGGY, 'issue')
    model = scripted('READ package/value.py 4-5', GOOD)
    try:
        result = run_loop(model, w, 'add(2, 3) should be 5', narrow, subprocess_check(PUBLIC), tmp_path / 'r.jsonl')
    finally:
        w.close()
    shown = model.seen[1][3]['content']
    assert result['status'] == 'accepted' and 'def add(a, b):\n    return a - b' in shown and '4: ' not in shown


def test_read_outside_prefix_and_budget_is_refused(tmp_path):
    reads = ['READ ../etc/passwd 1-2', 'READ package/value.py 1-2', 'READ package/value.py 3-4', GOOD]
    model = scripted(*reads)
    result, _, _ = loop(tmp_path, model, max_reads=1)
    assert 'refused' in model.seen[1][3]['content'] and 'read budget' in model.seen[3][-1]['content']
    assert result['status'] == 'accepted'


def test_receipts_form_a_hash_chain(tmp_path):
    _, _, receipts = loop(tmp_path, scripted(block('x\n', 'y\n'), GOOD))
    assert receipts[0]['previous'] is None and receipts[1]['previous'] == receipts[0]['sha256']


def test_check_timeout_is_a_failure_not_a_hang(tmp_path):
    w = make_workspace(tmp_path / 'w', BUGGY, 'issue')
    try:
        ok, message = subprocess_check('while True: pass\n', timeout=1)(w)
    finally:
        w.close()
    assert not ok and 'timed out' in message


def test_read_past_the_end_of_a_short_file_is_clamped(tmp_path):
    w = make_workspace(tmp_path / 'w', BUGGY, 'issue')
    model = scripted('READ package/value.py 1-50', GOOD)
    try:
        result = run_loop(model, w, 'add(2, 3) should be 5', REGIONS, subprocess_check(PUBLIC), tmp_path / 'r.jsonl')
    finally:
        w.close()
    assert result['status'] == 'accepted' and 'def add(a, b):' in model.seen[1][-1]['content']


# Visible repository tests and reproduction scripts (design 025 actions FIND, READ of tests, RUN).
TESTS = 'from package.value import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n'
SCRIPT = 'RUN\n```python\nimport package.value as v\nprint("got", v.add(2, 3))\n```\n'


def with_tests(tmp_path):
    w = make_workspace(tmp_path / uuid4().hex, BUGGY, 'issue')
    tests = w.registry.directory(w.case) / 'source/tests'
    tests.mkdir()
    (tests / 'test_value.py').write_text(TESTS)
    w.case['test_roots'] = ['tests/']
    w.reset()
    return w


def drive(tmp_path, w, model, **kwargs):
    receipts = tmp_path / 'drive.jsonl'
    try:
        result = run_loop(model, w, 'add(2, 3) should be 5', REGIONS, subprocess_check(PUBLIC), receipts, **kwargs)
    finally:
        w.close()
    return result, [json.loads(line)['kind'] for line in receipts.read_text().splitlines()]


def test_find_lists_matches_in_source_and_visible_tests(tmp_path):
    model = scripted('FIND add(', GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model)
    shown = model.seen[1][-1]['content']
    assert 'package/value.py:4: def add(a, b):' in shown and 'tests/test_value.py:5:     assert add(2, 3) == 5' in shown
    assert result['status'] == 'accepted' and kinds == ['find', 'accepted']


def test_read_of_a_visible_test_file_is_unnumbered_and_never_an_edit_region(tmp_path):
    model = scripted('READ tests/test_value.py 4-50', GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model)
    shown = model.seen[1][-1]['content']
    assert 'def test_add():\n    assert add(2, 3) == 5' in shown and '4: ' not in shown
    assert result['regions'] == REGIONS and kinds == ['read', 'accepted']


def test_reads_escaping_the_test_root_or_prefix_are_refused(tmp_path):
    bad = ['READ ../x.py 1-2', 'READ tests/../package/value.py 1-2', 'READ other/value.py 1-2', 'READ tests/notes.txt 1-2']
    model = scripted(*bad, GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model, max_reads=9)
    assert kinds == ['read_refused'] * 4 + ['accepted'] and result['status'] == 'accepted'
    assert all('READ refused' in seen[-1]['content'] for seen in model.seen[1:])


def test_edits_to_visible_tests_stay_rejected(tmp_path):
    edit = 'tests/test_value.py\n<<<<<<< SEARCH\n    assert add(2, 3) == 5\n=======\n    assert True\n>>>>>>> REPLACE\n'
    model = scripted(edit, GOOD)
    _, kinds = drive(tmp_path, with_tests(tmp_path), model)
    assert kinds == ['rejected', 'accepted'] and 'Edit rejected' in model.seen[1][-1]['content']


def test_find_and_read_share_one_budget(tmp_path):
    model = scripted('FIND add', 'READ tests/test_value.py 1-2', 'FIND return', GOOD)
    _, kinds = drive(tmp_path, with_tests(tmp_path), model, max_reads=2)
    assert kinds == ['find', 'read', 'read_refused', 'accepted'] and 'budget' in model.seen[3][-1]['content']


def test_run_returns_exit_code_and_output_as_its_own_user_message(tmp_path):
    model = scripted(SCRIPT, GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model, allow_run=True)
    second = model.seen[1]
    assert [m['role'] for m in second] == ['system', 'user', 'assistant', 'user'] and second[2]['content'] == SCRIPT
    assert 'exit 0' in second[3]['content'] and 'got -1' in second[3]['content']
    assert result['status'] == 'accepted' and kinds == ['run', 'accepted']


def test_run_uses_the_candidate_tree_and_case_python_paths(tmp_path):
    w = with_tests(tmp_path)
    (w.root / 'package/value.py').write_text('def add(a, b):\n    return "candidate"\n')
    w.case['python_paths'] = ['package']
    model = scripted('RUN\n```python\nimport value\nprint(value.add(1, 1))\n```', GOOD)
    drive(tmp_path, w, model, allow_run=True)
    assert 'candidate' in model.seen[1][-1]['content']


def test_run_is_refused_without_a_disposable_vm_and_after_its_budget(tmp_path):
    model = scripted(SCRIPT, GOOD)
    _, kinds = drive(tmp_path, with_tests(tmp_path), model)
    assert kinds == ['run_refused', 'accepted'] and 'RUN refused: no disposable VM' in model.seen[1][-1]['content']
    model = scripted(SCRIPT, SCRIPT.replace('got', 'again'), GOOD)
    (tmp_path / 'b').mkdir()
    _, kinds = drive(tmp_path / 'b', with_tests(tmp_path), model, allow_run=True, max_runs=1)
    assert kinds == ['run', 'run_refused', 'accepted'] and 'budget' in model.seen[2][-1]['content']


def test_run_timeout_is_reported_not_a_hang(tmp_path, monkeypatch):
    import scripts.repair_loop025 as loop_module
    monkeypatch.setattr(loop_module, 'RUN_TIMEOUT', 1)
    model = scripted('RUN\n```python\nwhile True: pass\n```', GOOD)
    _, kinds = drive(tmp_path, with_tests(tmp_path), model, allow_run=True)
    assert kinds == ['run', 'accepted'] and 'timed out' in model.seen[1][-1]['content']


# F025 run 3: action syntax the 14B actually produced; each was wasted as "no blocks" or repeated.
import pytest  # noqa: E402


@pytest.mark.parametrize('reply', ['FIND `add(`', 'FIND text: `add(`', 'FIND text "add("', 'FIND: "add("', 'FIND `add(` in `value.py`'])
def test_find_argument_variants_are_normalized(tmp_path, reply):
    model = scripted(reply, GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model)
    assert kinds == ['find', 'accepted'] and 'package/value.py:4: def add(a, b):' in model.seen[1][-1]['content']


def test_read_accepts_path_colon_range(tmp_path):
    model = scripted('READ package/value.py:4-5', GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model)
    assert kinds == ['read', 'accepted'] and 'def add(a, b):' in model.seen[1][-1]['content']


def test_run_fence_on_the_same_line_is_recognized(tmp_path):
    w = make_workspace(tmp_path / 'w', BUGGY, 'issue')
    model = scripted("RUN ```python\nprint('probe')\n```", GOOD)
    try:
        run_loop(model, w, 'issue', REGIONS, subprocess_check(PUBLIC), tmp_path / 'r.jsonl', allow_run=True)
    finally:
        w.close()
    assert 'RUN exit 0' in model.seen[1][-1]['content'] and 'probe' in model.seen[1][-1]['content']


def test_prompt_has_no_placeholder_path():
    from scripts.repair_loop025 import SYSTEM
    assert 'path/to' not in SYSTEM


# F025 runs 3-4: the only RUN replies also carried edit blocks and the RUN was silently dropped (RC5).
PROBE = "RUN\n```python\nprint('probe', 2 + 3)\n```\n"


def run_drive(tmp_path, model, **case):
    import sys as _sys
    w = make_workspace(tmp_path / 'w', BUGGY, 'issue')
    w.case.update(case)
    receipts = tmp_path / 'r.jsonl'
    try:
        result = run_loop(model, w, 'issue', REGIONS, subprocess_check(PUBLIC), receipts, allow_run=True)
    finally:
        w.close()
    return result, [json.loads(l)['kind'] for l in receipts.read_text().splitlines()]


def test_run_in_the_same_reply_as_edits_executes_before_the_edit(tmp_path):
    result, kinds = run_drive(tmp_path, scripted(PROBE + GOOD))
    assert result['status'] == 'accepted' and kinds == ['run', 'accepted']


def test_rejected_edit_feedback_carries_the_run_output(tmp_path):
    model = scripted(PROBE + block('return a - c\n', 'x\n'), GOOD)
    result, kinds = run_drive(tmp_path, model)
    shown = model.seen[1][-1]['content']
    assert 'probe 5' in shown and 'Edit rejected' in shown and kinds == ['run', 'rejected', 'accepted']


def test_run_uses_the_case_interpreter_and_prelude(tmp_path):
    import sys as _sys
    model = scripted("RUN\n```python\nprint('mark', MARK)\n```", GOOD)
    run_drive(tmp_path, model, run_python=_sys.executable, run_prelude='MARK = 41 + 1\n')
    assert 'mark 42' in model.seen[1][-1]['content']


def test_missing_run_interpreter_is_reported_not_raised(tmp_path):
    model = scripted("RUN\n```python\nprint(1)\n```", GOOD)
    result, kinds = run_drive(tmp_path, model, run_python='/nonexistent/python3.8')
    assert 'RUN unavailable' in model.seen[1][-1]['content'] and result['status'] == 'accepted'


def test_prompt_asks_for_a_reproduction_before_editing():
    from scripts.repair_loop025 import SYSTEM
    assert 'Before your first edit, RUN' in SYSTEM


# F025 run 5: every applied dev edit was accepted at once (static check), so the model never saw its own
# script on the edited code; replayed locally, that output exposes the wrong fix on 12325 and 12774.
STATIC = lambda _: (True, 'static checks only')  # noqa: E731
WRONG = block('    return a - b\n', '    return a * b\n')


def static_drive(tmp_path, model, **kwargs):
    w = with_tests(tmp_path)
    receipts = tmp_path / 'static.jsonl'
    try:
        result = run_loop(model, w, 'add(2, 3) should be 5', REGIONS, STATIC, receipts, allow_run=True, self_test=True, **kwargs)
    finally:
        w.close()
    return result, [json.loads(line)['kind'] for line in receipts.read_text().splitlines()]


ASSERTS = 'RUN\n```python\nimport package.value as v\nassert v.add(2, 3) == 5, v.add(2, 3)\n```\n'  # fails while buggy


def test_run_marker_inside_the_fence_is_recognized(tmp_path):
    model = scripted('```python\nRUN\nimport package.value as v\nprint("got", v.add(2, 3))\n```', GOOD)
    result, kinds = static_drive(tmp_path, model)
    assert kinds[0] == 'run' and 'got -1' in model.seen[1][-1]['content']


def test_reproduction_that_passes_after_the_edit_accepts_it_without_review(tmp_path):
    model = scripted(ASSERTS, GOOD)
    result, kinds = static_drive(tmp_path, model)
    assert 'reproduces the issue' in model.seen[1][-1]['content']
    assert kinds == ['run', 'self_test', 'accepted'] and len(model.seen) == 2 and 'a + b' in result['patch']


def test_reproduction_that_still_fails_asks_for_a_revision(tmp_path):
    model = scripted(ASSERTS, WRONG, GOOD)
    result, kinds = static_drive(tmp_path, model)
    shown = model.seen[2][-1]['content']
    assert 'still fails' in shown and 'AssertionError: 6' in shown
    assert kinds == ['run', 'self_test', 'self_test', 'accepted'] and 'a + b' in result['patch'] and 'a * b' not in result['patch']


@pytest.mark.parametrize('script, note', [
    ('print("got", v.add(2, 3))', 'does not show the bug'),
    ('x = 1', 'does not show the bug'),
    ('v.nope()', "script's own code"),
    ('v.add(2,', "script's own code"),
])
def test_script_that_does_not_fail_in_the_repository_gives_no_review(tmp_path, script, note):
    model = scripted(f'RUN\n```python\nimport package.value as v\n{script}\n```', GOOD)
    result, kinds = static_drive(tmp_path, model)
    assert note in model.seen[1][-1]['content'] and kinds == ['run', 'accepted']  # a correct edit cannot be talked out


def test_error_raised_inside_the_repository_reproduces():
    from scripts.repair_loop025 import _verdict
    inside = 'Traceback (most recent call last):\n  File "<string>", line 3, in <module>\n  File "package/value.py", line 5, in add\nTypeError: x\n'
    own = 'Traceback (most recent call last):\n  File "<string>", line 3, in <module>\nNameError: name \'q\' is not defined\n'
    asserted = 'Traceback (most recent call last):\n  File "<string>", line 3, in <module>\nAssertionError: 6\n'
    assert [_verdict(1, inside), _verdict(1, own), _verdict(1, asserted), _verdict(0, ''), _verdict(None, 'x'), _verdict(2, 'bye')] == \
        ['fails', 'script_error', 'fails', 'passes', None, 'fails']


def test_pending_candidate_survives_failed_revisions(tmp_path):
    bad = block('    return a - c\n', 'x\n')
    model = scripted(ASSERTS, WRONG, bad, bad.replace('c', 'd'), bad.replace('c', 'e'), bad.replace('c', 'f'))
    result, kinds = static_drive(tmp_path, model)
    assert result['status'] == 'accepted' and 'a * b' in result['patch'] and kinds[-1] == 'accepted'


def test_done_or_a_repeat_keeps_the_pending_candidate(tmp_path):
    for name, last in [('done', 'DONE'), ('repeat', WRONG)]:
        (tmp_path / name).mkdir()
        result, kinds = static_drive(tmp_path / name, scripted(ASSERTS, WRONG, last))
        assert result['status'] == 'accepted' and 'a * b' in result['patch'] and kinds == ['run', 'self_test', 'accepted']


def test_no_self_test_without_runs_left_or_a_script(tmp_path):
    _, kinds = static_drive(tmp_path, scripted(ASSERTS, GOOD), max_runs=1)
    assert kinds == ['run', 'accepted']
    (tmp_path / 'b').mkdir()
    _, kinds = static_drive(tmp_path / 'b', scripted(GOOD))
    assert kinds == ['accepted']


def test_run_on_the_reviewed_candidate_does_not_replace_the_reproduction(tmp_path):
    passing = 'RUN\n```python\nprint("probe")\n```'
    model = scripted(ASSERTS, WRONG, passing, GOOD)
    result, kinds = static_drive(tmp_path, model, max_runs=4)
    assert kinds == ['run', 'self_test', 'run', 'self_test', 'accepted'] and 'a + b' in result['patch']


class Stop(Exception):
    pass


def test_stop_during_review_returns_the_pending_candidate(tmp_path):
    replies = iter([ASSERTS, WRONG])

    def model(messages):
        try:
            return next(replies)
        except StopIteration:
            raise Stop('call_cap')
    result, kinds = static_drive(tmp_path, model, stop=(Stop,))
    assert result['status'] == 'accepted' and 'a * b' in result['patch'] and kinds == ['run', 'self_test', 'accepted']

    def stopper(messages):
        raise Stop('call_cap')
    (tmp_path / 'c').mkdir()
    with pytest.raises(Stop):  # nothing under review: the stop is the chain's outcome, as before
        static_drive(tmp_path / 'c', stopper, stop=(Stop,))


def test_self_test_is_off_unless_asked(tmp_path):
    _, kinds = drive(tmp_path, with_tests(tmp_path), scripted(SCRIPT, GOOD), allow_run=True)
    assert kinds == ['run', 'accepted']


def test_run_output_shows_repository_paths_not_the_temporary_root(tmp_path):
    model = scripted('RUN\n```python\nimport package.value as v\nprint(v.__file__)\n```', GOOD)
    result, kinds = drive(tmp_path, with_tests(tmp_path), model, allow_run=True)
    shown = model.seen[1][-1]['content']
    assert 'package/value.py' in shown and 'kairos' not in shown and str(tmp_path) not in shown
