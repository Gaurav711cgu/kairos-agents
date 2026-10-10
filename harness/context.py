from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContextMessage(BaseModel):
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tokens: int = 0

    def compute_tokens(self) -> int:
        # 1 token ~= 4 characters as standard heuristic
        return max(1, len(self.content) // 4)


class CompactionAudit(BaseModel):
    performed: bool = False
    original_tokens: int = 0
    compacted_tokens: int = 0
    dropped_count: int = 0
    compaction_policy: str = "none"


class ContextManager:
    def __init__(self, token_budget: int = 4096, compactor_policy: str = "lru_tools"):
        self.token_budget = token_budget
        self.compactor_policy = compactor_policy
        self.system_message: Optional[ContextMessage] = None
        self.task_instruction: Optional[ContextMessage] = None
        self.history: List[ContextMessage] = []

    def set_system_prompt(self, content: str):
        msg = ContextMessage(role="system", content=content)
        msg.tokens = msg.compute_tokens()
        self.system_message = msg

    def set_task(self, task: str):
        msg = ContextMessage(role="user", content=task)
        msg.tokens = msg.compute_tokens()
        self.task_instruction = msg

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        msg = ContextMessage(role=role, content=content, metadata=metadata or {})
        msg.tokens = msg.compute_tokens()
        self.history.append(msg)

    def assemble(self) -> tuple[List[Dict[str, str]], CompactionAudit, str]:
        total_tokens = 0
        if self.system_message:
            total_tokens += self.system_message.tokens
        if self.task_instruction:
            total_tokens += self.task_instruction.tokens
        for m in self.history:
            total_tokens += m.tokens

        audit = CompactionAudit(
            performed=False,
            original_tokens=total_tokens,
            compacted_tokens=total_tokens,
            dropped_count=0,
            compaction_policy="none",
        )

        messages_to_render = []
        if self.system_message:
            messages_to_render.append(self.system_message)
        if self.task_instruction:
            messages_to_render.append(self.task_instruction)

        # Check if compaction is needed
        if total_tokens > self.token_budget:
            audit.performed = True
            audit.compaction_policy = self.compactor_policy
            
            # Compaction: Keep system, keep task instruction, compact old intermediate tool responses
            compacted_history: List[ContextMessage] = []
            cumulative = (self.system_message.tokens if self.system_message else 0) + (
                self.task_instruction.tokens if self.task_instruction else 0
            )

            # Keep the latest 3 interactions intact, compact earlier ones
            cutoff = max(0, len(self.history) - 3)
            for idx, msg in enumerate(self.history):
                if idx < cutoff and msg.role == "tool":
                    # Truncate / summarize large tool payload
                    summary_text = f"[Tool output summarized: {msg.content[:80]}...]"
                    c_msg = ContextMessage(
                        role=msg.role,
                        content=summary_text,
                        metadata={"summarized": True, **msg.metadata},
                    )
                    c_msg.tokens = c_msg.compute_tokens()
                    compacted_history.append(c_msg)
                    cumulative += c_msg.tokens
                    audit.dropped_count += 1
                else:
                    compacted_history.append(msg)
                    cumulative += msg.tokens

            audit.compacted_tokens = cumulative
            messages_to_render.extend(compacted_history)
        else:
            messages_to_render.extend(self.history)

        formatted = [{"role": m.role, "content": m.content} for m in messages_to_render]
        
        # Compute deterministic SHA-256 fingerprint of assembled context
        raw_repr = json.dumps(formatted, sort_keys=True)
        context_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()

        return formatted, audit, context_hash
