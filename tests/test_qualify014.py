"""Qualification safety gates; tests never download source or call Docker."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts import qualify014 as q


def diff(name="src/_pytest/example.py", added=1, removed=1):
    before = "".join("-old" + str(i) + "\n" for i in range(removed))
    after = "".join("+new" + str(i) + "\n" for i in range(added))
    return f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n@@ -1,{removed} +1,{added} @@\n" + before + after


def row(identifier="pytest-dev__pytest-1"):
    return {"instance_id": identifier, "repo": "pytest-dev/pytest", "base_commit": "a" * 40,
        "problem_statement": "A behavioral regression", "version": "5.4.1", "created_at": "2020-01-01", "environment_setup_commit": "b" * 40,
        "patch": diff(), "test_patch": diff("testing/test_example.py"), "FAIL_TO_PASS": '["testing/test_example.py::test_one"]', "PASS_TO_PASS": "[]"}


def result(passed=False, **summary):
    return {"passed": passed, "environment_error": False, "returncode": 0 if passed else 1,
        "raw_output": {"complete": True}, "output_limit_exceeded": False,
        "summary": {"execution_complete": True, "complete": passed, "tests_run": 1,
            "regression_failed": [] if passed else ["test_one"], **summary}}


QUALIFIER = SimpleNamespace(scope=lambda value: (["src/_pytest/example.py"], "src/_pytest/", 2),
    test_paths=lambda value: ["testing/test_example.py"], verifier=lambda value, source: ("print('test')\n", {"omissions": []}),
    summary=lambda value: value["summary"])


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def test_scope_rejects_41_lines_and_three_files(self):
        value = row()
        value["patch"] = diff(added=21, removed=20)
        with self.assertRaisesRegex(ValueError, "40 changed"):
            q.source_scope(value, QUALIFIER)
        value["patch"] = "".join(diff(f"src/_pytest/file{n}.py") for n in range(3))
        with self.assertRaisesRegex(ValueError, "two approved"):
            q.source_scope(value, QUALIFIER)

    def test_scope_enforces_all_old_and_new_paths(self):
        for name in ("src/_pytest/../outside.py", "src/_pytest/tests/a.py", "src/_pytest/test_source.py", "src/_pytest/.secret.py", "testing/test_example.py"):
            with self.subTest(name=name):
                value = row()
                value["patch"] = diff(name)
                with self.assertRaises(ValueError):
                    q.source_scope(value, QUALIFIER)
        value = row()
        value["patch"] = diff().replace("--- a/src/_pytest/example.py", "--- a/testing/test_example.py")
        with self.assertRaises(ValueError):
            q.source_scope(value, QUALIFIER)

    def test_scope_uses_git_actual_line_counts(self):
        value = row()
        value["patch"] = diff(added=20, removed=20).replace("-old0", "---old0")
        self.assertEqual(q.source_scope(value, QUALIFIER)["changed_lines"], 40)

    def test_plan_preserves_exact_order_split_and_every_exclusion(self):
        values = [row("pytest-dev__pytest-" + str(n)) for n in range(24)]
        cohort = {"candidates": [{"instance_id": r["instance_id"], "repository": r["repo"], "base_commit": r["base_commit"], "split": "development" if n < 4 else "holdout"} for n, r in enumerate(values)]}
        values[1]["patch"] = diff(added=21, removed=20)
        values[5]["FAIL_TO_PASS"] = "[]"
        frozen = q.plan_for(cohort, {r["instance_id"]: r for r in values}, QUALIFIER)
        self.assertEqual([e["instance_id"] for e in frozen["candidates"]], [r["instance_id"] for r in values])
        self.assertEqual([e["split"] for e in frozen["candidates"]], [e["split"] for e in cohort["candidates"]])
        self.assertEqual([e["status"] for e in frozen["exclusions"]], ["scope_excluded", "input_unavailable"])
        missing = q.plan_for(cohort, {}, QUALIFIER, "Hidden records are absent")
        self.assertEqual(len(missing["exclusions"]), 24)
        self.assertTrue(all(e["status"] == "input_unavailable" for e in missing["candidates"]))

    def split_fixture(self):
        values = [row("pytest-dev__pytest-" + str(n)) for n in range(300)]
        metadata_dir = self.root / "evidence/evaluation013/cohort"
        metadata_dir.mkdir(parents=True)
        q.immutable(metadata_dir / "metadata.json", {"records": [{k: r[k] for k in q.METADATA_FIELDS} for r in values]})
        records, sidecar = self.root / "hidden.json", self.root / "provenance.json"
        q.immutable(records, values)
        q.immutable(sidecar, {"dataset": q.DATASET, "revision": q.REVISION, "split": "test", "rows": 300, "records_sha256": q.sha(records)})
        cohort = {"candidates": [{"instance_id": values[0]["instance_id"], "repository": values[0]["repo"], "base_commit": values[0]["base_commit"], "issue": values[0]["problem_statement"]}]}
        return values, records, sidecar, cohort

    def test_hidden_full_split_exact_metadata_and_hash(self):
        values, records, sidecar, cohort = self.split_fixture()
        self.assertEqual(len(q.hidden_rows(records, sidecar, self.root, cohort)), 300)
        values[0]["problem_statement"] += " changed"
        records.write_bytes(q.encoded(values))
        with self.assertRaisesRegex(q.InputUnavailable, "provenance"):
            q.hidden_rows(records, sidecar, self.root, cohort)
        provenance = q.load(sidecar)
        provenance["records_sha256"] = q.sha(records)
        sidecar.write_bytes(q.encoded(provenance))
        with self.assertRaisesRegex(q.InputUnavailable, "metadata differs"):
            q.hidden_rows(records, sidecar, self.root, cohort)

    def test_hidden_rejects_wrong_revision_even_with_matching_hash(self):
        _, records, sidecar, cohort = self.split_fixture()
        provenance = q.load(sidecar)
        provenance["revision"] = "c" * 40
        sidecar.write_bytes(q.encoded(provenance))
        with self.assertRaises(q.InputUnavailable):
            q.hidden_rows(records, sidecar, self.root, cohort)

    def test_budget_deduplicates_nested_roots_and_reserves_temp_copy(self):
        child = self.root / "child"
        child.mkdir()
        (self.root / "a").write_bytes(b"a" * 10)
        (child / "b").write_bytes(b"b" * 15)
        with patch.object(q, "CAPACITY", 100), patch.object(q, "RESERVE", 10), patch.object(q.shutil, "disk_usage", return_value=SimpleNamespace(free=100)):
            self.assertEqual(q.storage_guard([self.root, child], 20)["owned_bytes"], 25)
            with self.assertRaises(q.StorageFailure):
                q.storage_guard([self.root, child], 76)
            with self.assertRaises(q.StorageFailure):
                q.storage_guard([self.root], 91)

    def test_budget_rejects_symlink_roots(self):
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            q.storage_guard([link])

    def test_qualification_requires_complete_raw_outputs_and_both_behaviors(self):
        baseline, reference = result(), result(True)
        self.assertTrue(q.check_qualified(baseline, reference, QUALIFIER)["qualified"])
        for side, field, value in ((0, "execution_complete", False), (1, "complete", False)):
            pair = copy.deepcopy([baseline, reference])
            pair[side]["summary"][field] = value
            self.assertFalse(q.check_qualified(*pair, QUALIFIER)["qualified"])
        reference["raw_output"]["complete"] = False
        self.assertEqual(q.check_qualified(baseline, reference, QUALIFIER)["status"], "environment_failure")

    def test_baseline_allpass_is_behavioral_mismatch(self):
        self.assertEqual(q.check_qualified(result(True), result(True), QUALIFIER)["status"], "behavioral_mismatch")

    def test_captured_check_reuses_final_result_and_refuses_unknown(self):
        output = self.root / "baseline.json"
        calls = []
        def run():
            calls.append(True)
            return result()
        with patch.object(q, "storage_guard") as guard:
            q.captured_check(output, "baseline", run, "binding", [self.root], 123)
            q.captured_check(output, "baseline", run, "binding", [self.root], 123)
            self.assertEqual(len(calls), 1)
            guard.assert_called_once_with([self.root], q.CHECK_RESERVATION + 123)
        unknown = self.root / "reference.json"
        q.immutable(unknown.with_suffix(".started.json"), {"binding": "binding"})
        with self.assertRaisesRegex(RuntimeError, "no automatic redispatch"):
            q.captured_check(unknown, "reference", run, "binding", [self.root])
        self.assertEqual(len(calls), 1)

    def test_immutable_refuses_overwrite(self):
        target = self.root / "receipt.json"
        q.immutable(target, {"qualified": False})
        q.immutable(target, {"qualified": False})
        with self.assertRaisesRegex(ValueError, "Frozen receipt differs"):
            q.immutable(target, {"qualified": True})

    def execution_fixture(self, interrupt=False):
        value = row()
        entry = {"instance_id": value["instance_id"], "repository": value["repo"], "base_commit": value["base_commit"], "split": "holdout", "status": "eligible", "source_scope": q.source_scope(value, QUALIFIER)}
        counts = {"checks": 0, "proposes": 0}
        def tree_hash(path):
            return q.digest(q.material_manifest(path))
        def source(value, work, roots, allow, tree):
            source = work / "source"
            moved = work / "registry/cases" / value["instance_id"] / "source"
            if moved.exists():
                source = moved
            if not source.exists():
                (source / "src/_pytest").mkdir(parents=True)
                (source / "src/_pytest/example.py").write_text("old0\n")
                q.immutable(work / "source.json", {"repository": value["repo"], "revision": value["base_commit"], "source_digest": tree(source), "source_url": "https://codeload.github.com/pinned"})
            return source, q.load(work / "source.json")
        class FakeRegistry:
            def __init__(self, manifest, runtime):
                self.runtime = runtime
        class FakeWorkspace:
            def __init__(self, registry, case):
                self.root = registry.runtime / "cases" / case["id"] / "source"
                self.reference = False
            def checks(self):
                counts["checks"] += 1
                return result(self.reference)
            def propose(self, patch):
                counts["proposes"] += 1
                if interrupt and counts["proposes"] == 1:
                    raise KeyboardInterrupt("simulate process termination before reference dispatch")
                self.reference = True
            def close(self):
                pass
        return value, entry, counts, source, (QUALIFIER, FakeRegistry, tree_hash, FakeWorkspace)

    def test_execute_retains_hashes_and_checks_before_owned_cleanup(self):
        value, entry, counts, source, deps = self.execution_fixture()
        out = self.root / "out"
        out.mkdir()
        with patch.object(q, "pinned_source", side_effect=source):
            receipt = q.execute_case(entry, value, out, [self.root], "binding", False, deps)
            again = q.execute_case(entry, value, out, [self.root], "binding", False, deps)
        self.assertTrue(receipt["qualified"])
        self.assertEqual(receipt, again)
        self.assertEqual(counts["checks"], 2)
        evidence = out / "cases" / value["instance_id"]
        self.assertTrue((evidence / "baseline.json").exists())
        self.assertTrue((evidence / "reference.json").exists())
        self.assertFalse((out / "work" / value["instance_id"]).exists())
        self.assertTrue(q.load(evidence / "material-manifest.json")["files"])
        self.assertFalse(q.load(evidence / "case-definition.json")["qualified"])

    def test_resume_uses_captured_baseline_after_process_interruption(self):
        value, entry, counts, source, deps = self.execution_fixture(interrupt=True)
        out = self.root / "out"
        out.mkdir()
        with patch.object(q, "pinned_source", side_effect=source):
            with self.assertRaises(KeyboardInterrupt):
                q.execute_case(entry, value, out, [self.root], "binding", False, deps)
            receipt = q.execute_case(entry, value, out, [self.root], "binding", False, deps)
        self.assertTrue(receipt["qualified"])
        self.assertEqual(counts["checks"], 2)  # One baseline and one reference total.

    def test_completed_receipt_tampering_is_refused(self):
        value, entry, _, source, deps = self.execution_fixture()
        out = self.root / "out"
        out.mkdir()
        with patch.object(q, "pinned_source", side_effect=source):
            q.execute_case(entry, value, out, [self.root], "binding", False, deps)
            target = out / "cases" / value["instance_id"] / "baseline.json"
            target.write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "evidence changed"):
                q.execute_case(entry, value, out, [self.root], "binding", False, deps)

    def test_report_missing_inputs_never_claims_qualification(self):
        candidates = [{"instance_id": f"case-{n}", "repository": "django/django" if n < 12 else "pytest-dev/pytest", "split": "development" if n % 12 < 4 else "holdout", "status": "input_unavailable"} for n in range(24)]
        report = q.report({"candidates": candidates}, {}, True)
        self.assertEqual(report["counts"]["input_unavailable"], 24)
        self.assertEqual(report["qualified"], 0)
        self.assertFalse(report["performed"])
        self.assertFalse(report["qualification_complete"])


if __name__ == "__main__":
    unittest.main()
