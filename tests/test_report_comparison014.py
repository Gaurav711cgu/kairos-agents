"""Paired reporting retains both wins and failures without inference."""
import unittest
from scripts.report_comparison014 import paired_interval, usage_totals, assert_public_capture
import json

class PairedReportingTests(unittest.TestCase):
    def test_balanced_wins_and_losses_remain_zero_with_visible_uncertainty(self):
        rows=[{'arms':{'loop':{'verified':True},'baseline':{'verified':False}}},
              {'arms':{'loop':{'verified':False},'baseline':{'verified':True}}}]
        result=paired_interval(rows,'loop','baseline')
        self.assertEqual(result['pairs'],2)
        self.assertEqual(result['difference'],0)
        self.assertEqual(result['interval95'],[-1,1])
        self.assertEqual(result,paired_interval(rows,'loop','baseline'))

    def test_missing_pairs_do_not_become_zero_effect_evidence(self):
        result=paired_interval([],'loop','baseline')
        self.assertIsNone(result['difference'])
        self.assertIsNone(result['interval95'])

    def test_partial_usage_keeps_valid_counters_and_marks_missing_measurements(self):
        totals, complete = usage_totals([{'prompt_tokens': 15, 'completion_tokens': None}, None], 2, 3)
        self.assertEqual(totals, {'prompt_tokens': 15, 'completion_tokens': 0})
        self.assertFalse(complete)

    def test_only_exact_bound_public_issue_can_carry_an_upstream_author_path(self):
        issue='Public issue: traceback at /Users/upstream/project.py\nOriginal report.'
        assert_public_capture({'issue':issue,'prompt':json.dumps({'issue':issue})},issue)
        with self.assertRaisesRegex(ValueError,'Unbound'):
            assert_public_capture({'issue':issue,'other':'/Users/unrelated/private'},issue)
        with self.assertRaisesRegex(ValueError,'Private'):
            assert_public_capture({'issue':'/Users/gauravkumarnayak/private'},'/Users/gauravkumarnayak/private')
        totals, complete = usage_totals([{'prompt_tokens': True, 'completion_tokens': -4}], 1, 1)
        self.assertEqual(totals, {'prompt_tokens': 0, 'completion_tokens': 0})
        self.assertFalse(complete)
