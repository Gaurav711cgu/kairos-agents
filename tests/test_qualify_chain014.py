"""Verify that repeated image corrections preserve prior raw captures."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import qualify014 as q, qualify_chain014 as chain

class ChainTests(unittest.TestCase):
    def test_old_reuse_capture_is_preserved_without_overwriting_new_binding(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve(); old = root / 'old'; old.mkdir()
            q.immutable(old / 'receipt.json', {'binding': 'first', 'model_calls': 0})
            q.immutable(old / 'reuse-provenance.json', {'revision_binding': 'second', 'original_receipt_sha256': q.sha(old / 'receipt.json')})
            with patch.object(q, 'storage_guard'):
                chain.copy_chain(old / 'receipt.json', root / 'new', 'third', [root])
            self.assertEqual(q.sha(old / 'receipt.json'), q.sha(root / 'new/receipt.json'))
            preserved = list((root / 'new').glob('prior-reuse-*.json'))
            self.assertEqual(len(preserved), 1)
            self.assertEqual(q.sha(preserved[0]), q.sha(old / 'reuse-provenance.json'))
            self.assertEqual(q.load(root / 'new/reuse-provenance.json')['revision_binding'], 'third')

    def test_incomplete_or_uncertain_prior_run_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            for n, v in [('binding.json', {'binding': 'a'}), ('plan.json', {'binding': 'a'}), ('report.json', {'binding':'a','model_calls':0,'execution_complete':False,'candidates':[]})]: q.immutable(root / n, v)
            with self.assertRaisesRegex(ValueError, 'complete'):
                chain.previous_chain(root, {'candidates': []})
