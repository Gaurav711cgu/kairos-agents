"""A public qualification view cannot silently rewrite or replace evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.export_qualification014 import export, sanitized


class ExportTests(unittest.TestCase):
    def test_locations_are_explicitly_redacted_without_erasing_failure(self):
        value = {'status': 'environment_failure', 'reason': 'missing dependency', 'work': '/Users/alice/private', 'nested': ['/private/tmp/task']}
        public, changes = sanitized(value)
        self.assertEqual(public['status'], value['status'])
        self.assertEqual(public['reason'], value['reason'])
        self.assertEqual(changes, ['/work', '/nested/0'])
        self.assertNotIn('/Users/', json.dumps(public))
        self.assertEqual(value['work'], '/Users/alice/private')

    def test_source_digest_drift_cannot_produce_a_public_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); q = root/'q'; q.mkdir()
            (q/'report.json').write_text('{}')
            study = root/'study.json'; study.write_text(json.dumps({'qualification_report_sha256': 'a'*64, 'cases': []}))
            output = root/'public'
            with self.assertRaisesRegex(ValueError, 'qualification report'):
                export(q, study, hashlib.sha256(study.read_bytes()).hexdigest(), output)
            self.assertFalse(output.exists())
