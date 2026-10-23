"""Bounded synchronous MCP stdio client for repository intelligence.

This client supports the negotiated 2025-03-26 protocol on POSIX hosts. It never
retries an uncertain request, discards server stderr rather than exposing it,
and terminates only the child process it owns on transport failure.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import select
import subprocess
import threading
import time
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CODESAGE_ROOT = ROOT.parent / "Codesage"
PROTOCOL_VERSION = "2025-03-26"
MAX_MESSAGE_BYTES = 4 * 1024 * 1024


class CodeSageMCPClient:
    """One serialized request stream with initialization and absolute deadlines."""

    def __init__(self, codesage_root: Optional[Path] = None, timeout: float = 30.0) -> None:
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("MCP timeout must be finite and positive")
        env_root = os.environ.get("CODESAGE_PATH") or os.environ.get("CODESAGE_DIR")
        self.codesage_root = Path(codesage_root or env_root or DEFAULT_CODESAGE_ROOT).resolve()
        self.run_mcp_script = self.codesage_root / "bin" / "run-mcp"
        self.timeout = float(timeout)
        self.process = None
        self._request_counter = 0
        self._buffer = bytearray()
        self._lock = threading.RLock()
        self._initialized = False

    def start(self) -> None:
        with self._lock:
            if self.process is not None and self.process.poll() is None and self._initialized:
                return
            self.close()
            if os.name != "posix":
                raise RuntimeError("This MCP stdio transport requires POSIX pipe polling")
            if not self.run_mcp_script.is_file():
                raise FileNotFoundError(f"CodeSage MCP launcher not found at {self.run_mcp_script}")
            self.process = subprocess.Popen([str(self.run_mcp_script)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0, cwd=self.codesage_root)
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
            deadline = time.monotonic() + self.timeout
            try:
                result = self._exchange("initialize", {"protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {}, "clientInfo": {"name": "kairos-codesage", "version": "2.1.0"}}, deadline)
                if (result.get("protocolVersion") != PROTOCOL_VERSION
                        or not isinstance(result.get("capabilities"), dict)
                        or not isinstance(result["capabilities"].get("tools"), dict)):
                    raise RuntimeError("Incompatible MCP protocol or missing tools capability")
                self._write({"jsonrpc": "2.0", "method": "notifications/initialized"}, deadline)
                self._initialized = True
            except BaseException:
                self.close()
                raise

    def close(self) -> None:
        with self._lock:
            process, self.process = self.process, None
            self._initialized = False
            self._buffer.clear()
            if process is None:
                return
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=0.2)
            finally:
                if process.stdout:
                    process.stdout.close()

    def __enter__(self) -> CodeSageMCPClient:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _write(self, message, deadline):
        raw = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ValueError("MCP request exceeds message bound")
        offset = 0
        while offset < len(raw):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MCP request deadline exceeded")
            _, writable, _ = select.select([], [self.process.stdin], [], remaining)
            if writable:
                try:
                    offset += os.write(self.process.stdin.fileno(), raw[offset:])
                except BlockingIOError:
                    continue

    def _read(self, deadline):
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._buffer[:newline])
                del self._buffer[:newline + 1]
                if len(raw) > MAX_MESSAGE_BYTES:
                    raise RuntimeError("MCP response exceeds message bound")
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
                    raise RuntimeError("Invalid MCP response envelope")
                return value
            if len(self._buffer) > MAX_MESSAGE_BYTES:
                raise RuntimeError("MCP response exceeds message bound")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MCP request deadline exceeded")
            readable, _, _ = select.select([self.process.stdout], [], [], remaining)
            if readable:
                try:
                    data = os.read(self.process.stdout.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not data:
                    raise RuntimeError("MCP server closed its output stream")
                self._buffer.extend(data)

    def _exchange(self, method, params, deadline):
        self._request_counter += 1
        request_id = self._request_counter
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, deadline)
        try:
            while True:
                # Read JSON-RPC response line from stdout
                response = self._read(deadline)
                if "method" in response:
                    if "id" in response:
                        # Sampling and other server-initiated requests were not negotiated.
                        self._write({"jsonrpc": "2.0", "id": response["id"], "error":
                            {"code": -32601, "message": "Client capability not supported"}}, deadline)
                    continue
                if type(response.get("id")) is not int or response["id"] != request_id:
                    raise RuntimeError("MCP response request ID mismatch")
                if ("result" in response) == ("error" in response):
                    raise RuntimeError("MCP response must contain one result or error")
                if "error" in response:
                    raise RuntimeError("MCP server returned a request error")
                result = response["result"]
                if not isinstance(result, dict):
                    raise RuntimeError("MCP result must be an object")
                return result
        except TimeoutError:
            try:
                self._write({"jsonrpc": "2.0", "method": "notifications/cancelled",
                    "params": {"requestId": request_id, "reason": "Client deadline exceeded"}},
                    time.monotonic() + 0.05)
            except (OSError, TimeoutError):
                pass
            raise

    def _call_rpc(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self._lock.acquire(timeout=self.timeout):
            raise TimeoutError("MCP request serialization deadline exceeded")
        try:
            self.start()
            try:
                result = self._exchange(method, params or {}, time.monotonic() + self.timeout)
                if method == "tools/call" and result.get("isError") is True:
                    raise RuntimeError("MCP tool execution failed")
                return result
            except BaseException:
                self.close()
                raise
        finally:
            self._lock.release()

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools exposed by CodeSage MCP server."""
        result = self._call_rpc("tools/list")
        return result.get("tools", [])

    def export_kairos_context(
        self,
        repo_id: str,
        query: str,
        symbol_name: Optional[str] = None,
        max_chunks: int = 6,
    ) -> str:
        """
        Call 'export_kairos_context' tool to retrieve a 2-hop topological AST context slice.
        Returns the formatted Markdown prompt payload.
        """
        args = {
            "repo_id": repo_id,
            "query": query,
            "max_chunks": max_chunks,
        }
        if symbol_name:
            args["symbol_name"] = symbol_name

        result = self._call_rpc("tools/call", {"name": "export_kairos_context", "arguments": args})
        content_items = result.get("content", [])
        if not content_items:
            return ""
        return content_items[0].get("text", "")

    def retrieve_code_context(
        self,
        repo_id: str,
        query: str,
        mode: str = "graph",
    ) -> list[dict[str, Any]]:
        """Call 'retrieve_code_context' tool for raw ranked chunks."""
        args = {
            "repo_id": repo_id,
            "query": query,
            "mode": mode,
        }
        result = self._call_rpc("tools/call", {"name": "retrieve_code_context", "arguments": args})
        content_items = result.get("content", [])
        if not content_items:
            return []
        raw_text = content_items[0].get("text", "[]")
        return json.loads(raw_text)

    def get_call_graph(
        self,
        repo_id: str,
        symbol_name: str,
    ) -> dict[str, Any]:
        """Call 'get_call_graph' tool for callers, callees, and topology metadata."""
        args = {
            "repo_id": repo_id,
            "symbol_name": symbol_name,
        }
        result = self._call_rpc("tools/call", {"name": "get_call_graph", "arguments": args})
        content_items = result.get("content", [])
        if not content_items:
            return {}
        raw_text = content_items[0].get("text", "{}")
        return json.loads(raw_text)
