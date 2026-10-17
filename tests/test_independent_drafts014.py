"""Fixture-only independent-draft accounting and recovery checks."""
import copy
import json
import unittest

from scripts.repair014.independent_drafts014 import IndependentDraftWorker014, ReportedTokenBudget012


SOURCE = {"path": "src/_pytest/example.py", "reference": {"excerpt_id": "a" * 64}, "text": "1: old\n"}
HANDLE = "S" + "a" * 12
BUDGETS = {"max_calls": 10, "max_patches": 4, "max_checks": 4, "seconds": 900}


class Repository:
    def __init__(self):
        self.record = {"id": "job", "tenant_id": "study010", "steps": [], "integrity": {"verified": True},
            "model_calls": 0, "patch_count": 0, "check_count": 0, "outcome": None}

    def read(self, *args):
        return copy.deepcopy(self.record)

    def remaining(self, job):
        return 900

    def begin(self, job, kind, name, request):
        pending = [s for s in self.record["steps"] if s["state"] != "captured"]
        if pending:
            prior = pending[-1]
            if prior["kind"] == "model":
                raise RuntimeError("Unknown dispatch cannot repeat")
            if (prior["kind"], prior["name"], prior["request"]["body"]) == (kind, name, request):
                return prior["seq"]
            raise RuntimeError("Pending fixture step mismatch")
        if kind == "model":
            self.record["model_calls"] += 1
            assert self.record["model_calls"] <= 10
        if name == "run_checks":
            self.record["check_count"] += 1
            assert self.record["check_count"] <= 4
        seq = len(self.record["steps"]) + 1
        self.record["steps"].append({"seq": seq, "kind": kind, "name": name, "request": {"body": copy.deepcopy(request)}, "result": None, "state": "pending"})
        return seq

    def capture(self, job, seq, result):
        step = self.record["steps"][seq - 1]
        if step["name"] == "propose_patch" and "error" not in result:
            self.record["patch_count"] += 1
            assert self.record["patch_count"] <= 4
        step.update(state="captured", result={"body": copy.deepcopy(result)})

    def finish(self, job, outcome, summary):
        self.record.update(outcome=outcome, summary=summary)
        return self.read()


class Provider:
    def __init__(self, patches=None, unknown=False, token_stop=None):
        self.prepared, self.calls = [], 0
        self.patches = patches or [f"candidate-{n}" for n in range(10)]
        self.unknown, self.token_stop = unknown, token_stop

    def prepare(self, case, configuration, observations, budgets):
        if self.token_stop is not None and len(self.prepared) >= self.token_stop:
            raise ReportedTokenBudget012("Fixture captured token admission exhausted")
        self.prepared.append(copy.deepcopy((configuration, observations, budgets)))
        return {"index": len(self.prepared) - 1}, {"allowed_actions": ["propose_patch", "final_result"],
            "selection": {"latest_verification": None, "current_candidate": None, "recent_tools": []},
            "source_catalog": [copy.deepcopy(SOURCE)], "reference_bindings": {HANDLE: {"excerpt_id": "a" * 64}}}

    def __call__(self, request, seconds):
        self.calls += 1
        if self.unknown:
            raise RuntimeError("Fixture transport interrupted after dispatch intent")
        action = {"action": "propose_patch", "edits": [{"source_id": HANDLE, "start_line": 1, "end_line": 1, "new": self.patches[request["index"]]}]}
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 3}, "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(action)}}]}


class Workspace:
    case = {"id": "case"}
    def __init__(self, passes=None):
        self.current, self.passes, self.proposals, self.restored, self.checks_at_patch = None, passes, [], [], []

    def restore_reference(self, source):
        if source != SOURCE:
            raise ValueError("Changed captured source")
        self.restored.append(copy.deepcopy(source))

    def propose_line_edits(self, edits, references):
        assert references == {HANDLE: {"excerpt_id": "a" * 64}}
        assert self.restored
        patch = edits[0]["new"]
        if patch == "INVALID":
            raise ValueError("Fixture malformed source replacement")
        self.current = patch
        return {"patch": patch}

    def reset(self):
        self.current = None

    def propose(self, patch):
        self.current = patch
        self.proposals.append(patch)

    def checks(self, seconds):
        self.checks_at_patch.append(self.current)
        return {"passed": self.current == self.passes, "environment_error": False}


class Worker(IndependentDraftWorker014):
    def _state(self, job, workspace):
        record = self._record014(job)
        self.provider.captured_usage012 = [s["result"]["body"].get("usage") for s in record["steps"] if s["kind"] == "model" and s["state"] == "captured"]
        history = [{"action": s["name"], "result": s["result"]["body"]} for s in record["steps"] if s["kind"] == "tool" and s["state"] == "captured"]
        return record, [{"action": "initial_source", "result": copy.deepcopy(SOURCE)}, *history], "", None, False


