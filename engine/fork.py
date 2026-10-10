from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional
from harness.events import AgentEvent, EventLog, EventType
from harness.agent import AgentHarness, AgentConfig, AgentRunResult
from harness.tools.base import BaseTool


class ForkEngine:
    """
    Fork Engine.
    Takes a historical immutable run, forks execution at step k,
    injects modified prompts, tools, or model responses, and re-executes live.
    """

    @staticmethod
    def fork_at_step(
        harness: AgentHarness,
        task_prompt: str,
        baseline_log: EventLog,
        fork_step: int,
        patched_model_fn: Optional[Callable[[List[Dict[str, str]], int], Dict[str, Any]]] = None,
        expected_output: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentRunResult:
        # 1. Collect past events prior to fork_step
        past_events = []
        executed_tool_keys = []

        for e in baseline_log.events:
            step_num = e.payload.get("step")
            if step_num is not None and step_num < fork_step:
                past_events.append(e.model_dump())
                if e.event_type == EventType.TOOL_EXECUTED:
                    key = e.payload.get("tool_result", {}).get("idempotency_key")
                    if key:
                        executed_tool_keys.append(key)
            elif e.event_type == EventType.RUN_STARTED:
                past_events.append(e.model_dump())

        checkpoint_data = {
            "run_id": f"fork_{baseline_log.run_id[:8]}_s{fork_step}",
            "next_step": fork_step,
            "executed_tool_keys": executed_tool_keys,
            "past_events": past_events,
        }

        # 2. Swap model policy if patched
        original_model_fn = harness.model_fn
        if patched_model_fn:
            harness.model_fn = patched_model_fn

        try:
            forked_result = harness.run(
                task_prompt=task_prompt,
                expected_output=expected_output,
                resume_from_checkpoint=checkpoint_data,
            )
            return forked_result
        finally:
            harness.model_fn = original_model_fn
