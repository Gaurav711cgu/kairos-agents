"""Bound mutating HTTP bodies before JSON parsing and authentication dependencies."""
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BoundedBodyMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = 32768):
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("Body limit must be a positive integer")
        self.app = app
        self.max_bytes = max_bytes

    @staticmethod
    async def reject(send: Send, status: int, detail: str):
        body = json.dumps({"detail": detail}, separators=(",", ":")).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, send)
        lengths = [value.strip() for name, value in scope.get("headers", []) if name.lower() == b"content-length"]
        if len(lengths) > 1 or (lengths and not lengths[0].isdigit()):
            return await self.reject(send, 400, "Invalid request length.")
        if lengths and (len(lengths[0]) > 12 or int(lengths[0]) > self.max_bytes):
            return await self.reject(send, 413, "Request body exceeds 32768 bytes.")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            # Enforce the observed byte count even when Content-Length is absent or false.
            if len(body) + len(chunk) > self.max_bytes:
                return await self.reject(send, 413, "Request body exceeds 32768 bytes.")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
