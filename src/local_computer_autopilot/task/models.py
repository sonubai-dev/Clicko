"""Models for task and step tracking."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskRecord(BaseModel):
    """Record of a high-level user or autonomous task."""
    task_id: str
    description: str
    status: TaskStatus
    created_at: float
    updated_at: float
    error_message: str | None = None
    step_count: int = 0


class StepRecord(BaseModel):
    """Record of an individual action step inside a task."""
    step_id: int | None = None
    task_id: str
    step_number: int
    action_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus
    result_summary: str | None = None
    error_message: str | None = None
    visual_verified: bool = False
    created_at: float
