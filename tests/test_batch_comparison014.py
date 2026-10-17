"""Protect study artifacts during interrupted execution and storage compaction."""
from pathlib import Path
import json
import tempfile
import unittest
from scripts import batch_comparison014 as batch

class PreservationTests(unittest.TestCase):
    def test_stopped_database_round_trips_bytes_and_modes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            source = root / 'postgres-data/base'
            source.mkdir(parents=True)
            p = source / 'original'
            p.write_bytes(bytes(range(256)) * 40)
            p.chmod(0o600)
            batch.compact_database(root)
            self.assertFalse((root / 'postgres-data').exists())
            receipt = json.loads((root / 'database-preservation.json').read_bytes())
            self.assertEqual(receipt['files'][0]['mode'], 0o600)
            self.assertEqual(receipt['files'][0]['bytes'], 10240)

    def test_running_database_is_never_archived_or_removed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            source = root / 'postgres-data'
            source.mkdir()
            (source / 'postmaster.pid').write_text('fixture-only')
            with self.assertRaisesRegex(ValueError, 'still active'):
                batch.compact_database(root)
            self.assertTrue((source / 'postmaster.pid').exists())
            self.assertFalse((root / 'postgres-data.tar.gz').exists())
