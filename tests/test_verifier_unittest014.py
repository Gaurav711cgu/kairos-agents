"""Real unittest subprocesses reproduce wrapped descriptions and subtest failures."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from scripts.verifier_unittest014 import render_script014

class StructuredVerifierTests(unittest.TestCase):
    def check(self, body, expected):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / 'runner.py'
            path.write_text('import unittest\n' + body + '\nunittest.main(argv=["fixture"], verbosity=2)\n')
            result = subprocess.run([sys.executable, '-c', render_script014(expected, [], str(path))], capture_output=True, text=True, timeout=10)
            line = next(line for line in result.stdout.splitlines() if line.startswith('KAIROS_VERIFIER_RESULT '))
            return result.returncode, json.loads(line.split(' ', 1)[1])

    def test_wrapped_description_and_failing_subtest_reproduce_regression(self):
        body = '''class Example(unittest.TestCase):
 def test_extra_tags(self):
  """A message's extra_tags attribute is correctly preserved when retrieved"""
  with self.subTest(extra_tags=''): self.assertEqual(None, '')
'''
        expected = "A message's extra_tags attribute is correctly preserved when retrieved"
        code, result = self.check(body, [expected])
        self.assertEqual(code, 1)
        self.assertTrue(result['execution_complete'])
        self.assertEqual(result['regression_failed'], [expected])
        code, result = self.check(body.replace("self.assertEqual(None, '')", "self.assertEqual('', '')"), [expected])
        self.assertEqual(code, 0)
        self.assertTrue(result['complete'])

    def test_missing_or_skipped_regression_never_passes(self):
        body = 'class Example(unittest.TestCase):\n def test_other(self): self.skipTest("not executed")\n'
        for expected in ['missing', 'test_other (__main__.Example)']:
            code, result = self.check(body, [expected])
            self.assertNotEqual(code, 0)
            self.assertFalse(result['complete'])
            self.assertNotEqual(result['regression_passed'], [expected])

    def test_exception_and_expected_failure_remain_distinct(self):
        body = 'class Example(unittest.TestCase):\n def test_error(self): raise RuntimeError("broken")\n'
        code, result = self.check(body, ['test_error (__main__.Example)'])
        self.assertEqual(code, 1)
        self.assertTrue(result['execution_complete'])
        self.assertEqual(result['regression_failed'], ['test_error (__main__.Example)'])

    def test_expected_failure_is_not_a_verified_repair(self):
        body = 'class Example(unittest.TestCase):\n @unittest.expectedFailure\n def test_expected(self): self.fail("known defect")\n'
        code, result = self.check(body, ['test_expected (__main__.Example)'])
        self.assertEqual(code, 1)
        self.assertTrue(result['execution_complete'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['regression_failed'], [])
