"""Models for browser automation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TabInfo(BaseModel):
    """Information about an open browser tab."""
    tab_index: int = Field(description="Zero-based index of the tab")
    title: str = Field(description="Page title")
    url: str = Field(description="Current URL")
    is_active: bool = Field(default=False, description="True if tab is currently focused")


class BrowserState(BaseModel):
    """Current state of the local browser session."""
    is_open: bool = Field(description="Whether the browser process is currently active")
    headless: bool = Field(description="Whether running in headless mode")
    channel: str = Field(description="Browser channel in use (msedge, chrome, chromium)")
    active_tab_title: str | None = None
    active_tab_url: str | None = None
    tab_count: int = 0


class PageElementResult(BaseModel):
    """Result of an interaction with a web page element."""
    success: bool
    selector: str
    message: str
    content: str | None = None
