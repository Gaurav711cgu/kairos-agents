"""Independent original-context candidates on the existing durable v8 worker.

Only this optional subclass changes behavior. Existing configurations, workers,
transport, repository counters and verification remain unchanged.
"""
from __future__ import annotations

import copy

from pydantic import ValidationError

from kairos_api.investigations.contracts import ActionV7
from kairos_api.model_runtime import digest, strict_json
from scripts.repair012.retrieval_loop012 import (
    NoSourceEvidence012, ReportedTokenBudget012, UsageAwareWorker012,
)

VERSION = "independent-original-drafts014-v1"
POLICY = "first-four-structurally-valid-before-any-check"


def captured(record, name=None, kind=None):
    return [s for s in record["steps"] if s["state"] == "captured"
        and (name is None or s["name"] == name) and (kind is None or s["kind"] == kind)]


class IndependentDraftWorker014(UsageAwareWorker012):
    """Ten fresh original-only contexts; first four valid candidates are frozen."""

    def _record014(self, job):
        record = self.repository.read(str(job["id"]), job["tenant_id"])
        if not record["integrity"]["verified"]:
            raise ValueError("Independent drafts require verified durable integrity")
        return record

    def _context014(self, record, model):
        contexts = [s for s in captured(record, "selection", "context") if s["seq"] < model["seq"]]
        if not contexts:
            raise ValueError("Captured draft has no original dispatch authority")
        step = max(contexts, key=lambda s: s["seq"])
        if step["request"]["body"].get("strategy014") != VERSION:
            raise ValueError("Draft dispatch context belongs to a different strategy")
        context = step["result"]["body"]
        for source in context.get("source_catalog", []):
            self._workspace014.restore_reference(source)
        if set(context.get("allowed_actions", [])) - {"propose_patch", "final_result"}:
            raise ValueError("Fresh draft context grants an adaptive tool")
        selection = context.get("selection", {})
        if any(selection.get(key) for key in ("latest_verification", "current_candidate", "rejected_proposal", "latest_error", "recent_tools")):
            raise ValueError("Fresh draft context contains another candidate or check outcome")
        return context

    def _draft014(self, job, workspace, model):
        record = self._record014(job)
        context = self._context014(record, model)
        request = {"model_seq": model["seq"], "selection_policy": POLICY}
        seq = self.repository.begin(job, "tool", "draft_candidate014", request)
        try:
            choice = model["result"]["body"]["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError("Independent draft response was truncated")
            action = ActionV7.validate_python(strict_json(choice["message"]["content"])).model_dump()
            if action["action"] != "propose_patch" or "propose_patch" not in context.get("allowed_actions", []):
                raise ValueError("Independent draft did not propose an authorized patch")
            result = workspace.propose_line_edits(action["edits"], context.get("reference_bindings", {}))
            result.update(structurally_valid=True, model_seq=model["seq"])
        except (ValueError, ValidationError, KeyError, IndexError, TypeError, OSError) as error:
            result = {"error": str(error)[:1000], "structurally_valid": False, "model_seq": model["seq"]}
        finally:
            workspace.reset()
        # This name intentionally does not consume a registered applied-patch
        # counter. Only the frozen selected propose_patch events do that.
        self.repository.capture(job, seq, result)

    def _generate014(self, job, workspace):
        while True:
            if self.repository.remaining(job) <= 0:
                raise TimeoutError("Independent draft generation deadline exhausted")
            record, observations, _, _, _ = self._state(job, workspace)
            if captured(record, "draft_selection014", "context"):
                return
            if any(s["kind"] == "model" and s["state"] != "captured" for s in record["steps"]):
                self.repository.finish(job, "unknown_dispatch", "Pending independent draft will not be resent")
                return False
            if captured(record, "run_checks", "tool"):
                raise ValueError("Check results exist before the independent draft selection freeze")
            handled = {s["request"]["body"]["model_seq"] for s in captured(record, "draft_candidate014", "tool")}
            unhandled = [s for s in captured(record, kind="model") if s["seq"] not in handled]
            if unhandled:
                self._draft014(job, workspace, unhandled[0])
                continue
            if record["model_calls"] >= 10 or captured(record, "draft_token_stop014", "context"):
                break
            initial = [o for o in observations if o["action"] == "initial_source" and "reference" in o["result"]]
            if not initial:
                raise NoSourceEvidence012("No original AST source was captured; no entry-file fallback")
            # No candidate, rejection, read/search result or verifier observation
            # is supplied to a later draft. Transport dispatch IDs stay unique.
            try:
                request, context = self.provider.prepare(workspace.case, "baseline-v8", copy.deepcopy(initial),
                    {"calls_remaining": 1, "patches_remaining": 1, "checks_remaining": 1})
            except ReportedTokenBudget012 as error:
                self._record(job, "context", "draft_token_stop014", {}, {"reason": str(error)})
                break
            self._record(job, "context", "selection", {"configuration": "baseline-v8",
                "strategy014": VERSION, "draft_index": record["model_calls"]}, context)
            seq = self.repository.begin(job, "model", "dispatch", request)
            try:
                response = self.provider(request, float(self.repository.remaining(job)))
            except Exception as error:
                self.repository.finish(job, "unknown_dispatch", type(error).__name__ + ": " + str(error)[:300])
                return False
            self.repository.capture(job, seq, response)
        record = self._record014(job)
        valid = [s for s in captured(record, "draft_candidate014", "tool") if s["result"]["body"].get("structurally_valid")]
        self._record(job, "context", "draft_selection014", {"policy": POLICY}, {
            "selected": [{"draft_seq": s["seq"], "patch_digest": digest(s["result"]["body"]["patch"])} for s in valid[:4]],
            "captured_models": record["model_calls"], "valid_candidates": len(valid), "checks_before_selection": 0})

    def _check014(self, job, workspace):
        record = self._record014(job)
        selection = captured(record, "draft_selection014", "context")[-1]
        selected = selection["result"]["body"]["selected"]
        valid = [s for s in captured(record, "draft_candidate014", "tool")
            if s["seq"] < selection["seq"] and s["result"]["body"].get("structurally_valid")]
        expected = [{"draft_seq": s["seq"], "patch_digest": digest(s["result"]["body"]["patch"])} for s in valid[:4]]
        if (selection["request"]["body"].get("policy") != POLICY or selected != expected
                or any(s["seq"] < selection["seq"] for s in captured(record, "run_checks", "tool"))):
            raise ValueError("Independent selection differs from first four valid candidates before checks")
        if any(s["kind"] == "model" and s["seq"] > selection["seq"] for s in record["steps"]):
            raise ValueError("Model dispatch occurred after the independent selection freeze")
        by_seq = {s["seq"]: s for s in captured(record, "draft_candidate014", "tool")}
        checked = []
        for chosen in selected:
            candidate = by_seq[chosen["draft_seq"]]
            patch = candidate["result"]["body"]["patch"]
            if digest(patch) != chosen["patch_digest"]:
                raise ValueError("Frozen independent candidate digest changed")
            workspace.propose(patch)
            record = self._record014(job)
            proposals = [s for s in captured(record, "propose_patch", "tool") if s["request"]["body"].get("draft_seq") == candidate["seq"]]
            if not proposals:
                self._record(job, "tool", "propose_patch", {"draft_seq": candidate["seq"]},
                    {"patch": patch, "draft_seq": candidate["seq"], "construction": VERSION})
            checks = [s for s in captured(record, "run_checks", "tool") if s["result"]["body"].get("patch_digest") == chosen["patch_digest"]]
            if checks:
                verification = checks[-1]["result"]["body"]
            else:
                verification = self._verify(job, workspace, patch, candidate["seq"])
            checked.append({**chosen, "verification": verification, "reused_check": bool(checks)})
            if verification.get("passed") or verification.get("environment_error"):
                break
        winner = checked[-1] if checked else None
        if winner and winner["verification"].get("environment_error"):
            outcome = "environment_failure"
        elif winner and winner["verification"].get("passed"):
            outcome = "verified_repair"
        else:
            outcome = "failed_checks" if checked else "invalid_patch"
        self._record(job, "context", "draft_outcome014", {"policy": POLICY}, {
            "checked": checked, "selected_patch_digest": winner["patch_digest"] if winner else None,
            "selected_candidates": len(selected), "outcome": outcome})
        return self.repository.finish(job, outcome,
            "Independent original-only drafts frozen before checking first four structurally valid candidates")

    def _run(self, job, workspace):
        if (job["configuration"] != "loop-v8" or job["config_snapshot"]["budgets"] != {
                "max_calls": 10, "max_patches": 4, "max_checks": 4, "seconds": 900}):
            raise ValueError("Independent drafts require the unchanged physical loop-v8 budgets")
        self._workspace014 = workspace
        try:
            if self._generate014(job, workspace) is False:
                return self.repository.read(str(job["id"]), job["tenant_id"])
            return self._check014(job, workspace)
        except NoSourceEvidence012 as error:
            return self.repository.finish(job, "no_patch", str(error))
