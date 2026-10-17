"""External verification inputs cannot change a registered repair reproduction."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.reproduce_repair014 import checked_materials, run, TASK


class ReproductionTests(unittest.TestCase):
    def test_wrong_upstream_row_is_rejected_before_verifier_generation(self):
        case={'repository':'django/django','revision':'a'*40,'issue':'public issue'}
        with patch('scripts.reproduce_repair014.qualify006.verifier') as generate:
            with self.assertRaisesRegex(ValueError,'registered case'):
                checked_materials(case,{}, {'instance_id':'different'})
            generate.assert_not_called()

    def test_hidden_material_must_match_previously_qualified_hashes(self):
        case={'repository':'django/django','revision':'a'*40,'issue':'public issue',
            'reference_digest':hashlib.sha256(b'expected reference').hexdigest(),
            'verification_digest':hashlib.sha256(b'testsverifier').hexdigest()}
        scope={'added_hidden_tests':[]}
        row={'instance_id':TASK,'repo':case['repository'],'base_commit':case['revision'],
            'problem_statement':case['issue'],'patch':'changed reference','test_patch':'tests'}
        with patch('scripts.reproduce_repair014.qualify006.verifier',return_value=('verifier',scope)):
            with self.assertRaisesRegex(ValueError,'qualified hashes'):
                checked_materials(case,scope,row)

    def test_existing_runtime_is_preserved_without_docker_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);runtime=root/'existing';runtime.mkdir()
            with patch('scripts.reproduce_repair014.package',return_value={}), patch('scripts.reproduce_repair014.subprocess.run') as execute:
                with self.assertRaisesRegex(ValueError,'new reproduction runtime'):
                    run(runtime,[root],root/'external.json',root)
                execute.assert_not_called()
