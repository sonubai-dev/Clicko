"""Models for automated scheduled workflows."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScheduleDefinition(BaseModel):
    """Definition of an automated recurring autopilot schedule."""
    id: str = Field(description="Unique schedule identifier (e.g. sched_12345)")
    name: str = Field(description="Human-readable schedule title")
    interval_seconds: int = Field(gt=0, description="Interval in seconds between runs")
    target: str = Field(description="Goal prompt or macro name/id to execute")
    is_macro: bool = Field(default=False, description="Whether target is a macro name/id (True) or goal string (False)")
    enabled: bool = Field(default=True, description="Whether schedule is active")
    last_run: str | None = Field(default=None, description="ISO timestamp of last execution")
    next_run: str | None = Field(default=None, description="ISO timestamp of next scheduled execution")
    run_count: int = Field(default=0, description="Total number of times executed")


class ScheduleExecutionResult(BaseModel):
    """Summary of a scheduled workflow run."""
    schedule_id: str
    name: str
    success: bool
    executed_at: str
    message: str
