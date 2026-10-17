"""Regression checks for issue-only class links and import edit authority."""
from pathlib import Path
import difflib

from scripts.coding_context_v3_014 import select
from scripts.coding_actions014 import convert_action
from test_coding_context014 import make_workspace


def extra(workspace, name, text):
    root = workspace.registry.directory(workspace.case) / 'source'
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_explicit_function_captures_its_distant_import_authority(tmp_path):
    text = 'import os\n' + '\n' * 100 + 'def filename_base(name):\n    return name\n'
    w = make_workspace(tmp_path, text, 'filename_base in package/value.py loses periods')
    try:
        regions = select(w)
        assert 'def filename_base' in regions[0]['text']
        assert any('import os' in region['text'] for region in regions)
        after = text.replace('import os\n', 'import os\nimport pathlib\n').replace('return name', 'return pathlib.Path(name).name')
        patch = ''.join(difflib.unified_diff(text.splitlines(True), after.splitlines(True), fromfile='a/package/value.py', tofile='b/package/value.py'))
        action, _ = convert_action(w, patch, regions, anchor_policy='captured-neighbor-v2')
        assert len(action['edits']) == 2
        assert (w.root / 'package/value.py').read_text() == after
        assert (w.registry.directory(w.case) / 'source/package/value.py').read_text() == text
    finally:
        w.close()


def test_long_class_uses_complete_member_groups_and_imported_dependency(tmp_path):
    text = 'from package.reader import Reader\nclass Loader:\n    """' + 'loader documentation\n' * 90 + '"""\n    def __init__(self):\n        self.reader = Reader()\n    def __call__(self):\n        return self.reader.read()\n'
    w = make_workspace(tmp_path, text, 'Loader produces incorrect image arrays')
    extra(w, 'package/reader.py', 'class Reader:\n    """' + 'reader documentation\n' * 90 + '"""\n    def read(self):\n        return self.array_data()\n    def array_data(self):\n        return 0\n')
    try:
        regions = select(w)
        assert any('self.reader = Reader()' in region['text'] for region in regions)
        assert any('def array_data' in region['text'] for region in regions)
        assert all(region['reference']['end_line'] - region['reference']['start_line'] < 80 for region in regions)
    finally:
        w.close()


def test_original_documentation_can_link_a_related_wrapper_class(tmp_path):
    w = make_workspace(tmp_path, 'class CropSamples:\n    def __call__(self):\n        return 0\n', 'CropSamples must preserve random state')
    extra(w, 'package/wrappers.py', 'class DictionaryCrop:\n    """Dictionary version of package.CropSamples."""\n    def __call__(self):\n        return 0\n')
    try:
        regions = select(w)
        assert any(region['path'] == 'package/wrappers.py' for region in regions)
        assert any('documentation explicitly links' in region.get('selection_reason', '') for region in regions)
    finally:
        w.close()


def test_import_resolution_does_not_pick_an_unrelated_class_with_same_name(tmp_path):
    w = make_workspace(tmp_path, 'from package.good import Reader\nclass Loader:\n    def __call__(self):\n        return Reader()\n', 'Loader is wrong')
    extra(w, 'package/good.py', 'class Reader:\n    def read(self):\n        return "correct dependency"\n')
    extra(w, 'package/bad.py', 'class Reader:\n    def read(self):\n        return "unrelated dependency"\n')
    try:
        regions = select(w)
        assert any('correct dependency' in region['text'] for region in regions)
        assert not any('unrelated dependency' in region['text'] for region in regions)
    finally:
        w.close()


def test_region_budget_records_unavailable_original_lines(tmp_path):
    text = '\n'.join(f'class Target{i}:\n    def run(self):\n        return {i}\n' for i in range(7))
    w = make_workspace(tmp_path, text, ' '.join('Target' + str(i) for i in range(7)))
    try:
        regions = select(w)
        assert len(regions) <= 4
        assert any('budget exhausted' in item['reason'] for item in regions[0]['localization']['omissions'])
    finally:
        w.close()


def test_reference_verifier_and_entry_hints_are_not_read(tmp_path, monkeypatch):
    w = make_workspace(tmp_path, 'class Target:\n    def run(self):\n        return 1\n', 'Target fails')
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        if path.name in {'reference.patch', 'test.patch', 'verify.py', 'hidden_answer.py'}:
            raise AssertionError('Target or verification material was read')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    try:
        assert select(w)
    finally:
        w.close()


def test_symlink_cannot_expand_original_source_authority(tmp_path):
    w = make_workspace(tmp_path, 'class Target:\n    def run(self):\n        return 1\n', 'Target fails')
    outside = tmp_path / 'outside.py'
    outside.write_text('class Target:\n    secret = "must remain outside"\n')
    (w.registry.directory(w.case) / 'source/package/escape.py').symlink_to(outside)
    try:
        assert all('must remain outside' not in region['text'] for region in select(w))
    finally:
        w.close()
