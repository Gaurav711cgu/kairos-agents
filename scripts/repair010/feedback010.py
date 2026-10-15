"""Experimental rejection feedback; existing v7 code and budgets are unchanged.

Import with the target checkout on PYTHONPATH. This module neither reads source
files nor obtains reference repairs. All evidence comes from integrity-verified
durable observations captured by the existing worker.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import PurePosixPath
import re

import httpx

from kairos_api.investigations.context_v5 import source_handle
from kairos_api.investigations.model import LocalInvestigator
from kairos_api.investigations.worker import InvestigationWorker
from kairos_api.model_runtime import digest


VERSION = "captured-rejection-feedback-experimental010-v1"
CONTEXT_LIMIT = 4096
OUTPUT_LIMIT = 1024
RESERVE_TOKENS = 32


class FeedbackContextOverflow010(ValueError):
    """Required feedback and existing actionable context cannot fit the profile."""


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _omission(field, value, reason):
    raw = value.encode("utf-8") if isinstance(value, str) else _encoded(value)
    return {"field": field, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "reason": reason}


def observations_from_record010(record, observations):
    """Restore tool requests and their original dispatch authority after recovery.

    The parent worker already checks integrity, restores references, and restores
    an accepted candidate. This function only adds captured data; it executes no
    tool, mutates no candidate and never invents a missing tool request.
    """
    if not record.get("integrity", {}).get("verified"):
        raise ValueError("Feedback requires verified durable record integrity")
    tools = [step for step in record["steps"]
             if step["kind"] == "tool" and step["state"] == "captured"]
    if not tools:
        return copy.deepcopy(observations)
    if len(tools) != len(observations):
        raise ValueError("Durable tool history differs from reconstructed observations")
    restored = []
    for step, observation in zip(tools, observations):
        if step["name"] != observation["action"]:
            raise ValueError("Durable tool order differs from reconstructed observations")
        value = copy.deepcopy(observation)
        value["request"] = copy.deepcopy(step["request"]["body"])
        value["sequence"] = step["seq"]
        if step["name"] == "propose_patch" and "error" in value["result"]:
            model_seq = value["request"].get("model_seq")
            contexts = [item for item in record["steps"]
                        if item["kind"] == "context" and item["state"] == "captured"
                        and isinstance(model_seq, int) and item["seq"] < model_seq
                        and item.get("result")]
            if contexts:
                context = max(contexts, key=lambda item: item["seq"])
                body = context["result"]["body"]
                value["proposal_context"] = {
                    "sequence": context["seq"],
                    "reference_bindings": copy.deepcopy(body.get("reference_bindings", {})),
                    "source_catalog": copy.deepcopy(body.get("source_catalog", [])),
                }
        restored.append(value)
    return restored


def _captured_lines(context, handle):
    """Validate captured handle and excerpt bytes without touching any filesystem."""
    reference = context.get("reference_bindings", {}).get(handle)
    if (not isinstance(handle, str) or not re.fullmatch(r"S[a-f0-9]{12}", handle)
            or not isinstance(reference, dict) or source_handle(reference) != handle):
        raise ValueError("Source handle is absent from the original dispatch context")
    path = reference.get("path", "")
    parts = PurePosixPath(path).parts
    if (not path or PurePosixPath(path).is_absolute() or ".." in parts
            or "\\" in path or any(part in {".git", "tests", "test"} for part in parts)):
        raise ValueError("Captured source path is not an approved source path")
    if not re.fullmatch(r"[a-f0-9]{64}", reference.get("source_digest", "")):
        raise ValueError("Captured source digest is malformed")
    regions = [item for item in context.get("source_catalog", [])
               if item.get("reference") == reference and isinstance(item.get("text"), str)]
    if not regions:
        raise ValueError("Original dispatch source region is missing")
    start, end = reference.get("start_line"), reference.get("end_line")
    if (type(start) is not int or type(end) is not int or not 1 <= start <= end
            or end - start >= 80):
        raise ValueError("Captured source bounds are invalid")
    lines = {}
    for raw in regions[0]["text"].splitlines(keepends=True):
        match = re.fullmatch(r"(\d+): ([\s\S]*)", raw)
        if not match or int(match[1]) in lines:
            raise ValueError("Captured original source numbering is invalid")
        lines[int(match[1])] = match[2]
    if list(lines) != list(range(start, end + 1)):
        raise ValueError("Captured source numbering differs from its bounds")
    excerpt = {key: value for key, value in reference.items() if key != "excerpt_id"}
    if digest({**excerpt, "text": "".join(lines.values())}) != reference.get("excerpt_id"):
        raise ValueError("Captured original source excerpt digest changed")
    return reference, lines


def _indentation(text):
    return text[:len(text) - len(text.lstrip(" \t"))]


def rejection_feedback010(observations, maximum_bytes=6000):
    """Return bounded exact model-authored rejection feedback, never a repair.

    Oversized fields are omitted whole with hashes. Diagnostics describe visible
    syntax/coordinates only. They do not rewrite indentation, ranges or content.
    """
    if maximum_bytes < 512:
        raise ValueError("Feedback byte limit must be at least 512")
    latest = next((item for item in reversed(observations)
                   if item.get("action") == "propose_patch"), None)
    if latest is None or not isinstance(latest.get("result"), dict) or "error" not in latest["result"]:
        return None
    request = latest.get("request")
    feedback = {"version": VERSION, "tool_sequence": latest.get("sequence"),
                "rejection_reason": latest["result"]["error"], "edits": [], "omissions": [],
                "scope": "Exact rejected model replacement and captured original coordinates; no correction performed"}
    if not isinstance(request, dict) or request.get("action") != "propose_patch":
        feedback["request_unavailable"] = True
        return _bound_feedback(feedback, maximum_bytes)
    feedback["model_sequence"] = request.get("model_seq")
    feedback["request_sha256"] = hashlib.sha256(_encoded(request)).hexdigest()
    context = latest.get("proposal_context", {})
    feedback["context_sequence"] = context.get("sequence")
    ranges = []
    for index, edit in enumerate(request.get("edits", [])):
        detail = {"index": index, "source_id": edit.get("source_id"),
                  "start_line": edit.get("start_line"), "end_line": edit.get("end_line"),
                  "replacement": edit.get("new"), "coordinate_valid": False}
        try:
            reference, original = _captured_lines(context, edit.get("source_id"))
            detail["path"] = reference["path"]
            detail["captured_bounds"] = [reference["start_line"], reference["end_line"]]
            start, end = edit.get("start_line"), edit.get("end_line")
            if (type(start) is not int or type(end) is not int
                    or not reference["start_line"] <= start <= end <= reference["end_line"]):
                raise ValueError("Requested inclusive range escapes the captured original excerpt")
            detail["coordinate_valid"] = True
            detail["original_indentation"] = [
                {"line": number, "whitespace": _indentation(original[number])}
                for number in range(start, min(end + 1, start + 8))]
            if end - start + 1 > 8:
                feedback["omissions"].append({"field": f"edits.{index}.original_indentation",
                                              "reason": "Only first eight selected lines described"})
            ranges.append((reference["path"], start, end, index))
        except (KeyError, TypeError, ValueError) as error:
            detail["coordinate_error"] = str(error)
        replacement = edit.get("new")
        if isinstance(replacement, str):
            authored_lines = replacement.splitlines()
            detail["replacement_diagnostics"] = {
                "line_count": len(authored_lines),
                "numbered_line_prefixes": [number for number, line in enumerate(authored_lines, 1)
                                           if re.match(r"^\s*\d+:\s", line)][:8],
                "indentation": [{"line": number, "whitespace": _indentation(line)}
                                for number, line in enumerate(authored_lines[:8], 1)],
                "description": "Whitespace is shown exactly; indentation differences are not proof of an error",
            }
        feedback["edits"].append(detail)
    for left, right in zip(sorted(ranges), sorted(ranges)[1:]):
        if left[0] == right[0] and left[2] >= right[1]:
            feedback.setdefault("overlapping_edit_indices", []).append([left[3], right[3]])
    return _bound_feedback(feedback, maximum_bytes)


def _bound_feedback(feedback, maximum_bytes):
    """Omit complete optional fields, never malformed JSON or partial source."""
    # Replacement text is the core experiment, so keep it before descriptions.
    removable = [(edit, "replacement_diagnostics", f"edits.{edit['index']}.replacement_diagnostics")
                 for edit in feedback["edits"]]
    removable += [(edit, "original_indentation", f"edits.{edit['index']}.original_indentation")
                  for edit in feedback["edits"]]
    removable += [(edit, "replacement", f"edits.{edit['index']}.replacement")
                  for edit in sorted(feedback["edits"],
                                     key=lambda item: len(_encoded(item.get("replacement"))), reverse=True)]
    for owner, key, field in removable:
        if len(_encoded(feedback)) <= maximum_bytes:
            break
        if key in owner:
            feedback["omissions"].append(_omission(field, owner.pop(key),
                                                  "Complete field omitted to satisfy feedback byte budget"))
    if len(_encoded(feedback)) > maximum_bytes:
        raise FeedbackContextOverflow010("Required rejection metadata exceeds the feedback byte budget")
    return feedback


class FeedbackWorker010(InvestigationWorker):
    """Existing durable execution with request-preserving state reconstruction."""

    def _state(self, job, workspace):
        record, observations, patch, verification, invalid = super()._state(job, workspace)
        if job["configuration"].endswith(("-v7", "-v8")):
            observations = observations_from_record010(record, observations)
        return record, observations, patch, verification, invalid


class FeedbackInvestigator010(LocalInvestigator):
    """v7 provider decorator that measures its final chat-template prompt."""

    def __init__(self, maximum_feedback_bytes=6000):
        super().__init__()
        self.maximum_feedback_bytes = maximum_feedback_bytes

    def _measure_messages010(self, messages, generation):
        with httpx.Client(timeout=10, trust_env=False) as client:
            rendered = client.post(self.endpoint + "/apply-template", json={
                "messages": messages, "add_generation_prompt": True,
                "chat_template_kwargs": generation["chat_template_kwargs"]})
            rendered.raise_for_status()
            tokens = client.post(self.endpoint + "/tokenize", json={
                "content": rendered.json()["prompt"], "add_special": True})
            tokens.raise_for_status()
        return len(tokens.json()["tokens"])

    def prepare(self, case, configuration, observations, budgets, generation_snapshot=None):
        if not configuration.endswith(("-v7", "-v8")):
            raise ValueError("Feedback experiment010 only supports the unchanged line-handle action protocol through v7/v8")
        request, context = super().prepare(case, configuration, observations, budgets, generation_snapshot)
        request, context = copy.deepcopy(request), copy.deepcopy(context)
        if request.get("max_tokens") != OUTPUT_LIMIT:
            raise ValueError("Feedback experiment010 requires the 1024-token output profile")
        feedback = rejection_feedback010(observations, self.maximum_feedback_bytes)
        context["experimental_protocol"] = VERSION
        if feedback is None:
            return request, context
        selection = context["selection"]
        selection["rejected_proposal_feedback010"] = feedback
        while True:
            request["messages"][-1]["content"] = json.dumps(selection, ensure_ascii=False)
            count = self._measure_messages010(request["messages"], request)
            if count + OUTPUT_LIMIT + RESERVE_TOKENS <= CONTEXT_LIMIT:
                break
            if selection.get("recent_tools"):
                removed = selection["recent_tools"].pop(0)
                context["omissions"].append(_omission(
                    "recent_tools", removed,
                    "Complete old search result omitted before exact rejection feedback"))
            elif (selection.get("current_candidate") or {}).get("edits"):
                removed = selection["current_candidate"].pop("edits")
                context["omissions"].append(_omission(
                    "current_candidate.edits", removed,
                    "Complete previous candidate body omitted; candidate digest and exact rejection retained"))
            else:
                raise FeedbackContextOverflow010(
                    f"Rejection feedback requires {count} input + {OUTPUT_LIMIT} output + "
                    f"{RESERVE_TOKENS} reserve tokens; limit is {CONTEXT_LIMIT}")
        context.update(rendered_input_tokens=count, output_tokens=OUTPUT_LIMIT,
                       reserve_tokens=RESERVE_TOKENS,
                       context_version="source-line-handles-v7-with-rejection-feedback010")
        context["omissions"].extend(copy.deepcopy(feedback["omissions"]))
        return request, context
