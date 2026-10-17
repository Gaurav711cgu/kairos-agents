"""A learned index cannot silently accept frozen-base query vectors."""
import copy
import json
from pathlib import Path
import unittest
import pytest
np = pytest.importorskip('numpy')
torch = pytest.importorskip('torch')
from scripts.trained_encoder014 import TrainedCodeEncoder014
from scripts.retrieval011.core import _encoder, Limits

ROOT = Path(__file__).resolve().parents[1]
HEAD = '404b4e89a224ee424da41b650e23619d401e6b9187fd5f1f2209d1190bff62d0'

class BaseFixture:
    dimension = 768
    def __init__(self):
        self.identity = json.loads((ROOT / 'profiles/coderank011.json').read_text())
        self.last_metadata = {}
    def encode(self, texts):
        self.last_metadata = {'query_prefix_applied': False, 'inputs': []}
        return np.tile(np.eye(1, 768, dtype=np.float32), (len(texts), 1))
    def encode_queries(self, texts):
        result = self.encode(texts); self.last_metadata['query_prefix_applied'] = True
        return result

class DeploymentTests(unittest.TestCase):
    def test_same_head_transforms_code_and_query_and_changes_index_identity(self):
        base = BaseFixture()
        deployed = TrainedCodeEncoder014(base, ROOT / 'evidence/measurement014/training/adapter', HEAD)
        code = deployed.encode(['fixture code'])
        query = deployed.encode_queries(['fixture query'])
        np.testing.assert_array_equal(code, query)
        self.assertFalse(np.array_equal(code, base.encode(['fixture code'])))
        self.assertTrue(deployed.last_metadata['query_prefix_applied'])
        self.assertEqual(deployed.last_metadata['learned_projection014']['role'], 'query')
        self.assertNotEqual(_encoder(base, Limits()), _encoder(deployed, Limits()))
        self.assertAlmostEqual(float(np.linalg.norm(query)), 1.0, places=6)

    def test_changed_base_profile_or_corrupt_artifact_is_rejected(self):
        base = BaseFixture();base.identity['max_tokens'] = 1024
        with self.assertRaisesRegex(ValueError, 'exact frozen'):
            TrainedCodeEncoder014(base, ROOT / 'evidence/measurement014/training/adapter', HEAD)
        with self.assertRaisesRegex(ValueError, 'manifest hash'):
            TrainedCodeEncoder014(BaseFixture(), ROOT / 'evidence/measurement014/training/adapter', '0'*64)
