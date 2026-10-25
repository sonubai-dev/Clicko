"""Models for Macro definitions and execution results."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class MacroDefinition(BaseModel):
    """Definition of a saved, reusable automation macro."""
    id: str = Field(description="Unique macro identifier (e.g. macro_12345)")
    name: str = Field(description="Human-readable macro name")
    description: str = Field(default="", description="Description of what this macro does")
    created_at: str = Field(description="ISO 8601 creation timestamp")
    steps: list[dict[str, Any]] = Field(
        description="Ordered sequence of action steps, each with 'tool' (or 'action') and 'args'"
    )
    parameters: list[str] = Field(
        default_factory=list,
        description="List of template parameter names expected (e.g. ['url', 'query'])",
    )


class MacroExecutionResult(BaseModel):
    """Result of executing a macro."""
    macro_id: str
    name: str
    success: bool
    steps_executed: int
    total_steps: int
    error_message: str | None = None
    task_id: str | None = None
