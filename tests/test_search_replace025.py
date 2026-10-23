"""SEARCH/REPLACE edit layer: exact-once anchors, insert keeps the anchor, no snapshot writes."""
import json
from uuid import uuid4

from test_coding_context014 import make_workspace
from scripts.search_replace025 import apply_blocks, parse_blocks

TEXT = 'import attr\nfrom typing import Any\n\n\nclass A:\n    pass\n\n\ndef f(x):\n    return x\n'


def block(search, replace, path='package/value.py'):
    return f'{path}\n<<<<<<< SEARCH\n{search}=======\n{replace}>>>>>>> REPLACE\n'


def run(tmp_path, text, blocks, regions=None):
    w = make_workspace(tmp_path / uuid4().hex, text, 'issue')
    try:
        verdict = apply_blocks(w, parse_blocks(blocks), regions)
        snapshot = (w.registry.directory(w.case) / 'source/package/value.py').read_text()
    finally:
        w.close()
    assert snapshot == text  # the original snapshot is never written
    return verdict


def test_exact_replace(tmp_path):
    v = run(tmp_path, TEXT, block('    return x\n', '    return x + 1\n'))
    assert v['accepted'] and '+    return x + 1' in v['patch']


def test_insert_keeps_the_anchor(tmp_path):
    v = run(tmp_path, TEXT, block('import attr\n', 'import attr\nimport os\n'))
    assert v['accepted'] and '-import attr' not in v['patch'] and '+import os' in v['patch']


def test_delete(tmp_path):
    v = run(tmp_path, TEXT, block('def f(x):\n    return x\n', ''))
    assert v['accepted'] and '-def f(x):' in v['patch']


def test_zero_and_multiple_matches_rejected(tmp_path):
    v = run(tmp_path, TEXT, block('nothing here\n', 'x\n'))
    assert not v['accepted'] and v['stage'] == 'validate' and 'no match' in v['reason']
    v = run(tmp_path, TEXT + 'def g(x):\n    return x\n', block('    return x\n', 'pass\n'))
    assert not v['accepted'] and 'lines 10, 12' in v['reason']


def test_empty_search_rejected(tmp_path):
    v = run(tmp_path, TEXT, block('', 'x\n'))
    assert not v['accepted'] and 'empty' in v['reason']


def test_out_of_region_rejected_in_constrained_mode(tmp_path):
    region = {'path': 'package/value.py', 'start_line': 5, 'end_line': 10}
    v = run(tmp_path, TEXT, block('    return x\n', '    return 1\n'), [region])
    assert v['accepted'], v['reason']
    v = run(tmp_path, TEXT, block('import attr\n', 'import attr\nimport os\n'), [{'reference': region}])
    assert not v['accepted'] and 'outside' in v['reason']


def test_dangling_removal_rejected(tmp_path):
    v = run(tmp_path, TEXT + '\nvalue = A()\n', block('class A:\n    pass\n', ''))
    assert not v['accepted'] and v['stage'] == 'validate' and 'A' in v['reason']


def test_syntax_error_rejected(tmp_path):
    v = run(tmp_path, TEXT, block('    return x\n', 'return (x\n'))
    assert not v['accepted'] and 'syntax' in v['reason'].lower()


def test_fenced_and_prose_wrapped_output_parsed():
    text = 'Sure, here is the fix:\n```\n' + block('a\n', 'b\n') + '```\nHope it helps.'
    assert parse_blocks(text) == [('package/value.py', 'a\n', 'b\n')]
    assert parse_blocks('no blocks') == []


def test_control_hunk_parser_and_region_matching():
    from scripts.search_replace_control025 import expressible, parse_hunks
    patch = '+++ b/package/value.py\n@@ -1,2 +1,3 @@\n import attr\n+import os\n from typing import Any\n'
    assert parse_hunks(patch) == [('package/value.py', 'import attr\nfrom typing import Any\n',
                                   'import attr\nimport os\nfrom typing import Any\n')]
    region = {'path': 'package/value.py', 'start_line': 1, 'end_line': 2,
              'numbered_original_source': '1: import attr\n2: from typing import Any\n'}
    job = {'messages': [None, {'content': json.dumps({'original_source': [region]})}]}
    assert expressible(job, 'package/value.py', 'import attr\nfrom typing import Any\n')
    assert not expressible(job, 'package/value.py', 'import attr\nimport sys\n')


