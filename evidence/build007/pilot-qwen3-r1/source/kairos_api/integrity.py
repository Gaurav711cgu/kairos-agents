"""Local event-chain consistency. This is not administrator-resistant evidence."""
import hashlib
import json

GENESIS_HASH = "0" * 64
INTEGRITY_SCOPE = "Local event hash consistency only; database administrators can rewrite history."


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def request_digest(value: dict) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def hash_event(event: dict) -> str:
    signed = {key: event[key] for key in
              ("run_id", "seq", "event_type", "title", "summary", "created_at", "payload", "prev_hash")}
    return hashlib.sha256(canonical_json(signed).encode()).hexdigest()


def verify_events(events: list[dict], expected_count: int, expected_head: str, expected_run_id: str | None = None) -> bool:
    if not events or len(events) != expected_count:
        return False
    previous = GENESIS_HASH
    run_id = expected_run_id or events[0].get("run_id")
    for expected_seq, event in enumerate(events, 1):
        if event.get("seq") != expected_seq or event.get("prev_hash") != previous or event.get("run_id") != run_id:
            return False
        try:
            if event["event_hash"] != hash_event(event):
                return False
        except (KeyError, ValueError, TypeError):
            return False
        previous = event["event_hash"]
    return previous == expected_head
