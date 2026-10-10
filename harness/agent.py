from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel

from .events import AgentEvent, EventLog, EventType
from .context import ContextManager
from .tools.base import BaseTool, ToolResult
from .verifier import DeterministicVerifier, VerificationVerdict


class AgentConfig(BaseModel):
    agent_id: str = "text_to_sql_agent"
    version: str = "1.0.0"
    max_steps: int = 5
    token_budget: int = 4096
    compactor_policy: str = "lru_tools"


class AgentRunResult(BaseModel):
    run_id: str
    status: str  # "completed" | "failed" | "max_steps_exceeded"
    final_answer: Any
    total_steps: int
    event_log: EventLog
    verdict: Optional[VerificationVerdict] = None
    wall_time_ms: float


class AgentHarness:
    def __init__(
        self,
        config: AgentConfig,
        tools: List[BaseTool],
        model_fn: Callable[[List[Dict[str, str]], int], Dict[str, Any]],
        system_prompt: str = "You are a database querying agent. Translate requests into valid SQL.",
    ):
        self.config = config
        self.tools = {t.name: t for t in tools}
        self.model_fn = model_fn
        self.system_prompt = system_prompt

    def run(
        self,
        task_prompt: str,
        expected_output: Optional[List[Dict[str, Any]]] = None,
        resume_from_checkpoint: Optional[Dict[str, Any]] = None,
    ) -> AgentRunResult:
        start_time = time.perf_counter()
        run_id = (
            resume_from_checkpoint["run_id"]
            if resume_from_checkpoint
            else f"run_{uuid.uuid4().hex[:12]}"
        )
        event_log = EventLog(run_id=run_id)

        context_mgr = ContextManager(
            token_budget=self.config.token_budget,
            compactor_policy=self.config.compactor_policy,
        )
        context_mgr.set_system_prompt(self.system_prompt)
        context_mgr.set_task(task_prompt)

        start_step = 0
        executed_tool_keys = set()

        if resume_from_checkpoint:
            start_step = resume_from_checkpoint.get("next_step", 0)
            executed_tool_keys = set(resume_from_checkpoint.get("executed_tool_keys", []))
            # Restore past events
            for ev in resume_from_checkpoint.get("past_events", []):
                event_log.events.append(AgentEvent(**ev))
        else:
            event_log.append(
                EventType.RUN_STARTED,
                {
                    "agent_id": self.config.agent_id,
                    "version": self.config.version,
                    "task": task_prompt,
                    "max_steps": self.config.max_steps,
                },
            )

        final_answer = None
        last_verdict: Optional[VerificationVerdict] = None
        status = "running"

        for step in range(start_step, self.config.max_steps):
            # 1. Assemble context
            messages, audit, context_hash = context_mgr.assemble()
            event_log.append(
                EventType.CONTEXT_ASSEMBLED,
                {
                    "step": step,
                    "context_hash": context_hash,
                    "compaction_audit": audit.model_dump(),
                    "message_count": len(messages),
                },
            )

            # 2. Invoke model
            model_start = time.perf_counter()
            model_res = self.model_fn(messages, step)
            model_duration = round((time.perf_counter() - model_start) * 1000, 2)

            event_log.append(
                EventType.MODEL_INVOKED,
                {
                    "step": step,
                    "model_response": model_res,
                    "latency_ms": model_duration,
                },
            )

            # 3. Check if model decides to complete
            if model_res.get("type") == "final_answer":
                final_answer = model_res.get("content")
                status = "completed"
                break

            # 4. Process tool call
            if model_res.get("type") == "tool_call":
                tool_name = model_res.get("tool_name", "")
                tool_args = model_res.get("tool_args", {})
                
                tool = self.tools.get(tool_name)
                if not tool:
                    tool_res = ToolResult(
                        tool_name=tool_name,
                        idempotency_key="missing",
                        status="error",
                        output=None,
                        latency_ms=0.0,
                        error_message=f"Tool '{tool_name}' not found in registry",
                    )
                else:
                    idempotency_key = tool.generate_idempotency_key(tool_args)
                    if idempotency_key in executed_tool_keys:
                        # Prevent duplicate side-effects (Idempotency guarantee)
                        tool_res = ToolResult(
                            tool_name=tool_name,
                            idempotency_key=idempotency_key,
                            status="success",
                            output="[Idempotent Cache Hit: skipped re-execution]",
                            latency_ms=0.0,
                        )
                    else:
                        tool_res = tool.execute(**tool_args)
                        executed_tool_keys.add(idempotency_key)

                event_log.append(
                    EventType.TOOL_EXECUTED,
                    {
                        "step": step,
                        "tool_result": tool_res.model_dump(),
                    },
                )

                # Append tool observation back into context
                context_mgr.add_message(
                    role="tool",
                    content=str(tool_res.output),
                    metadata={"tool_name": tool_name, "idempotency_key": tool_res.idempotency_key},
                )

                # 5. Deterministic Verifier check if expected output provided
                if expected_output is not None and isinstance(tool_res.output, list):
                    last_verdict = DeterministicVerifier.verify_sql_result(
                        tool_res.output, expected_output
                    )
                    event_log.append(
                        EventType.VERIFIER_CHECKED,
                        {
                            "step": step,
                            "verdict": last_verdict.model_dump(),
                        },
                    )

            # 6. Save Checkpoint for durable recovery
            event_log.append(
                EventType.CHECKPOINT_SAVED,
                {
                    "step": step,
                    "next_step": step + 1,
                    "executed_tool_keys": list(executed_tool_keys),
                },
            )

        if status == "running":
            status = "max_steps_exceeded"

        wall_time = round((time.perf_counter() - start_time) * 1000, 2)
        event_log.append(
            EventType.RUN_COMPLETED if status == "completed" else EventType.RUN_FAILED,
            {
                "status": status,
                "final_answer": final_answer,
                "total_steps": len([e for e in event_log.events if e.event_type == EventType.MODEL_INVOKED]),
                "wall_time_ms": wall_time,
            },
        )

        return AgentRunResult(
            run_id=run_id,
            status=status,
            final_answer=final_answer,
            total_steps=len([e for e in event_log.events if e.event_type == EventType.MODEL_INVOKED]),
            event_log=event_log,
            verdict=last_verdict,
            wall_time_ms=wall_time,
        )
