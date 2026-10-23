"""Issue-relevance ranking for the v6 selector; no target material is supplied."""
import inspect

import pytest

import test_coding_context_v3_014 as v3_tests

from scripts import coding_context_v3_014, coding_context_v6_024
from test_coding_context014 import make_workspace
from test_coding_context_v3_014 import extra


def paths(regions):
    return list(dict.fromkeys(region['reference']['path'] for region in regions))


def noise(workspace):
    # Alphabetically earlier files that define common issue words.
    for index in range(5):
        extra(workspace, f'package/aaa{index}.py', 'def get(x):\n    return x\n\ndef run(x):\n    return x\n\nclass Field:\n    pass\n')


def test_cited_module_path_outranks_alphabetical_common_names(tmp_path):
    w = make_workspace(tmp_path, 'def get(x):\n    return x\n', 'Field get() in value.py returns wrong data when run twice')
    noise(w)
    try:
        assert paths(coding_context_v3_014.select(w))[0] != 'package/value.py'
        assert paths(coding_context_v6_024.select(w))[0] == 'package/value.py'
    finally:
        w.close()


def test_rare_issue_symbols_outrank_common_ones(tmp_path):
    w = make_workspace(tmp_path, 'def get(x):\n    return x\n\ndef render_widget_markup(x):\n    return x\n',
                       'Field get breaks render_widget_markup output')
    noise(w)
    try:
        assert paths(coding_context_v6_024.select(w))[0] == 'package/value.py'
    finally:
        w.close()


def test_selector_accepts_only_workspace():
    assert list(inspect.signature(coding_context_v6_024.select).parameters) == ['workspace']


def test_adjacent_issue_definitions_keep_complete_bodies(tmp_path):
    text = 'def alpha_rare(x):\n' + '    x += 1\n' * 8 + '    return x\n\ndef beta_rare(x):\n' + '    x += 2\n' * 8 + '    return x\n'
    w = make_workspace(tmp_path, text, 'alpha_rare and beta_rare both wrong')
    try:
        captured = ''.join(region['text'] for region in coding_context_v6_024.select(w))
        assert '21:     return x' in captured
    finally:
        w.close()


@pytest.mark.parametrize('name', [n for n in dir(v3_tests) if n.startswith('test_')])
def test_v3_capture_semantics_hold_for_v6(name, tmp_path, monkeypatch):
    monkeypatch.setattr(v3_tests, 'select', coding_context_v6_024.select)
    test = getattr(v3_tests, name)
    params = inspect.signature(test).parameters
    test(**{k: v for k, v in {'tmp_path': tmp_path, 'monkeypatch': monkeypatch}.items() if k in params})


def test_short_definition_names_do_not_outrank_real_symbols(tmp_path):
    w = make_workspace(tmp_path, 'def resolve_locale(x):\n    return x\n', 'I get a bad value: resolve_locale must be wrong for me, it says')
    extra(w, 'package/aaa_format.py', ''.join(f'def {n}(self):\n    return 0\n\n' for n in ['I', 'a', 'it', 'be', 'me']))
    try:
        assert paths(coding_context_v6_024.select(w))[0] == 'package/value.py'
    finally:
        w.close()


def test_named_method_is_captured_instead_of_leading_members_of_its_long_class(tmp_path):
    members = ''.join(f'    def member_{i}(self):\n' + '        x = 1\n' * 12 + '        return x\n\n' for i in range(24))
    text = 'class QueryPlan:\n' + members + '    def resolve_alias_value(self):\n        return "target body"\n'
    w = make_workspace(tmp_path, text, 'QueryPlan.resolve_alias_value returns the wrong alias')
    try:
        captured = ''.join(region['text'] for region in coding_context_v6_024.select(w))
        assert 'return "target body"' in captured
    finally:
        w.close()


def test_top_file_keeps_a_second_named_definition_before_weaker_files(tmp_path):
    gap = ''.join(f'def filler_{i}(x):\n    return x\n\n' for i in range(60))
    text = 'def compile_lookup_rare(x):\n    return x\n\n' + gap + 'def render_lookup_rare(x):\n    return "second body"\n'
    w = make_workspace(tmp_path, text, 'value.py: compile_lookup_rare and render_lookup_rare break Field get run')
    noise(w)
    try:
        captured = ''.join(region['text'] for region in coding_context_v6_024.select(w))
        assert 'return "second body"' in captured
    finally:
        w.close()


def test_method_specificity_does_not_change_file_ranking(tmp_path):
    w = make_workspace(tmp_path, 'def lone_helper_name(x):\n    return x\n', 'PlanBuilder.finish_plan_step breaks lone_helper_name')
    extra(w, 'package/zzz.py', 'class PlanBuilder:\n    def finish_plan_step(self):\n        return "method body"\n')
    try:
        assert paths(coding_context_v6_024.select(w))[0] == 'package/zzz.py'
    finally:
        w.close()


def test_generic_method_name_does_not_replace_its_distinctive_class(tmp_path):
    text = ('class ColorLevelFormatter:\n    def __init__(self):\n        self.mark = "target body"\n\n'
            '    def spacer(self):\n' + '        x = 1\n' * 12 + '\n    def format(self, record):\n        return record\n')
    w = make_workspace(tmp_path, text, 'ColorLevelFormatter format output loses colors')
    for index in range(3):
        extra(w, f'package/fmt{index}.py', 'def format(record):\n    return record\n')
    try:
        captured = ''.join(region['text'] for region in coding_context_v6_024.select(w))
        assert 'self.mark = "target body"' in captured
    finally:
        w.close()
