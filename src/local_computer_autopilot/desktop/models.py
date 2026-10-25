"""Models for desktop and window navigation."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class WindowState(str, Enum):
    NORMAL = "normal"
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    RESTORE = "restore"


class WindowInfo(BaseModel):
    """Information about an active top-level desktop window."""
    handle: int = Field(description="OS window handle")
    title: str = Field(description="Window title text")
    x: int = Field(description="Left screen coordinate")
    y: int = Field(description="Top screen coordinate")
    width: int = Field(description="Window width in pixels")
    height: int = Field(description="Window height in pixels")
    is_active: bool = Field(default=False, description="Whether this window currently has foreground focus")


class AppLaunchResult(BaseModel):
    """Result of launching a desktop application."""
    success: bool
    app_name: str
    pid: int | None = Field(default=None, description="Launched process identifier")
    hwnd: int | None = Field(default=None, description="Window handle if discovered")
    window_title: str | None = Field(default=None, description="Window title if discovered")
    message: str


class AppCloseResult(BaseModel):
    """Result of gracefully closing an application."""
    success: bool
    target: str = Field(description="Target window handle or title substring")
    closed: bool
    message: str
