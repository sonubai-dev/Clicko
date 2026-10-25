"""Pydantic models for structured inputs and outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Output models ──────────────────────────────────────────────────────────

class ScreenInfo(BaseModel):
    """Screen dimensions."""
    width: int = Field(description="Screen width in pixels")
    height: int = Field(description="Screen height in pixels")


class MonitorInfo(BaseModel):
    """Information about a connected display monitor."""
    index: int = Field(description="Monitor index (0-based)")
    device: str = Field(description="Device name (e.g. \\\\.\\DISPLAY1)")
    is_primary: bool = Field(description="Whether this is the primary display")
    x: int = Field(description="Left coordinate of monitor")
    y: int = Field(description="Top coordinate of monitor")
    width: int = Field(description="Width in pixels")
    height: int = Field(description="Height in pixels")
    work_area: dict[str, int] = Field(description="Usable work area excluding taskbar")


class ClipboardResult(BaseModel):
    """Result of clipboard read or write operations."""
    success: bool
    content_length: int = Field(description="Length of clipboard text in characters")
    content_preview: str = Field(description="Sanitized preview of clipboard text")
    message: str


class ActionResult(BaseModel):
    """Standard result for actions that modify desktop state."""
    success: bool
    message: str
    details: dict[str, object] | None = None


class StatusReport(BaseModel):
    """Runtime status report."""
    runtime_active: bool
    failsafe_enabled: bool
    action_lock_held: bool
    enabled_tools: list[str]
