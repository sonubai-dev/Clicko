"""Models for autonomous workflow planning and execution."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    AUTO = "auto"
    LOCAL_LLM = "local_llm"
    STRUCTURED = "structured"


class PlanStep(BaseModel):
    """An individual action step inside an autonomous task plan."""
    step_number: int = Field(ge=1, description="Sequential step index")
    action_name: str = Field(description="Name of the MCP / controller action to invoke")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")
    description: str = Field(description="Human-readable explanation of why this step is taken")
    verify_visual: bool = Field(default=False, description="Whether to capture and verify visual change")
    timeout_seconds: float = Field(default=10.0, description="Maximum execution timeout for this step")


class TaskPlan(BaseModel):
    """Complete sequence of planned steps to achieve a user goal."""
    goal: str = Field(description="Original user objective")
    mode_used: AgentMode = Field(description="Planning mode used (local_llm or structured)")
    steps: list[PlanStep] = Field(default_factory=list, description="Planned steps in order")
    estimated_duration_seconds: float = Field(default=5.0, description="Estimated completion time")
    notes: str = Field(default="", description="Planner notes or observations")


class StepExecutionDetail(BaseModel):
    """Detailed record of an executed step during an agent run."""
    step_number: int
    action_name: str
    parameters: dict[str, Any]
    status: str
    result_summary: str | None = None
    error_message: str | None = None
    visual_verified: bool = False
    duration_seconds: float = 0.0


class ExecutionResult(BaseModel):
    """Final result of an autonomous agent run."""
    task_id: str
    goal: str
    success: bool
    status: str
    steps_total: int
    steps_completed: int
    duration_seconds: float
    error_message: str | None = None
    step_details: list[StepExecutionDetail] = Field(default_factory=list)
