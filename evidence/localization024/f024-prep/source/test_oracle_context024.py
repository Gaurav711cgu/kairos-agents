"""Oracle regions are a labelled diagnostic upper bound built from the gold patch."""
import difflib

import pytest

from scripts.coding_actions014 import convert_action
from scripts.oracle_context024 import ORACLE_LABEL, oracle_regions
from test_coding_context014 import make_workspace


def patch_for(before, after):
    return 'diff --git a/package/value.py b/package/value.py\n' + ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/package/value.py', tofile='b/package/value.py'))


def test_oracle_regions_contain_every_gold_hunk(tmp_path):
    before = ''.join(f'line_{i} = {i}\n' for i in range(200))
    after = before.replace('line_10 = 10\n', 'line_10 = 11\n').replace('line_150 = 150\n', 'line_150 = 151\n')
    w = make_workspace(tmp_path, before, 'irrelevant issue text')
    try:
        regions = oracle_regions(w, patch_for(before, after), 'package/')
        assert len(regions) == 2 and all(r['selection_reason'] == ORACLE_LABEL for r in regions)
        convert_action(w, patch_for(before, after), regions, anchor_policy='captured-neighbor-coalesced-v3')
    finally:
        w.close()


def test_oracle_refuses_instead_of_truncating(tmp_path):
    before = ''.join(f'line_{i} = {i}\n' for i in range(300))
    after = ''.join(f'line_{i} = {i + 1}\n' if i < 90 else f'line_{i} = {i}\n' for i in range(300))
    w = make_workspace(tmp_path, before, 'irrelevant')
    try:
        with pytest.raises(ValueError, match='80-line'):
            oracle_regions(w, patch_for(before, after), 'package/')
    finally:
        w.close()


def test_oracle_refuses_new_files_and_renames(tmp_path):
    w = make_workspace(tmp_path, 'x = 1\n', 'irrelevant')
    created = 'diff --git a/package/new.py b/package/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/package/new.py\n@@ -0,0 +1 @@\n+y = 2\n'
    renamed = 'diff --git a/other/x.py b/package/x.py\n--- a/other/x.py\n+++ b/package/x.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n'
    try:
        for patch in (created, renamed):
            with pytest.raises(ValueError):
                oracle_regions(w, patch, 'package/')
    finally:
        w.close()
