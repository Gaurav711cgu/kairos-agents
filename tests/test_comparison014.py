"""Fixture-only frozen-study and qualification admission checks."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import comparison014 as c


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(c.canonical(value))


def check(passed):
    summary = {"execution_complete": True, "complete": passed, "tests_run": 2, "regression_failed": [] if passed else ["test_regression"]}
    stdout = "KAIROS_VERIFIER_RESULT " + json.dumps(summary) + "\n"
    raw = {"encoding": "base64", "complete": True}
    for name, data in (("stdout", stdout.encode()), ("stderr", b"")):
        raw[name] = {"data": base64.b64encode(data).decode(), "bytes": len(data), "observed_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "truncated": False}
    return {"passed": passed, "returncode": 0 if passed else 1, "environment_error": False,
        "stdout": stdout, "stderr": "", "raw_output": raw, "output_limit_exceeded": False}


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def qualification(self):
        case = {"id": "pytest-dev__pytest-1", "split": "holdout", "qualified": True, "source_digest": "a" * 64}
        files = {"baseline.json": {"result": check(False)}, "reference.json": {"result": check(True)},
            "case-definition.json": {**case, "qualified": False}, "source.json": {}, "material-manifest.json": {}, "test-scope.json": {}}
        for name, value in files.items():
            save(self.root / name, value)
        receipt = {"instance_id": case["id"], "split": "holdout", "qualified": True, "status": "qualified",
            "evidence_sha256": {name: c.sha(self.root / name) for name in files}}
        save(self.root / "receipt.json", receipt)
        return case, receipt

    def test_complete_evidence_admitted_and_changed_case_refused(self):
        case, _ = self.qualification()
        receipt = self.root / "receipt.json"
        self.assertTrue(c.validate_qualification014(receipt, c.sha(receipt), case)["qualified"])
        with self.assertRaisesRegex(ValueError, "Rehydrated registered case differs"):
            c.validate_qualification014(receipt, c.sha(receipt), {**case, "source_digest": "b" * 64})

    def test_rebound_allpass_baseline_still_refused(self):
        case, receipt = self.qualification()
        save(self.root / "baseline.json", {"result": check(True)})
        receipt["evidence_sha256"]["baseline.json"] = c.sha(self.root / "baseline.json")
        save(self.root / "receipt.json", receipt)
        with self.assertRaisesRegex(ValueError, "baseline regression failure"):
            c.validate_qualification014(self.root / "receipt.json", c.sha(self.root / "receipt.json"), case)

    def test_raw_output_hash_tampering_is_refused(self):
        result = check(True)
        self.assertTrue(c.raw_complete014(result))
        result["raw_output"]["stdout"]["sha256"] = "0" * 64
        self.assertFalse(c.raw_complete014(result))
        result = check(True)
        result["raw_output"]["stdout"]["truncated"] = True
        self.assertFalse(c.raw_complete014(result))

    def test_qualification_artifact_tampering_is_refused(self):
        case, _ = self.qualification()
        (self.root / "reference.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            c.validate_qualification014(self.root / "receipt.json", c.sha(self.root / "receipt.json"), case)

    def study(self):
        cases = [{"instance_id": f"case-{n}", "split": "development" if n % 12 < 4 else "holdout", "qualification_receipt_sha256": "a" * 64} for n in range(24)]
        cohort = {"candidates": copy.deepcopy(cases)}
        study = {"version": c.VERSION, "cohort_sha256": c.COHORT_SHA, "arms": list(c.ARMS), "cases": cases,
            "strategy_profiles_sha256": c.digest(c.strategy_profiles014())}
        save(self.root / "study.json", study)
        return study, cohort

    def test_study_binds_all24_order_splits_and_profiles(self):
        study, cohort = self.study()
        target = self.root / "study.json"
        self.assertEqual(c.validate_study014(target, c.sha(target), cohort), study)
        study["cases"][0], study["cases"][1] = study["cases"][1], study["cases"][0]
        save(target, study)
        with self.assertRaisesRegex(ValueError, "order and splits"):
            c.validate_study014(target, c.sha(target), cohort)
        study["cases"] = cohort["candidates"]
        study["strategy_profiles_sha256"] = "b" * 64
        save(target, study)
        with self.assertRaisesRegex(ValueError, "strategy profiles"):
            c.validate_study014(target, c.sha(target), cohort)

    def test_uninstalled_staged_source_refused_before_execution(self):
        args = SimpleNamespace(arm="drafts", checkout=self.root)
        with patch.object(c, "policy012", return_value=SimpleNamespace(source_files=())):
            with self.assertRaisesRegex(ValueError, "Install reviewed comparison source"):
                c.make_policy014(args, None, None, {}, "a" * 64)


if __name__ == "__main__":
    unittest.main()
