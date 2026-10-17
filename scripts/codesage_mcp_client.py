"""
CodeSage Model Context Protocol (MCP) Client for Kairos.

Enables Kairos SWE repair agents to query CodeSage Graph-RAG retrieval over
standard MCP stdio JSON-RPC protocol without tight coupling.

Retrieves:
  - 2-hop topological call chains (callers and callees)
  - AST-pruned function signatures, docstrings, and type hints
  - Bounded context slices ready for Kairos 14B QLoRA prompt consumption.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CODESAGE_ROOT = Path("/Users/gauravkumarnayak/Desktop/Codesage")


class CodeSageMCPClient:
    """Stdio JSON-RPC MCP client for interacting with CodeSage repository intelligence server."""

    def __init__(self, codesage_root: Optional[Path] = None, timeout: float = 30.0) -> None:
        self.codesage_root = codesage_root or Path(os.environ.get("CODESAGE_PATH", str(DEFAULT_CODESAGE_ROOT)))
        self.run_mcp_script = self.codesage_root / "bin" / "run-mcp"
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self._request_counter = 0

    def start(self) -> None:
        """Spawn the CodeSage MCP server subprocess."""
        if self.process is not None and self.process.poll() is None:
            return

        if not self.run_mcp_script.exists():
            raise FileNotFoundError(f"CodeSage MCP launcher not found at {self.run_mcp_script}")

        cmd = [str(self.run_mcp_script)]
        logger.info("Spawning CodeSage MCP server: %s", " ".join(cmd))
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(self.codesage_root),
        )

    def close(self) -> None:
        """Terminate the server process."""
        if self.process is not None:
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=3.0)
            except Exception:
                self.process.kill()
            finally:
                self.process = None

    def __enter__(self) -> CodeSageMCPClient:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _call_rpc(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if self.process is None or self.process.poll() is not None:
            self.start()

        self._request_counter += 1
        req_id = self._request_counter
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        req_line = json.dumps(payload) + "\n"
        self.process.stdin.write(req_line)
        self.process.stdin.flush()

        # Read JSON-RPC response line from stdout
        resp_line = self.process.stdout.readline()
        if not resp_line:
            stderr_out = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"CodeSage MCP server closed pipe unexpectedly. Stderr: {stderr_out}")

        resp = json.loads(resp_line)
        if "error" in resp:
            raise RuntimeError(f"MCP RPC Error ({resp['error'].get('code')}): {resp['error'].get('message')}")

        return resp.get("result", {})

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
