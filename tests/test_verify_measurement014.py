"""Seals reject undeclared runtime state and altered aggregate metrics."""
import copy
import unittest
from scripts import verify_measurement014 as v

class SealTests(unittest.TestCase):
    def test_undeclared_changes_and_private_paths_are_rejected(self):
        a = {'sha256': 'a'*64, 'bytes': 1}; b = {'sha256': 'b'*64, 'bytes': 1}
        v.verify_delta({'README.md': b}, {'README.md': a}, {'README.md': b})
        for name in ['.runtime/auth.json', 'kairos_api/app.py', 'evidence/evaluation013/manifest.json', v.MANIFEST]:
            with self.assertRaises(ValueError): v.verify_delta({name:b}, {}, {name:b})
        with self.assertRaises(ValueError): v.verify_delta({'README.md':a}, {'README.md':a}, {'README.md':b})

    def test_metric_summary_cannot_disagree_with_paired_rows(self):
        metrics = {'mrr':1.0,'recall@1':1.0,'recall@5':1.0,'recall@10':1.0}
        report = {'queries':1,'paired':[{'example_id':'one','base':dict(metrics),'adapter':dict(metrics)}], 'summary':{'base':dict(metrics),'adapter':dict(metrics)}}
        self.assertTrue(v.metric_arithmetic(report))
        changed = copy.deepcopy(report);changed['summary']['base']['mrr']=0.5
        with self.assertRaisesRegex(ValueError,'mean'): v.metric_arithmetic(changed)
        changed=copy.deepcopy(report);changed['paired'].append(changed['paired'][0]);changed['queries']=2
        with self.assertRaisesRegex(ValueError,'duplicate'):v.metric_arithmetic(changed)

    def test_comparison_cannot_replace_exclusions_or_missing_arms_with_successes(self):
        rows = [{'instance_id':str(i),'qualified':False,'split':'holdout','arms':{}} for i in range(24)]
        empty = {'cases':0,'verified':0,'outcomes':{},'calls':0,'checks_admitted':0,'checks_captured':0,
            'input_tokens_observed':0,'output_tokens_observed':0,'token_measurements_complete':True,'elapsed_seconds':0}
        report = {'execution_complete':True,'attempts':0,'qualified_cases':0,'cases':rows,
            'summary':{split:{arm:dict(empty) for arm in ['baseline','loop','drafts']} for split in ['development','holdout']}}
        self.assertTrue(v.comparison_arithmetic(report))
        changed=copy.deepcopy(report);changed['summary']['holdout']['loop']['verified']=1
        with self.assertRaisesRegex(ValueError,'summary'):v.comparison_arithmetic(changed)
        changed=copy.deepcopy(report);changed['cases'][0]['qualified']=True;changed['qualified_cases']=1
        with self.assertRaisesRegex(ValueError,'paired arm'):v.comparison_arithmetic(changed)
