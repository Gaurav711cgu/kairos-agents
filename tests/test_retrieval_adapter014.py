"""Synthetic, explicitly labeled fixtures test mechanics, never model quality."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

try:
    import torch
    local_trainer = Path(__file__).with_name("retrieval_adapter014.py")
    if local_trainer.is_file():
        spec = importlib.util.spec_from_file_location("retrieval_adapter014", local_trainer)
        trainer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = trainer
        spec.loader.exec_module(trainer)
    elif importlib.util.find_spec("scripts.retrieval_adapter014"):
        from scripts import retrieval_adapter014 as trainer
    else:
        import retrieval_adapter014 as trainer
except ImportError as error:
    raise unittest.SkipTest("Optional retrieval-adapter ML dependencies are unavailable: " + str(error)) from error


TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


def fixture_data(dimension=24):
    """Four artificial geometry tasks; training/development are test fixtures."""
    rows, vectors = {}, {}
    for split in ("train", "development"):
        rows[split] = []
        for task in range(4):
            query, positive, negative = [torch.zeros(dimension) for _ in range(3)]
            query[task], positive[task + 4] = 1, 1
            negative[task], negative[task + 8] = 0.8, 0.6
            for label, code in ((1, positive), (0, negative)):
                name = trainer.sha(f"FIXTURE ONLY {split} {task} {label}")
                rows[split].append({"example_id": name, "component_key": f"fixture/{split}#{task}",
                                    "issue_sha256": trainer.sha(f"fixture query {task}"),
                                    "source_commit": "0" * 40, "split": split, "relevance": label})
                vectors[name] = (query, code)
    cache = trainer.EmbeddingCache(vectors, dimension, {"data_kind": "fixture"})
    return rows, cache


def fixture_session(dimension=24, *, encoder=None):
    rows, cache = fixture_data(dimension)
    identity = {"data_kind": "fixture", "note": "synthetic mechanics only"}
    if encoder is not None:
        identity["encoder"] = encoder
    return trainer.TrainingSession(rows, cache, identity)


class TrainerMechanicsTests(unittest.TestCase):
    def test_fixture_has_real_gradients_and_improves_constructed_geometry(self):
        session = fixture_session()
        initial = copy.deepcopy(session.model.state_dict())
        for _ in range(trainer.PROTOCOL["steps"]):
            session.update()
        self.assertLess(session.loss_trace[-1], session.loss_trace[0] / 4)
        self.assertTrue(any(not torch.equal(initial[k], v) for k, v in session.model.state_dict().items()))
        self.assertGreater(session.history[-1]["metrics"]["summary"]["adapter"]["mrr"],
                           session.history[0]["metrics"]["summary"]["base"]["mrr"])
        self.assertEqual([h["step"] for h in session.history], list(range(0, 201, 20)))

    def test_complete_resume_restores_adam_step_rng_and_sampler_bitwise(self):
        uninterrupted = fixture_session()
        for _ in range(200):
            uninterrupted.update()
        expected_python, expected_torch = random.random(), torch.rand(8)
        interrupted = fixture_session()
        for _ in range(37):
            interrupted.update()
        with tempfile.TemporaryDirectory(prefix="kairos014-fixture-", dir=TEMP_ROOT) as root:
            checkpoint = Path(root) / "checkpoint"
            digest = interrupted.save(checkpoint)
            self.assertEqual({p.name for p in checkpoint.iterdir()}, {"manifest.json", "state.safetensors"})
            next_python, next_torch = random.random(), torch.rand(8)
            resumed = fixture_session()
            resumed.restore(checkpoint, digest)
            self.assertEqual(random.random(), next_python)
            self.assertTrue(torch.equal(torch.rand(8), next_torch))
            # Restore again because the assertions consumed the saved RNG state.
            resumed.restore(checkpoint, digest)
            for _ in range(37, 200):
                resumed.update()
        self.assertEqual(resumed.step, 200)
        self.assertEqual(resumed.loss_trace, uninterrupted.loss_trace)
        self.assertEqual(resumed.history, uninterrupted.history)
        self.assertEqual(resumed.sampler.order, uninterrupted.sampler.order)
        self.assertEqual(resumed.sampler.cursor, uninterrupted.sampler.cursor)
        self.assertEqual(resumed.sampler.epoch, uninterrupted.sampler.epoch)
        self.assertTrue(torch.equal(resumed.sampler.generator.get_state(), uninterrupted.sampler.generator.get_state()))
        for key, value in uninterrupted.model.state_dict().items():
            self.assertTrue(torch.equal(resumed.model.state_dict()[key], value), key)
            self.assertTrue(torch.equal(resumed.best_state[key], uninterrupted.best_state[key]), key)
        expected_optimizer = uninterrupted.optimizer.state_dict()
        actual_optimizer = resumed.optimizer.state_dict()
        self.assertEqual(expected_optimizer["param_groups"], actual_optimizer["param_groups"])
        for index, state in expected_optimizer["state"].items():
            for key, value in state.items():
                self.assertTrue(torch.equal(actual_optimizer["state"][index][key], value), key)
        self.assertEqual(random.random(), expected_python)
        self.assertTrue(torch.equal(torch.rand(8), expected_torch))

    def test_step_zero_resume_is_valid(self):
        session = fixture_session()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            checkpoint = Path(root) / "zero"
            digest = session.save(checkpoint)
            restored = fixture_session()
            restored.restore(checkpoint, digest)
            self.assertEqual(restored.step, 0)
            self.assertEqual(restored.sampler.order, [])
            self.assertEqual(restored.update(), session.update())

    def test_checkpoint_corruption_and_data_drift_rejected(self):
        session = fixture_session()
        session.update()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            checkpoint = Path(root) / "checkpoint"
            digest = session.save(checkpoint)
            with self.assertRaisesRegex(ValueError, "manifest hash"):
                trainer.read_checkpoint(checkpoint, "0" * 64)
            other = fixture_session()
            other.identity = {"data_kind": "different fixture"}
            with self.assertRaisesRegex(ValueError, "data, implementation or protocol"):
                other.restore(checkpoint, digest)
            weights = checkpoint / "state.safetensors"
            weights.write_bytes(weights.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "tensor hash"):
                trainer.read_checkpoint(checkpoint, digest)

    def test_selected_projection_is_best_snapshot_not_last_weights(self):
        session = fixture_session()
        for _ in range(40):
            session.update()
        session.best_step = 0
        with torch.no_grad():
            session.best_state["up.weight"].zero_()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            checkpoint = Path(root) / "checkpoint"
            digest = session.save(checkpoint)
            model, metadata = trainer.load_projection(checkpoint, digest)
            self.assertEqual(metadata["best_step"], 0)
            self.assertTrue(torch.equal(model.up.weight, torch.zeros_like(model.up.weight)))
            self.assertFalse(torch.equal(model.up.weight, session.model.up.weight))

    def test_pairs_stay_within_issue_and_family_weights_total_equal(self):
        rows, cache = fixture_data()
        groups = trainer.groups_for(rows["train"], cache.vectors)
        pairs, weights = trainer.pair_table(groups)
        totals = {}
        for (group, positive, negative), weight in zip(pairs, weights):
            self.assertEqual(groups[group]["rows"][positive]["relevance"], 1)
            self.assertEqual(groups[group]["rows"][negative]["relevance"], 0)
            family = groups[group]["key"][0]
            totals[family] = totals.get(family, 0) + weight
        self.assertEqual(len(set(totals.values())), 1)
        rows["train"][0]["split"] = "holdout"
        with self.assertRaisesRegex(ValueError, "held-out"):
            trainer.groups_for(rows["train"], cache.vectors)

    def test_fixture_cannot_enter_production_fit(self):
        rows, cache = fixture_data()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            with self.assertRaisesRegex(ValueError, "reviewed"):
                trainer.fit(trainer.ReviewedBundle(rows, {"data_kind": "fixture"}), cache, Path(root) / "run")

    def test_exported_json_head_roundtrips_selected_weights_only(self):
        session = fixture_session(768, encoder={**trainer.ENCODER, "profile_sha256": trainer.APPROVED_PROFILE_SHA256})
        # Production geometry with synthetic selected values; no optimization needed.
        session.best_state["up.weight"].fill_(0.002)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            checkpoint, exported = Path(root) / "checkpoint", Path(root) / "exported"
            checkpoint_sha = session.save(checkpoint)
            manifest_sha = trainer.export_projection(checkpoint, checkpoint_sha, exported)
            model, metadata = trainer.load_inference_projection(exported, manifest_sha)
            self.assertEqual({path.name for path in exported.iterdir()}, {"manifest.json", "adapter.json"})
            for key, value in session.best_state.items():
                self.assertTrue(torch.equal(model.state_dict()[key], value), key)
            self.assertEqual(metadata["manifest"]["data_kind"], "fixture")
            artifact = json.loads((exported / "adapter.json").read_text())
            self.assertEqual(set(artifact["weights"]), {"up.weight", "down.weight"})
            self.assertFalse({"optimizer", "python_rng", "sampler", "rows", "heldout"} & set(artifact))
            artifact["weights"]["up.weight"][0][0] += 1
            (exported / "adapter.json").write_bytes(trainer.canonical(artifact))
            with self.assertRaisesRegex(ValueError, "tensor hash"):
                trainer.load_inference_projection(exported, manifest_sha)

    def test_small_mechanics_checkpoint_cannot_enter_production_export(self):
        session = fixture_session()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            checkpoint, exported = Path(root) / "checkpoint", Path(root) / "exported"
            digest = session.save(checkpoint)
            with self.assertRaisesRegex(ValueError, "inference shape mismatch"):
                trainer.export_projection(checkpoint, digest, exported)
            self.assertFalse(exported.exists())

    def test_public_inference_rejects_dimension_and_encoder_profile_drift(self):
        def write_artifact(root, dimension, encoder):
            artifact = {"schema_version": trainer.VERSION, "dimension": dimension,
                        "rank": trainer.PROTOCOL["rank"], "selected_step": 0, "encoder": encoder,
                        "weights": {"down.weight": [[0.0] * dimension for _ in range(16)],
                                    "up.weight": [[0.0] * 16 for _ in range(dimension)]}}
            raw = trainer.canonical(artifact) + b"\n"
            (root / "adapter.json").write_bytes(raw)
            manifest = {"schema_version": trainer.VERSION, "data_kind": "fixture",
                        "files": {"adapter.json": {"sha256": trainer.sha(raw), "bytes": len(raw)}}}
            encoded = trainer.canonical(manifest) + b"\n"
            (root / "manifest.json").write_bytes(encoded)
            return trainer.sha(encoded)
        approved = {**trainer.ENCODER, "profile_sha256": trainer.APPROVED_PROFILE_SHA256}
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            digest = write_artifact(root, 24, approved)
            with self.assertRaisesRegex(ValueError, "inference shape mismatch"):
                trainer.load_inference_projection(root, digest)
            for field, value in (("profile_sha256", "a" * 64), ("dimension", 24),
                                 ("max_tokens", 1024), ("normalize", 1),
                                 ("query_prefix", "different prefix"), ("revision", "0" * 40)):
                with self.subTest(field=field):
                    digest = write_artifact(root, 768, {**approved, field: value})
                    with self.assertRaisesRegex(ValueError, "unsupported inference encoder"):
                        trainer.load_inference_projection(root, digest)

    def test_source_targets_and_pseudo_negatives_stay_in_repository_and_split(self):
        rows, vectors = [], {}
        for repository in ("fixture/one", "fixture/two"):
            for index in range(2):
                name = trainer.sha(repository + str(index))
                rows.append({"example_id": name, "split": "train", "repository": repository,
                             "query_sha256": trainer.sha(name), "source_commit": "0" * 40})
                vector = torch.zeros(24)
                vector[index] = 1
                vectors[name] = (vector, vector)
        groups = trainer.source_groups_for(rows, vectors)
        repositories = {row["example_id"]: row["repository"] for row in rows}
        for group in groups:
            self.assertEqual(sum(row["relevance"] for row in group["rows"]), 1)
            self.assertEqual({repositories[row["example_id"]] for row in group["rows"]},
                             {repositories[group["key"][0]]})
        rows[0]["split"] = "holdout"
        with self.assertRaisesRegex(ValueError, "held-out"):
            trainer.source_groups_for(rows, vectors)


class AdmissionTests(unittest.TestCase):
    def test_original_empty_gate_and_forged_ready_manifest_stay_closed(self):
        from scripts import training_bundle013 as prep
        MAIN = Path(prep.__file__).resolve().parents[1]
        inventory = json.loads((MAIN / "evidence/evaluation013/training/inventory.empty.json").read_text())
        audit = (MAIN / "evidence/evaluation013/data-audit.json").read_bytes()
        frozen, _, _ = prep.freeze(inventory, audit)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            paths = {key: Path(root) / (key + ".json") for key in ("archive", "receipt", "inventory", "frozen", "audit")}
            contents = {"archive": b"FIXTURE: no training data", "receipt": trainer.canonical({}),
                        "inventory": trainer.canonical(inventory), "frozen": trainer.canonical(frozen), "audit": audit}
            for key, value in contents.items():
                paths[key].write_bytes(value)
            expected = {key: trainer.sha(value) for key, value in contents.items()}
            with self.assertRaisesRegex(ValueError, "not ready"):
                trainer.load_reviewed_bundle(**paths, expected_hashes=expected)
            frozen["training_data_ready"] = True
            paths["frozen"].write_bytes(trainer.canonical(frozen))
            expected["frozen"] = trainer.sha(paths["frozen"].read_bytes())
            with self.assertRaisesRegex(ValueError, "drift"):
                trainer.load_reviewed_bundle(**paths, expected_hashes=expected)
            expected["audit"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "trusted input hash"):
                trainer.load_reviewed_bundle(**paths, expected_hashes=expected)

    def cache_fixture(self):
        row = {"example_id": "e" * 64, "query": "FIXTURE query", "code": "FIXTURE code", "split": "train"}
        bundle = trainer.ReviewedBundle({"train": [row], "development": []},
                                       {"data_kind": "source-only-docstring-retrieval-pilot", "frozen_sha256": "f" * 64})
        vector = [1.0] + [0.0] * 767
        cache = {"schema_version": trainer.CACHE_VERSION, "frozen_sha256": "f" * 64,
                 "encoder": {**trainer.ENCODER, "profile_sha256": trainer.APPROVED_PROFILE_SHA256},
                 "rows": [{"example_id": row["example_id"], "query_sha256": trainer.sha(row["query"]),
                           "code_sha256": trainer.sha(row["code"]), "query": vector, "code": vector}]}
        return bundle, cache

    def test_embedding_exact_coverage_hash_and_frozen_identity(self):
        bundle, cache = self.cache_fixture()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            path = Path(root) / "fixture-cache.json"
            def load():
                path.write_bytes(trainer.canonical(cache))
                return trainer.load_embedding_cache(path, trainer.sha(path.read_bytes()), bundle)
            admitted = load()
            self.assertEqual(admitted.dimension, 768)
            cache["rows"][0]["code_sha256"] = "c" * 64
            with self.assertRaisesRegex(ValueError, "exact model input"):
                load()
            cache["rows"][0]["code_sha256"] = trainer.sha("FIXTURE code")
            cache["rows"].append(copy.deepcopy(cache["rows"][0]))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load()
            cache["rows"] = []
            with self.assertRaisesRegex(ValueError, "exactly exported"):
                load()
            cache["frozen_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "frozen identity"):
                load()

    def test_cache_requires_exact_approved_profile_hash(self):
        bundle, cache = self.cache_fixture()
        cache["encoder"]["profile_sha256"] = "a" * 64
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            path = Path(root) / "cache.json"
            path.write_bytes(trainer.canonical(cache))
            with self.assertRaisesRegex(ValueError, "unsupported frozen encoder"):
                trainer.load_embedding_cache(path, trainer.sha(path.read_bytes()), bundle)

    def test_cache_boolean_nonfinite_unnormalized_and_wrong_encoder_rejected(self):
        for value in (True, 10**100, 0):
            bundle, cache = self.cache_fixture()
            cache["rows"][0]["query"][0] = value
            with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
                path = Path(root) / "cache.json"
                path.write_bytes(trainer.canonical(cache))
                with self.assertRaises((ValueError, OverflowError)):
                    trainer.load_embedding_cache(path, trainer.sha(path.read_bytes()), bundle)
        bundle, cache = self.cache_fixture()
        cache["encoder"]["revision"] = "0" * 40
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            path = Path(root) / "cache.json"
            path.write_bytes(trainer.canonical(cache))
            with self.assertRaisesRegex(ValueError, "unsupported frozen encoder"):
                trainer.load_embedding_cache(path, trainer.sha(path.read_bytes()), bundle)


class SeparateEvaluatorTests(unittest.TestCase):
    def evaluator(self):
        if importlib.util.find_spec("scripts.evaluate_source014"):
            from scripts import evaluate_source014
        else:
            import evaluate_source014
        return evaluate_source014

    def test_fixture_ranks_paired_metrics_and_intervals_are_deterministic(self):
        evaluator = self.evaluator()
        rows, vectors = [], {}
        for index in range(3):
            name = f"{index:064x}"
            rows.append({"example_id": name, "repository": "fixture/evaluator"})
            vectors[name] = (torch.eye(3)[index], torch.eye(3)[(index + 1) % 3])
        report = evaluator.score_holdout(rows, vectors, torch.nn.Identity())
        self.assertEqual([row["base"]["rank"] for row in report["paired"]], [2, 2, 3])
        self.assertEqual(report["summary"]["base"]["recall@1"], 0)
        self.assertEqual(report["summary"]["base"]["recall@5"], 1)
        self.assertEqual(set(report["summary"]["delta"].values()), {0})
        self.assertEqual(report["uncertainty"], evaluator.paired_intervals(report["paired"]))
        self.assertTrue(all(value == {"lower": 0, "upper": 0}
                            for value in report["uncertainty"]["delta_intervals"].values()))

    def test_holdout_cache_exact_target_hashes_and_encoder_profile(self):
        evaluator = self.evaluator()
        bundle, cache = AdmissionTests().cache_fixture()
        row = bundle.rows["train"][0]
        rows = [{**row, "query_sha256": trainer.sha(row["query"]), "code_sha256": trainer.sha(row["code"])}]
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            path = Path(root) / "fixture-heldout-cache.json"
            def load():
                path.write_bytes(trainer.canonical(cache))
                return evaluator.load_holdout_cache(path, trainer.sha(path.read_bytes()), rows,
                                                     bundle.identity, cache["encoder"])
            self.assertEqual(set(load()), {row["example_id"]})
            cache["rows"][0]["query_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "text hash"):
                load()
            cache["rows"][0]["query_sha256"] = trainer.sha(row["query"])
            path.write_bytes(trainer.canonical(cache))
            other_encoder = {**cache["encoder"], "profile_sha256": "0" * 64}
            with self.assertRaisesRegex(ValueError, "encoder differs"):
                evaluator.load_holdout_cache(path, trainer.sha(path.read_bytes()), rows,
                                             bundle.identity, other_encoder)


if __name__ == "__main__":
    unittest.main(verbosity=2)
