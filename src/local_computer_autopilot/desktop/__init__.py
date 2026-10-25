"""Desktop navigation and window management subsystem."""

from local_computer_autopilot.desktop.models import WindowInfo, WindowState
from local_computer_autopilot.desktop.window_manager import WindowManager

__all__ = [
    "WindowManager",
    "WindowInfo",
    "WindowState",
]
