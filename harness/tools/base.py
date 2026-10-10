from __future__ import annotations

import abc
import hashlib
import json
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    tool_name: str
    idempotency_key: str
    status: str  # "success" | "error" | "timeout"
    output: Any
    latency_ms: float
    error_message: Optional[str] = None


class BaseTool(abc.ABC):
    name: str
    description: str
    timeout_sec: float = 5.0
    read_only: bool = True

    @abc.abstractmethod
    def run(self, **kwargs) -> Any:
        pass

    def generate_idempotency_key(self, args: Dict[str, Any]) -> str:
        serialized = json.dumps({"tool": self.name, "args": args}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def execute(self, **kwargs) -> ToolResult:
        idempotency_key = self.generate_idempotency_key(kwargs)
        start_time = time.perf_counter()
        try:
            output = self.run(**kwargs)
            duration = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                idempotency_key=idempotency_key,
                status="success",
                output=output,
                latency_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                idempotency_key=idempotency_key,
                status="error",
                output=None,
                latency_ms=round(duration, 2),
                error_message=str(e),
            )
