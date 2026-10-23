"""Synthetic F025 tasks: every buggy file fails its visible check, every author fix passes through the loop.

The reference fixes are an infrastructure positive control, not model output.
"""
import pytest

from scripts.f025_tasks import HELDOUT, TASKS, prompt_issue, workspace
from scripts.repair_loop025 import run_loop, subprocess_check


@pytest.mark.parametrize('task', TASKS + HELDOUT, ids=[t['task_id'] for t in TASKS + HELDOUT])
def test_bug_is_real_and_reference_fix_is_accepted(task, tmp_path):
    w = workspace(task, tmp_path / 'case')
    try:
        ok, output = subprocess_check(task['check'])(w)
        assert not ok, output  # negative control: the defect fails its own visible check
        result = run_loop(lambda messages: task['reference'], w, prompt_issue(task), task['regions'],
                          subprocess_check(task['check']), tmp_path / 'r.jsonl')
    finally:
        w.close()
    assert result['status'] == 'accepted' and result['calls'] == 1


def test_r_task_fix_never_reaches_the_prompt(tmp_path):
    for task in [t for t in TASKS + HELDOUT if t['kind'] == 'R']:  # P tasks state the change by design
        w = workspace(task, tmp_path / task['task_id'])
        seen = []
        try:
            run_loop(lambda m: seen.append(m) or 'no blocks', w, prompt_issue(task), task['regions'],
                     subprocess_check(task['check']), tmp_path / 'x.jsonl', max_corrections=0)
        finally:
            w.close()
        replace = task['reference'].split('=======\n')[1].split('>>>>>>>')[0]
        assert replace.strip() not in seen[0][1]['content']


def test_balanced_probe():
    assert [t['kind'] for t in TASKS].count('P') == 3 and [t['kind'] for t in TASKS].count('R') == 3


def test_heldout_is_balanced_and_disjoint():
    assert [t['kind'] for t in HELDOUT].count('R') == 3 and not {t['task_id'] for t in HELDOUT} & {t['task_id'] for t in TASKS}