class DraftTests(unittest.TestCase):
    def run_fixture(self, provider=None, workspace=None, worker=Worker):
        repository, provider, workspace = Repository(), provider or Provider(), workspace or Workspace()
        instance = worker(repository, provider)
        job = {"id": "job", "tenant_id": "study010", "configuration": "loop-v8", "config_snapshot": {"budgets": BUDGETS}}
        result = instance._run(job, workspace)
        return result, repository, provider, workspace, instance, job

    def test_ten_fresh_contexts_select_first_four_valid_before_any_checks(self):
        provider = Provider(["INVALID", "INVALID", *[f"candidate-{n}" for n in range(8)]])
        result, repo, provider, workspace, _, _ = self.run_fixture(provider)
        self.assertEqual((result["model_calls"], result["patch_count"], result["check_count"]), (10, 4, 4))
        self.assertEqual(workspace.checks_at_patch, [f"candidate-{n}" for n in range(4)])
        for configuration, observations, budgets in provider.prepared:
            self.assertEqual(configuration, "baseline-v8")
            self.assertEqual(observations, [{"action": "initial_source", "result": SOURCE}])
            self.assertEqual(budgets, {"calls_remaining": 1, "patches_remaining": 1, "checks_remaining": 1})
        selection = next(s for s in repo.record["steps"] if s["name"] == "draft_selection014")
        self.assertTrue(all(s["seq"] < selection["seq"] for s in repo.record["steps"] if s["kind"] == "model"))
        self.assertTrue(all(s["seq"] > selection["seq"] for s in repo.record["steps"] if s["name"] == "run_checks"))

    def test_duplicate_candidates_reuse_one_captured_check(self):
        result, _, _, workspace, _, _ = self.run_fixture(Provider(["same"] * 10))
        self.assertEqual((result["patch_count"], result["check_count"]), (4, 1))
        self.assertEqual(workspace.checks_at_patch, ["same"])

    def test_recovery_refuses_result_based_candidate_reselection(self):
        _, repository, _, workspace, instance, job = self.run_fixture()
        selection = next(s for s in repository.record["steps"] if s["name"] == "draft_selection014")
        selection["result"]["body"]["selected"].reverse()
        with self.assertRaisesRegex(ValueError, "first four valid candidates"):
            instance._check014(job, workspace)
        self.assertEqual(repository.record["check_count"], 4)

    def test_success_stops_checks_after_frozen_selection_and_active_patch_matches(self):
        result, repo, _, workspace, _, _ = self.run_fixture(workspace=Workspace(passes="candidate-0"))
        self.assertEqual(result["outcome"], "verified_repair")
        self.assertEqual((result["model_calls"], result["patch_count"], result["check_count"]), (10, 1, 1))
        self.assertEqual(workspace.current, "candidate-0")
        selected = next(s for s in repo.record["steps"] if s["name"] == "draft_selection014")
        self.assertEqual(len(selected["result"]["body"]["selected"]), 4)

    def test_uncertain_dispatch_is_not_resent_on_recovery(self):
        result, _, provider, workspace, instance, job = self.run_fixture(Provider(unknown=True))
        self.assertEqual(result["outcome"], "unknown_dispatch")
        result = instance._run(job, workspace)
        self.assertEqual(result["outcome"], "unknown_dispatch")
        self.assertEqual(provider.calls, 1)

    def test_recovery_uses_captured_model_and_restores_its_context_authority(self):
        class InterruptedWorker(Worker):
            interrupted = False
            def _draft014(self, job, workspace, model):
                if not self.interrupted:
                    self.interrupted = True
                    raise KeyboardInterrupt("Fixture process stop after captured model")
                return super()._draft014(job, workspace, model)
        repository, provider, workspace = Repository(), Provider(), Workspace()
        instance = InterruptedWorker(repository, provider)
        job = {"id": "job", "tenant_id": "study010", "configuration": "loop-v8", "config_snapshot": {"budgets": BUDGETS}}
        with self.assertRaises(KeyboardInterrupt):
            instance._run(job, workspace)
        self.assertEqual(provider.calls, 1)
        instance._run(job, workspace)
        self.assertEqual(provider.calls, 10)
        self.assertEqual(len(workspace.restored), 10)

    def test_token_admission_stops_before_new_dispatch_and_records_shortfall(self):
        result, repo, provider, _, _, _ = self.run_fixture(Provider(token_stop=3))
        self.assertEqual((provider.calls, result["model_calls"], result["patch_count"]), (3, 3, 3))
        self.assertTrue(any(s["name"] == "draft_token_stop014" for s in repo.record["steps"]))


if __name__ == "__main__":
    unittest.main()
