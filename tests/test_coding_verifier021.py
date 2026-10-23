import json
import subprocess
import sys
import pytest
from scripts.coding_verifier021 import verifier


def row():
    return {'FAIL_TO_PASS': ['test_case.py::test_regression'],
            'PASS_TO_PASS': ['test_case.py::test_existing[first', 'test_case.py::test_existing[second]']}


def test_truncated_parameter_expands_to_complete_function():
    script, scope = verifier(row())
    compile(script, 'verifier', 'exec')
    assert scope['existing'] == ['test_case.py::test_existing', 'test_case.py::test_existing[second]']
    assert scope['parameter_expansions'] == [{'declared': 'test_case.py::test_existing[first', 'executed': 'test_case.py::test_existing'}]
    assert not scope['omissions']


def test_overlap_after_expansion_is_rejected():
    value = row(); value['FAIL_TO_PASS'] = ['test_case.py::test_existing']
    with pytest.raises(ValueError, match='overlap'):
        verifier(value)


@pytest.mark.parametrize('broken', [False, True])
def test_expanded_suite_executes_every_parameter_and_rejects_failure(tmp_path, broken):
    (tmp_path / 'test_case.py').write_text(
        'import pytest\n'
        'def test_regression(): pass\n'
        '@pytest.mark.parametrize("value", ["first value", "second"])\n'
        f'def test_existing(value): assert value != {"second"!r} or {not broken!r}\n')
    script, _ = verifier(row()); (tmp_path / 'verify.py').write_text(script)
    result = subprocess.run([sys.executable, 'verify.py'], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    summary = json.loads(result.stdout.split('KAIROS_VERIFIER_RESULT ')[1].splitlines()[0])
    assert summary['tests_run'] == summary['collected'] == 3
    assert summary['execution_complete'] is True
    assert summary['complete'] is (not broken)
    assert (result.returncode == 0) is (not broken)
