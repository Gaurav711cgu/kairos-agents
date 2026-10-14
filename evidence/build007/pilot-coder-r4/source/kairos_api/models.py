"""Controlled command contracts. No caller-supplied tools, tenant IDs, or tasks."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

Policy = Literal["compact", "preserve"]
ScenarioId = Literal["late-order-exception", "late-order-standard", "insufficient-evidence"]


class RunCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: ScenarioId = "late-order-exception"
    policy: Policy = "compact"
    publish: bool = False


class ForkCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: Policy = "preserve"
