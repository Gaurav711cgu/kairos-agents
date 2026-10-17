"""Integrity and source-only boundary tests; no model or acquired code executes."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_functions014 as evaluation
import unittest

ROOT = Path(__file__).resolve().parents[1] / "evidence/measurement014/data"
spec = importlib.util.spec_from_file_location("build_functions014", Path(__file__).resolve().parents[1] / "scripts/build_functions014.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceProtocolTests(unittest.TestCase):
    def test_docstring_is_removed_and_original_range_is_exact(self):
        source = 'class Example:\n    def useful(self, value):\n        """Convert the supplied numeric input into the stable canonical output value."""\n        result = value + 1\n        return result\n'
        node = ast.parse(source).body[0].body[0]
        query, code, original, start, end = module.derive(source, node)
        self.assertIn("Convert the supplied", query)
        self.assertNotIn("Convert the supplied", code)
        self.assertEqual(original, "".join(source.splitlines(keepends=True)[1:5]))
        self.assertEqual((start, end), (3, 3))
        ast.parse(code)

    def test_cross_repository_duplicate_quarantines_both(self):
        rows = [{"example_id": "a", "repository": "one/repo", "query": "A maintained query with enough words to compare safely", "code": "def answer(x):\n    result = x + 1\n    return result\n"}, {"example_id": "b", "repository": "two/repo", "query": "Another maintained query describes another distinct public function", "code": "def answer(x):\n    result = x + 1\n    return result\n"}]
        retained, report = module.deduplicate(rows)
        self.assertEqual(retained, [])
        self.assertEqual(len(report["removed"]), 2)

    def test_same_repository_duplicate_keeps_deterministic_copy(self):
        rows = [{"example_id": key, "repository": "one/repo", "query": "A maintained query with enough words to compare safely", "code": "def f(x):\n    result = x + 1\n    return result\n"} for key in ("b", "a")]
        retained, report = module.deduplicate(rows)
        self.assertEqual([r["example_id"] for r in retained], ["a"])

    def test_pinned_source_blob_tampering_rejected(self):
        acquisition = json.loads((ROOT / "raw-v2/acquisition.json").read_text())
        first = next(iter(acquisition["objects"].values()))
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            shutil.copytree(ROOT / "raw-v2", raw)
            path = raw / first["local_path"]
            path.write_bytes(path.read_bytes() + b"\n# tampered\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                module.check_acquisition(raw)

    def test_training_loader_does_not_read_or_need_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "prepared"
            target.mkdir()
            shutil.copytree(ROOT / "prepared/public", target / "public")
            shutil.copyfile(ROOT / "prepared/frozen.json", target / "frozen.json")
            frozen = json.loads((target / "frozen.json").read_text())
            # No raw sources, private manifest, receipts or evaluation directory exist.
            train, development, identity = module.load_for_training014(target, module.sha(module.canonical(frozen)))
            self.assertEqual(len(train), frozen["function_counts"]["train"])
            self.assertEqual(len(development), frozen["function_counts"]["development"])
            self.assertEqual({r["split"] for r in train + development}, {"train", "development"})
            self.assertFalse(identity["original013_issue_family_training_data_ready"])

    def test_untrusted_frozen_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "Trusted frozen hash mismatch"):
            module.load_for_training014(ROOT / "prepared", "0" * 64)

    def test_changed_public_bytes_rejected_before_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "prepared"
            target.mkdir()
            shutil.copytree(ROOT / "prepared/public", target / "public")
            shutil.copyfile(ROOT / "prepared/frozen.json", target / "frozen.json")
            frozen = json.loads((target / "frozen.json").read_text())
            path = target / "public/train.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "public hash mismatch"):
                module.load_for_training014(target, module.sha(module.canonical(frozen)))

    def test_extra_public_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "prepared"
            target.mkdir()
            shutil.copytree(ROOT / "prepared/public", target / "public")
            shutil.copyfile(ROOT / "prepared/frozen.json", target / "frozen.json")
            frozen = json.loads((target / "frozen.json").read_text())
            (target / "public/holdout.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "extra or missing"):
                module.load_for_training014(target, module.sha(module.canonical(frozen)))

    def test_private_evaluator_returns_only_frozen_holdout(self):
        frozen = json.loads((ROOT / "prepared/frozen.json").read_text())
        rows, identity = evaluation.load_for_evaluation014(ROOT / "prepared", module.sha(module.canonical(frozen)))
        self.assertEqual(len(rows), frozen["function_counts"]["holdout"])
        self.assertEqual({row["split"] for row in rows}, {"holdout"})
        self.assertEqual({row["repository"] for row in rows}, {"pallets/click"})
        self.assertTrue(identity["evaluation_only"])

    def test_private_evaluator_rejects_changed_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "prepared"
            shutil.copytree(ROOT / "prepared", target)
            frozen = json.loads((target / "frozen.json").read_text())
            path = target / "evaluation-private/holdout.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "Private evaluator file hash mismatch"):
                evaluation.load_for_evaluation014(target, module.sha(module.canonical(frozen)))


if __name__ == "__main__":
    unittest.main()
