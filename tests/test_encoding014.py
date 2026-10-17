"""Mechanical encoder-boundary tests using a fake encoder; no model weights load."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

DATA = Path(__file__).resolve().parents[1]
STAGE = DATA.parent
spec = importlib.util.spec_from_file_location("encoding_source_protocol014", DATA / "scripts/build_functions014.py")
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)


class Vector:
    def tolist(self):
        return [1.0] + [0.0] * 767


class FakeEncoder:
    calls = []
    metadata_override = None
    vector_override = None

    def __init__(self, directory, profile, *, batch_size, threads):
        self.last_metadata = {}
        self.calls.append(("init", batch_size, threads))

    def run(self, texts, queries):
        self.calls.append(("queries" if queries else "code", list(texts)))
        self.last_metadata = {"query_prefix_applied": queries, "max_tokens": 512, "inputs": [{"input_sha256": protocol.sha(text), "input_tokens_with_special_and_prefix": 5, "encoded_tokens": 5, "truncated": False, "included_character_end": len(text), "omitted_bytes": 0, "scope": "Mechanical fixture"} for text in texts]}
        if self.metadata_override:
            type(self).metadata_override(self.last_metadata)
        return type(self).vector_override(texts) if type(self).vector_override else [Vector() for _ in texts]

    def encode_queries(self, texts):
        return self.run(texts, True)

    def encode(self, texts):
        return self.run(texts, False)


def load_encoder_module():
    scripts = types.ModuleType("scripts")
    scripts.__path__ = []
    build = types.ModuleType("scripts.build_functions014")
    build.load_for_training014 = lambda *_: None
    build.canonical, build.sha = protocol.canonical, protocol.sha
    evaluator = types.ModuleType("scripts.evaluate_functions014")
    evaluator.load_for_evaluation014 = lambda *_: None
    retrieval = types.ModuleType("scripts.retrieval011")
    retrieval.__path__ = []
    encoder = types.ModuleType("scripts.retrieval011.encoder")
    encoder.CodeRankEncoder = FakeEncoder
    encoder.verify_profile = lambda *_: None
    command = types.ModuleType("scripts.retrieval011.__main__")
    command.storage_guard = lambda *_: {"mechanical_fixture": True}
    modules = {"scripts": scripts, "scripts.build_functions014": build, "scripts.evaluate_functions014": evaluator, "scripts.retrieval011": retrieval, "scripts.retrieval011.encoder": encoder, "scripts.retrieval011.__main__": command}
    # Staging location differs from the eventual scripts/ package location.
    path = DATA / "scripts/encode_training014.py"
    if not path.is_file():
        path = STAGE / "encode_training014.py"
    spec = importlib.util.spec_from_file_location("encoding014_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class EncodingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.module = load_encoder_module()
        FakeEncoder.calls = []
        FakeEncoder.metadata_override = None
        FakeEncoder.vector_override = None
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "data").mkdir()
        (self.root / "encoder").mkdir()
        profile_path = DATA / "profiles/coderank011.json"
        if not profile_path.is_file():
            profile_path = DATA / "tests/fixtures/coderank011.json"
        self.profile = json.loads(profile_path.read_text())
        (self.root / "profile.json").write_text(json.dumps(self.profile))
        self.args = argparse.Namespace(data=self.root / "data", output=self.root / "encoded", profile=self.root / "profile.json", encoder_dir=self.root / "encoder", frozen_sha256="a" * 64, budget_root=[self.root], heldout=False)
        self.train = [{"example_id": "train", "query": "Exact maintained query text", "code": "def exact_code(x):\n    return x + 1\n", "split": "train"}]
        self.development = [{"example_id": "development", "query": "Exact development query text", "code": "def development_code(y):\n    return y * 2\n", "split": "development"}]
        self.holdout = [{"example_id": "holdout", "query": "Exact holdout query text", "code": "def holdout_code(z):\n    return z - 3\n", "split": "holdout"}]

    def tearDown(self):
        self.tmp.cleanup()

    def run_encode(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.module.encode(self.args)

    def test_only_exact_training_query_and_code_enter_encoder(self):
        with patch.object(self.module, "load_for_training014", return_value=(self.train, self.development, {})) as admitted, patch.object(self.module, "load_for_evaluation014", side_effect=AssertionError("Trainer touched private evaluator")):
            self.run_encode()
        self.assertEqual(FakeEncoder.calls, [("init", 2, 2), ("queries", [row["query"] for row in self.train + self.development]), ("code", [row["code"] for row in self.train + self.development])])
        admitted.assert_called_once_with(self.args.data, self.args.frozen_sha256)
        cache = json.loads((self.args.output / "embeddings.json").read_text())
        self.assertEqual({row["example_id"] for row in cache["rows"]}, {"train", "development"})
        receipt = json.loads((self.args.output / "receipt.json").read_text())
        self.assertEqual(receipt["encoding"][0]["query"]["input_sha256"], protocol.sha(self.train[0]["query"]))
        self.assertEqual(receipt["encoder"]["max_tokens"], 512)
        self.assertEqual(receipt["encoder"]["profile_sha256"], self.module.PROFILE_SHA256)

    def test_heldout_route_uses_only_trusted_evaluator_loader(self):
        self.args.heldout = True
        with patch.object(self.module, "load_for_training014", side_effect=AssertionError("Wrong training route")), patch.object(self.module, "load_for_evaluation014", return_value=(self.holdout, {"evaluation_only": True})) as evaluator:
            self.run_encode()
        evaluator.assert_called_once_with(self.args.data, self.args.frozen_sha256)
        cache = json.loads((self.args.output / "embeddings.json").read_text())
        self.assertEqual([row["example_id"] for row in cache["rows"]], ["holdout"])
        self.assertEqual(FakeEncoder.calls[1], ("queries", [self.holdout[0]["query"]]))

    def test_profile_hash_and_512_token_ceiling_are_trusted(self):
        self.profile["max_tokens"] = 1024
        self.args.profile.write_text(json.dumps(self.profile))
        with patch.object(self.module, "load_for_training014", return_value=(self.train, [], {})), self.assertRaisesRegex(ValueError, "Trusted encoder profile changed"):
            self.run_encode()
        self.assertEqual(FakeEncoder.calls, [])
        self.assertFalse(self.args.output.exists())

    def test_wrong_metadata_shape_rejected_before_cache(self):
        FakeEncoder.metadata_override = lambda value: value.update(max_tokens=1024)
        with patch.object(self.module, "load_for_training014", return_value=(self.train, [], {})), self.assertRaisesRegex(ValueError, "metadata shape"):
            self.run_encode()
        self.assertFalse((self.args.output / "embeddings.json").exists())

    def test_metadata_cannot_relabel_changed_model_input(self):
        FakeEncoder.metadata_override = lambda value: value["inputs"][0].update(input_sha256="f" * 64)
        with patch.object(self.module, "load_for_training014", return_value=(self.train, [], {})), self.assertRaisesRegex(ValueError, "exact admitted input"):
            self.run_encode()
        self.assertFalse((self.args.output / "embeddings.json").exists())

    def test_invalid_encoder_vector_rejected_before_cache(self):
        class ShortVector:
            def tolist(self):
                return [1.0]
        FakeEncoder.vector_override = lambda texts: [ShortVector() for _ in texts]
        with patch.object(self.module, "load_for_training014", return_value=(self.train, [], {})), self.assertRaisesRegex(ValueError, "768-dimensional"):
            self.run_encode()
        self.assertFalse((self.args.output / "embeddings.json").exists())

    def test_output_symlink_ancestor_rejected(self):
        actual = self.root / "elsewhere"
        actual.mkdir()
        (self.root / "linked").symlink_to(actual, target_is_directory=True)
        self.args.output = self.root / "linked/encoded"
        with self.assertRaisesRegex(ValueError, "new encoding output"):
            self.run_encode()
        self.assertEqual(FakeEncoder.calls, [])

    def test_encoder_directory_must_count_toward_storage_budget(self):
        self.args.encoder_dir = self.root.parent / "outside-owned-root"
        with patch.object(self.module, "load_for_training014", return_value=(self.train, [], {})), self.assertRaisesRegex(ValueError, "aggregate experiment budget"):
            self.run_encode()
        self.assertEqual(FakeEncoder.calls, [])


if __name__ == "__main__":
    unittest.main()
