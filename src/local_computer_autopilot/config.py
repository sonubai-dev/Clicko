"""Configuration and safety limits for LocalComputerAutopilot."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path


@dataclass(frozen=True)
class SafetyLimits:
    """Hard limits for all computer-control operations."""

    max_move_duration: float = 5.0
    min_move_duration: float = 0.0
    max_text_length: int = 1000
    max_scroll_clicks: int = 20
    max_click_pause: float = 1.0

    # Allowlisted click types
    allowed_click_types: frozenset[str] = frozenset(
        {"left", "right", "middle", "double"}
    )

    # Allowlisted keys — PyAutoGUI documented key names
    allowed_keys: frozenset[str] = frozenset({
        # Letters
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
        "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
        # Digits
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
        # Function keys
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
        # Modifiers
        "shift", "shiftleft", "shiftright",
        "ctrl", "ctrlleft", "ctrlright",
        "alt", "altleft", "altright",
        "win", "winleft", "winright",
        # Navigation
        "up", "down", "left", "right",
        "pageup", "pagedown", "home", "end",
        # Editing
        "enter", "return", "tab", "space", "backspace", "delete",
        "insert", "escape", "esc",
        # Punctuation and symbols
        "minus", "equal", "backslash", "comma", "period", "slash",
        "semicolon", "apostrophe", "bracketleft", "bracketright",
        "grave", "capslock", "numlock", "scrolllock",
        "printscreen", "pause",
        # Numpad
        "num0", "num1", "num2", "num3", "num4", "num5",
        "num6", "num7", "num8", "num9",
        "multiply", "add", "subtract", "decimal", "divide",
    })

    # Maximum simultaneous modifier keys in a combo (e.g. ctrl+shift+s = 3)
    max_combo_keys: int = 4


@dataclass
class ToolPolicy:
    """Configurable policy controlling which tools are enabled."""

    # Phase 1: Computer control
    computer_get_screen_info: bool = True
    computer_screenshot: bool = True
    computer_move_mouse: bool = True
    computer_click: bool = True
    computer_scroll: bool = True
    computer_type_text: bool = True
    computer_press_key: bool = True
    computer_get_status: bool = True

    # Phase 2: Visual verification
    visual_wait_for_change: bool = True

    # Phase 2: Task tracking
    task_create: bool = True
    task_record_step: bool = True
    task_get_status: bool = True
    task_list_history: bool = True
    task_cancel: bool = True

    # Phase 2: Desktop & window navigation
    desktop_list_windows: bool = True
    desktop_focus_window: bool = True
    desktop_get_window_bounds: bool = True
    desktop_set_window_state: bool = True

    # Phase 2: Browser automation
    browser_open: bool = True
    browser_new_tab: bool = True
    browser_list_tabs: bool = True
    browser_switch_tab: bool = True
    browser_close_tab: bool = True
    browser_click: bool = True
    browser_type: bool = True
    browser_get_content: bool = True
    browser_screenshot: bool = True
    browser_close: bool = True

    # Phase 3: Autonomous Agent & Web UI
    agent_plan_task: bool = True
    agent_execute_task: bool = True
    web_get_status: bool = True

    # Phase 4: Visual Grounding, Macros, Multi-Monitor & Desktop System Lifecycle
    computer_get_monitors: bool = True
    computer_clipboard_get: bool = True
    computer_clipboard_set: bool = True
    desktop_launch_app: bool = True
    desktop_close_app: bool = True
    visual_locate_element: bool = True
    visual_click_element: bool = True
    macro_create: bool = True
    macro_list: bool = True
    macro_execute: bool = True
    macro_delete: bool = True

    # Phase 5: Production Automation Scheduler & Audit Exports
    schedule_create: bool = True
    schedule_list: bool = True
    schedule_delete: bool = True
    schedule_toggle: bool = True
    audit_export_json: bool = True
    audit_export_csv: bool = True

    def is_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled by its name."""
        return getattr(self, tool_name, False)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    safety: SafetyLimits = field(default_factory=SafetyLimits)
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)
    log_level: str = field(default_factory=lambda: os.getenv("CLICKO_LOG_LEVEL", "INFO"))
    pyautogui_failsafe: bool = True
    pyautogui_pause: float = 0.1
    host: str = field(default_factory=lambda: os.getenv("CLICKO_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("CLICKO_PORT", "8000")))
    log_file: str | None = field(default_factory=lambda: os.getenv("CLICKO_LOG_FILE", "logs/clicko.log"))
    require_approval: bool = field(
        default_factory=lambda: os.getenv("CLICKO_REQUIRE_APPROVAL", "false").lower() in ("true", "1", "yes")
    )


def configure_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Configure logging to stderr and optional rotating file.

    STDOUT is strictly reserved for MCP JSON-RPC stdio transport.
    """
    logger = logging.getLogger("local_computer_autopilot")
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # 1. Stderr stream handler
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)

        # 2. Optional rotating file handler
        target_log_file = log_file or os.getenv("CLICKO_LOG_FILE")
        if target_log_file and target_log_file != ":none:":
            try:
                log_path = Path(target_log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(
                    log_path,
                    maxBytes=10 * 1024 * 1024,  # 10 MB per file
                    backupCount=5,
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as exc:
                # Do not break if file logging fails
                logger.warning("Could not initialize file logger: %s", exc)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
