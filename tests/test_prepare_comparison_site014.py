"""A downloaded repair must match its passing check, not the latest proposal."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from kairos_api.model_runtime import digest
from scripts.prepare_comparison_site014 import prepare


class WebsiteEvidenceTests(unittest.TestCase):
    def source(self, root, matching=True):
        # These isolated records are mechanical fixtures, not model evidence.
        case = 'django__django-1'
        record = {'task_id':case,'outcome':'verified_repair','steps':[
            {'name':'propose_patch','state':'captured','result':{'body':{'patch':'checked candidate'}}},
            {'name':'propose_patch','state':'captured','result':{'body':{'patch':'different later proposal'}}},
            {'name':'run_checks','state':'captured','result':{'body':{'passed':True,'patch_digest':digest('checked candidate' if matching else 'missing candidate')}}}]}
        raw=json.dumps(record).encode()
        paths={
            'evidence/measurement014/comparison/records/'+case+'/loop/bundle.json':raw,
            'evidence/measurement014/qualification/index.json':b'{}',
            'evidence/measurement014/qualification/'+case+'/receipt.json':b'{}',
            'evidence/measurement014/comparison/report.json':json.dumps({'execution_complete':True,'frozen_candidates':24,'attempts':1,
                'cases':[{'instance_id':case,'arms':{'loop':{'record_sha256':hashlib.sha256(raw).hexdigest(),'outcome':'verified_repair','verified':True}}}]}).encode()}
        for name,value in paths.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        (root/'dashboard/lib').mkdir(parents=True)

    def test_selected_download_matches_the_checked_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.source(root)
            prepare(root)
            entries=json.loads((root/'dashboard/lib/comparison014-downloads.json').read_bytes())
            patch=entries['django__django-1-loop']['candidate.patch']
            self.assertEqual(base64.b64decode(patch['base64']),b'checked candidate')

    def test_verified_verdict_with_unmatched_patch_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.source(root,False)
            with self.assertRaisesRegex(ValueError,'matching captured patch'):
                prepare(root)
            self.assertFalse((root/'dashboard/lib/comparison014-downloads.json').exists())
