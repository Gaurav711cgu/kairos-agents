"""Exact model classification; arithmetic stays in a deterministic tool."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

import httpx

from kairos_api.grading import grade_decision
from kairos_api.scenarios import get_scenario


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class BlobStore:
    """Local content-addressed objects; atomic rename + fsync, not WORM storage."""
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("KAIROS_BLOB_DIR", ".runtime/blobs")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, value):
        encoded = canonical(value).encode()
        key = hashlib.sha256(encoded).hexdigest()
        target = self.root / key
        fd, name = tempfile.mkstemp(dir=self.root, prefix=".pending-")
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, target)
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return {"sha256": key, "bytes": len(encoded), "storage": "local-content-addressed-fsync"}

    def get(self, key):
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid object digest")
        data = (self.root / key).read_bytes()
        if hashlib.sha256(data).hexdigest() != key:
            raise ValueError("Object digest mismatch")
        return json.loads(data)


def model_request(blocks):
    context = "\n\n".join(f"[{b['id']}] {b['content']}" for b in blocks if b["included"])
    return {"messages": [
        {"role": "system", "content": "You classify a synthetic order-support review. Never execute payment. Reply with exactly one JSON object and no markdown. Keys: disposition (refund, zero, or abstain), reason (nonempty string), evidence_ids (nonempty array of bracketed context IDs without brackets). Choose refund only if verified delay >=30 minutes and no prior compensation exception. Choose zero for prior compensation or delay <30. Choose abstain if amount or delay evidence missing. Do not calculate any money; a deterministic tool calculates cents."},
        {"role": "user", "content": context}], "max_tokens": 128, "temperature": 0,
        "contract_version": "classification-v1"}


def call_model(request):
    endpoint = os.environ.get("KAIROS_MODEL_ENDPOINT", "http://127.0.0.1:8120/generate")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Model endpoint must be a configured HTTP URL without credentials/query")
    # Only the server-controlled configuration selects a provider; no user URL can reach this function.
    with httpx.Client(timeout=httpx.Timeout(100, connect=5), trust_env=False) as client:
        response = client.post(endpoint, json=request)
        response.raise_for_status()
        if len(response.content) > 1_000_000:
            raise ValueError("Provider response exceeds capture budget")
        value = response.json()
    if not isinstance(value, dict) or not isinstance(value.get("raw_response"), str):
        raise ValueError("Provider contract requires exact raw_response")
    return value


def classify_and_grade(scenario_id, blocks, response):
    raw = response["raw_response"]
    try:
        # No fence stripping, repairs or permissive extraction. Every failure is preserved.
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or set(parsed) != {"disposition", "reason", "evidence_ids"}:
            raise ValueError("Exactly disposition, reason and evidence_ids are required")
        if parsed["disposition"] not in {"refund", "zero", "abstain"}:
            raise ValueError("Unknown disposition")
        if not isinstance(parsed["reason"], str) or not parsed["reason"].strip():
            raise ValueError("Nonempty reason required")
        ids = parsed["evidence_ids"]
        allowed = {b["id"] for b in blocks if b["included"]}
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in allowed for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("Evidence must cite unique included context IDs")
        scenario = get_scenario(scenario_id)
        if parsed["disposition"] == "abstain":
            cents = None
        elif parsed["disposition"] == "zero":
            cents = 0
        elif type(scenario["order_total_cents"]) is int:
            cents = scenario["order_total_cents"] // 5
        else:
            raise ValueError("Arithmetic tool refuses absent verified amount")
        decision = {"refund_cents": cents, "reason": parsed["reason"], "evidence_ids": ids}
        return {"decision": decision, "grade": grade_decision(scenario_id, decision),
                "classification": parsed, "parse_error": None}
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        return {"decision": None, "grade": {"passed": False, "checks": {"strict_model_schema": False}},
                "classification": None, "parse_error": str(error)}
