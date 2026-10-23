"""Static preflight: an edit must not drop a module's top-level definitions or imports."""
from scripts.edit_preflight024 import removed_top_level_names

ORIGINAL = '''import attr
from typing import Any


class MD5(object):
    function = 'MD5'


def helper(x):
    return x

LIMIT = 3
'''


def test_deleting_a_class_other_modules_import_is_reported():
    candidate = ORIGINAL.replace("class MD5(object):\n    function = 'MD5'\n", '')
    assert removed_top_level_names(ORIGINAL, candidate) == ['MD5']


def test_overwriting_an_import_line_instead_of_inserting_is_reported():
    candidate = ORIGINAL.replace('import attr\n', 'from typing import Any\n', 1)
    assert removed_top_level_names(ORIGINAL, candidate) == ['attr']


def test_editing_bodies_and_adding_names_is_allowed():
    candidate = ORIGINAL.replace('return x', 'return x + 1') + '\n\ndef extra():\n    return 0\n'
    assert removed_top_level_names(ORIGINAL, candidate) == []


def test_moving_an_import_is_not_a_removal():
    candidate = ORIGINAL.replace('import attr\n', '') + '\nimport attr\n'
    assert removed_top_level_names(ORIGINAL, candidate) == []


def test_only_removals_that_leave_something_dangling_are_rejected(tmp_path):
    from scripts.edit_preflight024 import dangling_removals
    pkg = tmp_path / 'pkg'
    (pkg / 'functions').mkdir(parents=True)
    (pkg / 'functions' / '__init__.py').write_text('from .text import MD5\n')
    original = 'import attr\nfrom urllib.parse import quote\n\n\nclass MD5:\n    pass\n\n\n@attr.s\nclass Key:\n    pass\n\n\ndef make(x):\n    return quote(x)\n'
    # The correct fix drops `quote` and stops using it: allowed.
    fixed = original.replace('from urllib.parse import quote\n', 'import hashlib\n').replace('quote(x)', 'hashlib.md5(x).hexdigest()')
    assert dangling_removals(tmp_path, 'pkg/functions/text.py', original, fixed) == []
    # Overwriting `import attr` while `@attr.s` remains: dangling reference.
    assert dangling_removals(tmp_path, 'pkg/functions/text.py', original, original.replace('import attr\n', 'from typing import Any\n')) == ['attr']
    # Deleting MD5 that a sibling imports: dangling import.
    assert dangling_removals(tmp_path, 'pkg/functions/text.py', original, original.replace('class MD5:\n    pass\n', '')) == ['MD5']


def test_names_bound_under_top_level_try_are_tracked():
    from scripts.edit_preflight024 import removed_top_level_names
    original = 'try:\n    import json as j\nexcept ImportError:\n    j = None\n'
    assert removed_top_level_names(original, '') == ['j']


def test_package_init_exports_are_checked(tmp_path):
    from scripts.edit_preflight024 import dangling_removals
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg/__init__.py').write_text('from .core import Foo\n')
    (tmp_path / 'pkg/user.py').write_text('from pkg import Foo\n')
    assert dangling_removals(tmp_path, 'pkg/__init__.py', 'from .core import Foo\n', '') == ['Foo']
