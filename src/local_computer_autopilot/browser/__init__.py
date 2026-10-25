"""Browser automation subsystem."""

from local_computer_autopilot.browser.browser_manager import BrowserManager
from local_computer_autopilot.browser.models import (
    BrowserState,
    PageElementResult,
    TabInfo,
)

__all__ = [
    "BrowserManager",
    "BrowserState",
    "TabInfo",
    "PageElementResult",
]
