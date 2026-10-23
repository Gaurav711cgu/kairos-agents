"""Parquet list fields are normalized to the JSON strings qualify014 expects."""
import json

from scripts.f024_qualify import normalize


def test_list_test_ids_become_json_strings_and_strings_are_kept():
    row = {'FAIL_TO_PASS': ['tests/a.py::t'], 'PASS_TO_PASS': '["tests/b.py::u"]', 'patch': 'p'}
    out = normalize(row)
    assert json.loads(out['FAIL_TO_PASS']) == ['tests/a.py::t'] and out['PASS_TO_PASS'] == '["tests/b.py::u"]'
    assert out['patch'] == 'p' and row['FAIL_TO_PASS'] == ['tests/a.py::t']
