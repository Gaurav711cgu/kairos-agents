"""Transport-budget checks run before downstream parsing or authorization."""
import asyncio
import json

from fastapi.testclient import TestClient
import pytest

from kairos_api.app import create_app
from kairos_api.http_boundary import BoundedBodyMiddleware


def exercise(chunks, headers=(), method="POST", disconnected=False):
    sent, seen = [], []
    messages = [{"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1 or disconnected}
                for i, chunk in enumerate(chunks)]
    if disconnected:
        messages.append({"type": "http.disconnect"})
    receives = 0

    async def receive():
        nonlocal receives
        receives += 1
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def downstream(scope, receive, send):
        message = await receive()
        seen.append(message["body"])
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    asyncio.run(BoundedBodyMiddleware(downstream)({"type": "http", "method": method, "headers": list(headers)}, receive, send))
    status = next((m["status"] for m in sent if m["type"] == "http.response.start"), None)
    return status, seen, receives, sent


@pytest.mark.parametrize("headers", [(), ((b"content-length", b"1"),), ((b"transfer-encoding", b"chunked"),)])
def test_observed_chunked_bytes_cannot_bypass_budget(headers):
    status, seen, receives, sent = exercise([b"x" * 16000, b"x" * 16000, b"x" * 769, b"must-not-be-read"], headers)
    assert status == 413 and not seen and receives == 3
    assert json.loads(sent[-1]["body"])["detail"] == "Request body exceeds 32768 bytes."


def test_declared_oversize_rejects_without_reading_body():
    status, seen, receives, _ = exercise([b"unread"], [(b"content-length", b"32769")])
    assert status == 413 and not seen and receives == 0


@pytest.mark.parametrize("lengths", [[b"-1"], [b"invalid"], [b""], [b"1", b"1"]])
def test_invalid_or_duplicate_declared_length_fails_closed(lengths):
    status, seen, receives, _ = exercise([b"unread"], [(b"content-length", length) for length in lengths])
    assert status == 400 and not seen and receives == 0


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_exact_budget_bytes_replayed_once_for_all_mutating_methods(method):
    chunks = [b"x" * 10000, b"x" * 22768]
    status, seen, receives, _ = exercise(chunks, method=method)
    assert status == 204 and seen == [b"".join(chunks)] and receives == 2


def test_budget_counts_utf8_bytes_not_characters():
    status, seen, _, _ = exercise([("😀" * 8193).encode()])
    assert status == 413 and not seen


def test_client_disconnect_never_reaches_downstream():
    status, seen, _, _ = exercise([b"partial"], disconnected=True)
    assert status is None and not seen


def test_installed_boundary_runs_before_database_authentication_and_json_parse():
    # Deliberately do not start lifespan: any dependency access would fail. The
    # invalid oversized JSON must be rejected at transport boundary instead.
    client = TestClient(create_app())
    response = client.post("/api/jobs", content=b"{" + b"x" * 32768, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_nonmutating_request_is_not_buffered():
    status, seen, receives, _ = exercise([b"x" * 32769], method="GET")
    assert status == 204 and len(seen[0]) == 32769 and receives == 1
