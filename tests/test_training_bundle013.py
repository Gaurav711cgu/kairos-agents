"""Synthetic fixtures exercise preparation boundaries, never serve as training data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import scripts.training_bundle013 as b

AUDIT = b.canonical({"exposures": [], "exposed_issue_digests": []})
NOW = "2026-10-16T00:00:00Z"


def sign(data, approved=True):
    content = {k: v for k, v in data.items() if k != "export_review"}
    data["export_review"] = {"reviewer": "synthetic-reviewer", "reviewed_at": NOW,
                             "approved": approved, "inventory_content_sha256": b.sha(b.canonical(content))}
    return data


def fixture(keys):
    data = {"schema_version": b.VERSION, "study_id": "synthetic-tests-only", "examples": [],
            "families": {}, "unresolved_families": [], "rights": {}, "receipts": {}, "exposures": {},
            "guard": {**b.audit_guard(AUDIT), "reviewer": "synthetic-reviewer", "reviewed_at": NOW,
                      "reserved_components": [], "locked_components": []}}
    for key in keys:
        repo, issue = key.split("#")
        query = " ".join(b.sha(f"{key}/{i}")[:12] for i in range(12))
        source = f"value = '{b.sha(key)[:10]}'\n"
        row = {"kind": "retrieval", "instance_id": repo.replace("/", "__") + "-" + issue,
               "repository": repo, "upstream_issue_id": issue, "dataset_id": "synthetic-tests-only",
               "dataset_revision": "a" * 40, "source_commit": "b" * 40, "acquired_at": NOW,
               "query": query, "issue_sha256": b.sha(query), "path": "src/example.py", "source_text": source,
               "source_file_sha256": b.sha(source), "start_line": 1, "end_line": 1, "code": source,
               "chunk_sha256": b.sha(source), "rights_refs": [], "exposure_refs": [key],
               "relevance": 1, "negative_method": None}
        label = {"kind": "relevance_review", **{k: row[k] for k in b.BINDING + ["chunk_sha256", "relevance"]},
                 "method": "independent_review", "reviewer": "synthetic-reviewer", "reviewed_at": NOW}
        digest = b.sha(b.canonical(label))
        data["receipts"][digest] = label
        row["label_provenance"] = {k: label[k] for k in ("method", "reviewer", "reviewed_at")}
        row["label_provenance"]["receipt_sha256"] = digest
        revisions = {"issue": row["issue_sha256"], "source": row["source_commit"], "label": digest, "dataset": row["dataset_revision"]}
        data["families"][key] = [key]
        for kind, revision in revisions.items():
            ref = key + ":" + kind
            row["rights_refs"].append(ref)
            data["rights"][ref] = {"component_key": key, "kind": kind, "origin": "https://example.org/synthetic-fixture",
                                   "revision": revision, "license_or_terms": "Synthetic test fixture only",
                                   "evidence_sha256": b.sha("synthetic"), "notices": ["Synthetic; not a public dataset."],
                                   "reviewer": "synthetic-reviewer", "reviewed_at": NOW,
                                   "training_allowed": True, "redistribution_allowed": True}
        data["exposures"][key] = {"component_key": key, "issue_sha256": row["issue_sha256"], "kind": "acquisition_review", "reviewed_at": NOW}
        data["examples"].append(row)
    return sign(data)


def key_for(split):
    return next(f"owner/repo#{i}" for i in range(1, 1000) if b.assigned(f"owner/repo#{i}") == split)


def repair_fixture():
    data = fixture([key_for("train")])
    row = data["examples"][0]
    for key in b.RETRIEVAL:
        row.pop(key)
    row.update(kind="repair", target_patch="--- a/src/example.py\n+++ b/src/example.py\n@@ -1 +1 @@\n-old\n+new\n",
               verifier_revision="c" * 40, outcome="verified_repair", outcome_provenance="original", target_use="supervised_loss_only")
    row["target_patch_sha256"] = b.sha(row["target_patch"])
    for kind in ("baseline_failure", "verification_pass"):
        receipt = {"kind": kind, **{k: row[k] for k in b.BINDING + ["target_patch_sha256", "verifier_revision", "outcome_provenance"]},
                   "tests_sha256": b.sha("test suite"), "passed": 2 if kind == "baseline_failure" else 3,
                   "failed": 1 if kind == "baseline_failure" else 0, "total": 3, "independent": True}
        digest = b.sha(b.canonical(receipt))
        data["receipts"][digest] = receipt
        row[kind + "_receipt_sha256"] = digest
    component = key_for("train")
    data["rights"][component + ":label"]["revision"] = row["verification_pass_receipt_sha256"]
    patch_right = dict(data["rights"][component + ":source"], kind="patch", revision=row["target_patch_sha256"])
    data["rights"][component + ":patch"] = patch_right
    row["rights_refs"].append(component + ":patch")
    return sign(data)


class BundleTests(unittest.TestCase):
    def test_split_is_deterministic_and_issue_revisions_stay_together(self):
        data = fixture([key_for("train"), key_for("development")])
        extra = copy.deepcopy(data["examples"][0])
        extra["dataset_id"] = "second-package"
        data["examples"].append(extra)
        one = b.freeze(sign(data), AUDIT)[0]
        data["examples"].reverse()
        two = b.freeze(sign(data), AUDIT)[0]
        self.assertEqual(one["assignments"], two["assignments"])
        self.assertEqual(one["distinct_issue_counts"], {"train": 1, "development": 1, "holdout": 0})
        self.assertEqual(one["deduplicated_rows"], 2)
        self.assertEqual(len(one["duplicates"]), 1)

    def test_locked_exposed_and_reserved_components_are_excluded(self):
        keys = ["owner/repo#1", "owner/repo#2", "owner/repo#3"]
        data = fixture(keys)
        data["guard"]["locked_components"] = [keys[0]]
        data["guard"]["reserved_components"] = [keys[1]]
        audit = b.canonical({"exposures": [{"instance_id": "owner__repo-3-scope"}], "exposed_issue_digests": []})
        data["guard"].update(b.audit_guard(audit))
        frozen = b.freeze(sign(data), audit)[0]
        self.assertFalse(frozen["assignments"])
        self.assertEqual(len(frozen["quarantine"]), 3)
        data["guard"]["identities"] = []
        with self.assertRaisesRegex(ValueError, "missing exposures"):
            b.freeze(sign(data), audit)

    def test_exposed_original_issue_digest_blocks_new_alias(self):
        data = fixture(["other/project#9"])
        digest = data["examples"][0]["issue_sha256"]
        audit = b.canonical({"exposures": [], "exposed_issue_digests": [digest]})
        data["guard"].update(b.audit_guard(audit))
        self.assertFalse(b.freeze(sign(data), audit)[0]["assignments"])

    def test_audit_lowercase_whitespace_digest_blocks_case_changed_alias(self):
        data = fixture(["other/project#9"])
        row = data["examples"][0]
        historical_digest = b.audit_issue_sha(row["query"])
        row["query"] = "  " + row["query"].upper().replace(" ", "\t\n") + "  "
        row["issue_sha256"] = b.sha(row["query"])
        self.assertNotEqual(row["issue_sha256"], historical_digest)
        old = row["label_provenance"]["receipt_sha256"]
        receipt = dict(data["receipts"][old], issue_sha256=row["issue_sha256"])
        digest = b.sha(b.canonical(receipt))
        data["receipts"][digest] = receipt
        row["label_provenance"]["receipt_sha256"] = digest
        data["rights"]["other/project#9:label"]["revision"] = digest
        data["rights"]["other/project#9:issue"]["revision"] = row["issue_sha256"]
        data["exposures"]["other/project#9"]["issue_sha256"] = row["issue_sha256"]
        audit = b.canonical({"exposures": [], "exposed_issue_digests": [historical_digest]})
        data["guard"].update(b.audit_guard(audit))
        self.assertFalse(b.freeze(sign(data), audit)[0]["assignments"])

    def test_cross_family_exact_and_normalized_duplicates_quarantine_both(self):
        data = fixture(["owner/repo#1", "owner/repo#2"])
        left, right = data["examples"]
        # Rebuild the second reviewed fixture around equivalent issue bytes.
        for query in (left["query"], "  " + left["query"].replace(" ", "\r\n  ") + " "):
            test = copy.deepcopy(data)
            row = test["examples"][1]
            row["query"], row["issue_sha256"] = query, b.sha(query)
            ref = row["label_provenance"]["receipt_sha256"]
            receipt = dict(test["receipts"][ref], issue_sha256=b.sha(query))
            new_ref = b.sha(b.canonical(receipt))
            test["receipts"][new_ref] = receipt
            row["label_provenance"]["receipt_sha256"] = new_ref
            test["rights"]["owner/repo#2:label"]["revision"] = new_ref
            test["rights"]["owner/repo#2:issue"]["revision"] = b.sha(query)
            test["exposures"]["owner/repo#2"]["issue_sha256"] = b.sha(query)
            frozen = b.freeze(sign(test), AUDIT)[0]
            self.assertEqual(set(frozen["quarantine"]), {"owner/repo#1", "owner/repo#2"})

    def test_shared_original_code_does_not_imply_relevance_or_duplicates(self):
        data = fixture(["owner/repo#1", "owner/repo#2"])
        left, right = data["examples"]
        for key in ("source_text", "source_file_sha256", "code", "chunk_sha256"):
            right[key] = left[key]
        old = right["label_provenance"]["receipt_sha256"]
        receipt = dict(data["receipts"][old], source_file_sha256=right["source_file_sha256"], chunk_sha256=right["chunk_sha256"])
        digest = b.sha(b.canonical(receipt))
        data["receipts"][digest] = receipt
        right["label_provenance"]["receipt_sha256"] = digest
        data["rights"]["owner/repo#2:label"]["revision"] = digest
        self.assertEqual(len(b.freeze(sign(data), AUDIT)[0]["assignments"]), 2)

    def test_invalid_source_paths_hashes_and_private_strings_reject(self):
        data = fixture([key_for("train")])
        for field, value in (("path", "../escape.py"), ("path", "/absolute.py"), ("path", ".git/config"),
                             ("path", "src//example.py"), ("source_file_sha256", "0" * 64),
                             ("code", "changed\n"), ("dataset_id", "/Users/private/runtime")):
            test = copy.deepcopy(data)
            test["examples"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                b.freeze(sign(test), AUDIT)
        with self.assertRaises(ValueError):
            b.public({"value": "C:\\Users\\person\\runtime"})

    def test_rights_deny_quarantines_and_wrong_revision_rejects(self):
        data = fixture(["owner/repo#1"])
        data["rights"]["owner/repo#1:issue"]["training_allowed"] = False
        self.assertFalse(b.freeze(sign(data), AUDIT)[0]["assignments"])
        data["rights"]["owner/repo#1:source"]["revision"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "rights revision"):
            b.freeze(sign(data), AUDIT)

    def test_positive_receipt_binds_source_label_and_issue(self):
        data = fixture(["owner/repo#1"])
        row = data["examples"][0]
        row["relevance"] = 0
        row["negative_method"] = {"method": "within_component", "miner_revision": "a" * 40, "component_key": "owner/repo#1"}
        with self.assertRaisesRegex(ValueError, "receipt binding"):
            b.freeze(sign(data), AUDIT)

    def test_small_dataset_and_122_duplicate_records_do_not_pass_gate(self):
        data = fixture(["owner/repo#1", "owner/repo#2"])
        data["examples"] = [copy.deepcopy(data["examples"][i % 2]) for i in range(122)]
        frozen = b.freeze(sign(data), AUDIT)[0]
        self.assertFalse(frozen["training_data_ready"])
        self.assertEqual(frozen["deduplicated_rows"], 2)
        self.assertEqual(sum(frozen["positive_issue_counts"].values()), 2)

    def test_export_omits_holdout_receipts_and_full_source(self):
        train, holdout = key_for("train"), key_for("holdout")
        data = fixture([train, holdout])
        frozen = b.freeze(data, AUDIT)[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve() / "bundle"
            receipt = b.export(data, frozen, root, AUDIT)
            with zipfile.ZipFile(root / "training-bundle.zip") as archive:
                self.assertEqual(set(archive.namelist()), set(receipt["files"]))
                public_bytes = b"".join(archive.read(name) for name in archive.namelist())
                self.assertNotIn(holdout.encode(), public_bytes)
                self.assertNotIn(data["examples"][1]["query"].encode(), public_bytes)
                self.assertNotIn(b'"source_text"', public_bytes)
                self.assertNotIn("receipts.json", archive.namelist())
                self.assertNotIn(b'"independent":true', public_bytes)
                row = json.loads(archive.read("train.jsonl"))
                self.assertEqual(b.model_input(row), {"query": row["query"], "code": row["code"]})
                example_id = row.pop("example_id")
                self.assertEqual(example_id, b.sha(b.canonical(row)))
            self.assertIn(holdout, (root / "holdout-manifest.private.json").read_text())
            self.assertEqual(receipt["archive_sha256"], b.sha((root / "training-bundle.zip").read_bytes()))

    def test_frozen_and_manual_review_drift_prevent_export(self):
        data = fixture([key_for("train")])
        frozen = b.freeze(data, AUDIT)[0]
        with tempfile.TemporaryDirectory() as temp:
            data["study_id"] = "changed"
            with self.assertRaisesRegex(ValueError, "review does not bind"):
                b.export(data, frozen, Path(temp) / "first", AUDIT)
            sign(data)
            with self.assertRaisesRegex(ValueError, "frozen inventory/protocol drift"):
                b.export(data, frozen, Path(temp) / "second", AUDIT)
            frozen = b.freeze(sign(data, approved=False), AUDIT)[0]
            with self.assertRaisesRegex(ValueError, "manual export review"):
                b.export(data, frozen, Path(temp) / "third", AUDIT)

    def test_unknown_fields_duplicate_keys_and_symlink_inputs_reject(self):
        data = fixture(["owner/repo#1"])
        data["examples"][0]["hidden_target"] = "answer"
        with self.assertRaisesRegex(ValueError, "missing or unknown"):
            b.freeze(sign(data), AUDIT)
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "inventory.json"
            file.write_text('{"same":1,"same":2}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                b.load(file)
            link = Path(temp) / "link.json"
            link.symlink_to(file)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                b.load(link)

    def test_verified_repair_receipts_bind_exact_patch_and_baseline(self):
        data = repair_fixture()
        frozen = b.freeze(data, AUDIT)[0]
        self.assertEqual(sum(frozen["positive_issue_counts"].values()), 1)
        row = data["examples"][0]
        old = row["baseline_failure_receipt_sha256"]
        bad = dict(data["receipts"][old], failed=0, passed=3)
        digest = b.sha(b.canonical(bad))
        data["receipts"][digest] = bad
        row["baseline_failure_receipt_sha256"] = digest
        with self.assertRaisesRegex(ValueError, "baseline must fail"):
            b.freeze(sign(data), AUDIT)

    def test_repair_and_relevance_receipts_reject_commit_or_path_retag(self):
        for make in (repair_fixture, lambda: fixture([key_for("train")])):
            original = make()
            for field, value in (("source_commit", "d" * 40), ("path", "other/example.py")):
                data = copy.deepcopy(original)
                row = data["examples"][0]
                row[field] = value
                if field == "source_commit":
                    data["rights"][key_for("train") + ":source"]["revision"] = value
                with self.subTest(kind=row["kind"], field=field), self.assertRaisesRegex(ValueError, "receipt binding"):
                    b.freeze(sign(data), AUDIT)

    def test_repair_target_never_enters_model_input(self):
        data = repair_fixture()
        frozen = b.freeze(data, AUDIT)[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve() / "repair"
            b.export(data, frozen, root, AUDIT)
            row = json.loads((root / "public/train.jsonl").read_text())
            self.assertIn("target_patch", row)
            self.assertNotIn("target_patch", b.model_input(row))
            row["split"] = "holdout"
            with self.assertRaisesRegex(ValueError, "held-out"):
                b.model_input(row)

    def test_near_and_short_issue_texts_require_quarantine(self):
        for short in (False, True):
            data = fixture(["owner/repo#1", "owner/repo#2"])
            base = " ".join("word" + str(i) for i in range(50))
            for i, row in enumerate(data["examples"]):
                query = ("short " + str(i)) if short else base + " ending" + str(i)
                row["query"], row["issue_sha256"] = query, b.sha(query)
                old = row["label_provenance"]["receipt_sha256"]
                receipt = dict(data["receipts"][old], issue_sha256=b.sha(query))
                digest = b.sha(b.canonical(receipt))
                data["receipts"][digest] = receipt
                row["label_provenance"]["receipt_sha256"] = digest
                key = b.identity(row)
                data["rights"][key + ":label"]["revision"] = digest
                data["rights"][key + ":issue"]["revision"] = b.sha(query)
                data["exposures"][key]["issue_sha256"] = b.sha(query)
            self.assertEqual(len(b.freeze(sign(data), AUDIT)[0]["quarantine"]), 2)

    def test_explicit_family_aliases_share_one_split_and_weight(self):
        data = fixture(["owner/repo#1", "owner/repo#2"])
        data["families"] = {"owner/repo#1": ["owner/repo#1", "owner/repo#2"]}
        for right in data["rights"].values():
            right["component_key"] = "owner/repo#1"
        data["exposures"]["owner/repo#2"]["component_key"] = "owner/repo#1"
        frozen = b.freeze(sign(data), AUDIT)[0]
        self.assertEqual(len(frozen["assignments"]), 1)
        self.assertEqual(sum(frozen["distinct_issue_counts"].values()), 1)

    def test_symlink_export_parent_is_rejected(self):
        data = fixture([key_for("train")])
        frozen = b.freeze(data, AUDIT)[0]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            (base / "real").mkdir()
            (base / "link").symlink_to(base / "real", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                b.export(data, frozen, base / "link" / "output", AUDIT)

    def test_gate_needs_positive_families_in_every_required_split(self):
        keys = []
        for repo in ("first/repo", "second/repo"):
            for split, count in (("train", 20), ("development", 4), ("holdout", 8)):
                keys.extend([f"{repo}#{i}" for i in range(1, 10000) if b.assigned(f"{repo}#{i}") == split][:count])
        data = fixture(keys)
        self.assertTrue(b.freeze(data, AUDIT)[0]["training_data_ready"])
        for row in data["examples"]:
            row["relevance"] = 0
            component = b.identity(row)
            row["negative_method"] = {"method": "within_component", "miner_revision": "a" * 40, "component_key": component}
            old = row["label_provenance"]["receipt_sha256"]
            receipt = dict(data["receipts"][old], relevance=0)
            digest = b.sha(b.canonical(receipt))
            data["receipts"][digest] = receipt
            row["label_provenance"]["receipt_sha256"] = digest
            data["rights"][component + ":label"]["revision"] = digest
        frozen = b.freeze(sign(data), AUDIT)[0]
        self.assertEqual(frozen["distinct_issue_counts"], {"train": 40, "development": 8, "holdout": 16})
        self.assertFalse(frozen["training_data_ready"])


if __name__ == "__main__":
    unittest.main()
