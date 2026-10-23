import copy
import pytest
from scripts.coding_target_completeness021 import audit_row, parse_patch

PATCH = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 3\n z = 4\n'
def row():
    return {'instance_id': 'case-1', 'input': {'original_source': [{'path': 'a.py', 'source_id': 'S1', 'start_line': 1, 'end_line': 3, 'numbered_original_source': '1: x = 1\n2: y = 2\n3: z = 4\n'}]}, 'assistant_target': {'action': 'propose_patch', 'edits': [{'source_id': 'S1', 'start_line': 2, 'end_line': 2, 'new': 'y = 3\n'}]}}

def test_complete(): assert audit_row(row(), PATCH)['complete_reference_equivalence']
def test_noop_rejected():
    r = row(); r['assistant_target']['edits'][0]['new'] = 'y = 2\n'
    assert not audit_row(r, PATCH)['complete_reference_equivalence']
def test_missing_hunk_rejected():
    patch = PATCH + '@@ -10 +10 @@\n-old = 1\n+old = 2\n'
    assert not audit_row(row(), patch)['complete_reference_equivalence']
def test_equivalent_coalesced_edit():
    r = row(); r['assistant_target']['edits'] = [{'source_id': 'S1', 'start_line': 1, 'end_line': 3, 'new': 'x = 1\ny = 3\nz = 4\n'}]
    assert audit_row(r, PATCH)['complete_reference_equivalence']
def test_conflicting_original():
    r = row(); r['input']['original_source'][0]['numbered_original_source'] = '1: x = 1\n2: y = 9\n3: z = 4\n'
    with pytest.raises(ValueError, match='Conflicting'): audit_row(r, PATCH)
def test_escaping_authority():
    r = row(); r['assistant_target']['edits'][0]['end_line'] = 4
    with pytest.raises(ValueError, match='authority'): audit_row(r, PATCH)
def test_traversal():
    with pytest.raises(ValueError, match='Unsafe'): parse_patch(PATCH.replace('a/a.py', 'a/../a.py'))
def test_overlap():
    r = row(); r['assistant_target']['edits'] *= 2
    with pytest.raises(ValueError, match='Overlapping'): audit_row(r, PATCH)
def test_insertion_anchor():
    r = row(); r['assistant_target']['edits'][0]['new'] = 'y = 2\nadded = 1\n'
    patch = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -2,0 +3 @@\n+added = 1\n'
    assert audit_row(r, patch)['complete_reference_equivalence']
