from __future__ import annotations

import hashlib
import json
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    CONTEXT_ASSEMBLED = "context_assembled"
    MODEL_INVOKED = "model_invoked"
    TOOL_EXECUTED = "tool_executed"
    VERIFIER_CHECKED = "verifier_checked"
    CHECKPOINT_SAVED = "checkpoint_saved"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class AgentEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    seq_id: int
    timestamp_ns: int = Field(default_factory=lambda: time.time_ns())
    event_type: EventType
    payload: Dict[str, Any]
    prev_event_hash: str = "0" * 64
    event_hash: str = ""

    def compute_hash(self) -> str:
        data_to_hash = {
            "run_id": self.run_id,
            "seq_id": self.seq_id,
            "timestamp_ns": self.timestamp_ns,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "prev_event_hash": self.prev_event_hash,
        }
        serialized = json.dumps(data_to_hash, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def finalize(self) -> AgentEvent:
        self.event_hash = self.compute_hash()
        return self


class EventLog(BaseModel):
    run_id: str
    events: List[AgentEvent] = Field(default_factory=list)

    def append(self, event_type: EventType, payload: Dict[str, Any]) -> AgentEvent:
        seq_id = len(self.events)
        prev_hash = self.events[-1].event_hash if self.events else "0" * 64
        event = AgentEvent(
            run_id=self.run_id,
            seq_id=seq_id,
            event_type=event_type,
            payload=payload,
            prev_event_hash=prev_hash,
        ).finalize()
        self.events.append(event)
        return event

    def verify_integrity(self) -> bool:
        for idx, event in enumerate(self.events):
            expected_prev = self.events[idx - 1].event_hash if idx > 0 else "0" * 64
            if event.prev_event_hash != expected_prev:
                return False
            if event.event_hash != event.compute_hash():
                return False
        return True