def test_f024_pilot_gold_hunks_are_expressible():
    import os
    from pathlib import Path
    import pytest
    root = Path(os.path.expanduser('~/Desktop/resume/kairos-closeout020'))
    package, parquet = root / 'f024-pilot/upload-v2/f024-package.json', root / 'unseen023-full/test.parquet'
    if not (package.is_file() and parquet.is_file()):
        pytest.skip('F024 pilot package or unseen023 parquet not present')
    import pyarrow.parquet as pq
    from scripts.search_replace_control025 import expressible, parse_hunks
    jobs = {j['job_id']: j for j in json.loads(package.read_text())['jobs']}
    gold = {r['instance_id']: r['patch'] for r in pq.read_table(parquet).to_pylist()}
    for instance in ('django__django-11772', 'pytest-dev__pytest-8124'):
        for path, old, _ in parse_hunks(gold[instance]):
            assert expressible(jobs[instance + '/oracle/base/t1'], path, old), (instance, path)


def test_overlapping_occurrences_count_as_multiple_matches(tmp_path):
    v = run(tmp_path, 'x = 1\nx = 1\nx = 1\n', block('x = 1\nx = 1\n', 'x = 2\n'))  # occurrences at lines 1 and 2 overlap
    assert not v['accepted'] and 'matches at lines' in v['reason']


def test_unparsable_original_is_a_rejection_not_a_crash(tmp_path):
    v = run(tmp_path, 'def f(:\n', block('def f(:\n', 'def f():\n    pass\n'))
    assert not v['accepted'] and v['stage'] == 'validate'


# F025 Colab run: the 14B wrapped SEARCH/REPLACE bodies in ```python fences and copied the prompt's
# `path/to/` placeholder; both blocked otherwise-correct edits.
def test_code_fences_inside_a_block_are_stripped():
    blocks = parse_blocks('package/value.py\n<<<<<<< SEARCH\n```python\n    return x\n```\n=======\n```python\n    return x + 1\n```\n>>>>>>> REPLACE\n')
    assert blocks == [('package/value.py', '    return x\n', '    return x + 1\n')]


def test_placeholder_path_resolves_to_the_one_region_file_that_matches(tmp_path):
    regions = [{'path': 'package/value.py', 'start_line': 1, 'end_line': 10}]
    v = run(tmp_path, TEXT, block('    return x\n', '    return x + 1\n', path='path/to/file.py'), regions)
    assert v['accepted'] and '+++ b/package/value.py' in v['patch']
    v = run(tmp_path, TEXT, block('    return x\n', '    return x + 1\n', path='path/to/file.py'))
    assert not v['accepted']  # unconstrained mode never guesses a file


# F025 run 3 error analysis: every rejected edit had SEARCH/REPLACE uniformly dedented to column 0 (the 14B
# copies snippets as standalone code), and `return enum.unique(cls)` matched mid-line. Whole-line matching
# plus uniform leading-whitespace tolerance follows Aider's editblock_coder (reimplemented, not copied).
METHOD = 'class A:\n    def get(self, x):\n        if x:\n            return 1\n        return 0\n'


def run_method(tmp_path, blocks, regions=None):
    from test_coding_context014 import make_workspace
    w = make_workspace(tmp_path / uuid4().hex, METHOD, 'issue')
    try:
        return apply_blocks(w, parse_blocks(blocks), regions)
    finally:
        w.close()


def test_search_never_matches_inside_a_line(tmp_path):
    v = run_method(tmp_path, block('return 0\n', 'x = 0\nreturn x\n'))  # 12304-s1 shape: 2nd line lost its indent
    assert v['accepted'] and '+        x = 0' in v['patch'] and '+        return x' in v['patch']


def test_uniformly_dedented_block_is_reindented(tmp_path):
    v = run_method(tmp_path, block('def get(self, x):\n    if x:\n        return 1\n', 'def get(self, x):\n    if x:\n        return 3\n'))
    assert v['accepted'] and '+            return 3' in v['patch']


def test_dedented_block_matching_two_places_is_rejected(tmp_path):
    text = 'class A:\n    def f(self):\n        return 1\n\n\nclass B:\n    def f(self):\n        return 1\n'
    v = run(tmp_path, text, block('def f(self):\n    return 1\n', 'def f(self):\n    return 2\n'))
    assert not v['accepted'] and 'matches at lines 2, 7' in v['reason']


def test_path_to_prefix_is_stripped(tmp_path):
    v = run(tmp_path, TEXT, block('    return x\n', '    return x + 1\n', path='path/to/package/value.py'))
    assert v['accepted'] and '+++ b/package/value.py' in v['patch']


def test_no_match_shows_the_closest_real_lines(tmp_path):
    v = run_method(tmp_path, block('    def get(self, y):\n', '    def get(self, z):\n'))
    assert not v['accepted'] and 'no match' in v['reason'] and 'closest lines 2-2' in v['reason'] and 'def get(self, x):' in v['reason']
