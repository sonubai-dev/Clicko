"""Desktop and window navigation subsystem for Windows."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from typing import Any

from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.desktop.models import (
    AppCloseResult,
    AppLaunchResult,
    WindowInfo,
    WindowState,
)

logger = logging.getLogger("local_computer_autopilot.desktop")

try:
    import win32con
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class WindowManager:
    """Manages discovery, focus, and state for top-level Windows applications."""

    def __init__(self) -> None:
        if not HAS_WIN32:
            logger.warning("pywin32 is not installed; Desktop window controls will run in degraded mode")

    def list_windows(self) -> list[WindowInfo]:
        """List all visible, named top-level windows."""
        if not HAS_WIN32:
            return []

        active_hwnd = win32gui.GetForegroundWindow()
        windows: list[WindowInfo] = []

        def enum_handler(hwnd: int, extra: Any) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).strip()
            if not title:
                return

            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            width = right - x
            height = bottom - y

            if width <= 0 or height <= 0:
                return

            windows.append(
                WindowInfo(
                    handle=hwnd,
                    title=title,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    is_active=(hwnd == active_hwnd),
                )
            )

        win32gui.EnumWindows(enum_handler, None)
        return windows

    def find_window(self, query: str | int) -> WindowInfo:
        """Find a window by exact handle or case-insensitive title search."""
        windows = self.list_windows()

        if isinstance(query, int):
            for w in windows:
                if w.handle == query:
                    return w
            raise SafetyError(f"Window with handle {query} not found")

        q_lower = query.lower().strip()
        # 1. Exact match
        for w in windows:
            if w.title.lower() == q_lower:
                return w

        # 2. Substring match
        matches = [w for w in windows if q_lower in w.title.lower()]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            matching_titles = ", ".join(f"'{m.title}'" for m in matches[:3])
            raise SafetyError(f"Multiple windows matched query '{query}': {matching_titles}")

        raise SafetyError(f"No window found matching title '{query}'")

    def focus_window(self, query: str | int) -> WindowInfo:
        """Bring window to foreground and set active focus."""
        if not HAS_WIN32:
            raise SafetyError("pywin32 is required to focus windows on Windows")

        win = self.find_window(query)
        hwnd = win.handle

        try:
            # Restore if minimized, otherwise bring to top
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.BringWindowToTop(hwnd)

            win32gui.SetForegroundWindow(hwnd)
            logger.info("Focused window: '%s' (handle=%d)", win.title, hwnd)
            win.is_active = True
            return win
        except Exception as e:
            raise SafetyError(f"Failed to focus window '{win.title}': {e}") from e

    def get_window_bounds(self, query: str | int) -> WindowInfo:
        """Get the current screen coordinates and dimensions of a window."""
        return self.find_window(query)

    def set_window_state(self, query: str | int, state: WindowState | str) -> WindowInfo:
        """Change window state (maximize, minimize, restore, normal)."""
        if not HAS_WIN32:
            raise SafetyError("pywin32 is required to manipulate window state")

        win = self.find_window(query)
        hwnd = win.handle

        if isinstance(state, str):
            try:
                state = WindowState(state.lower())
            except ValueError:
                raise SafetyError(
                    f"Invalid window state '{state}'. Valid states: {[s.value for s in WindowState]}"
                )

        cmd_map = {
            WindowState.MAXIMIZE: win32con.SW_MAXIMIZE,
            WindowState.MINIMIZE: win32con.SW_MINIMIZE,
            WindowState.RESTORE: win32con.SW_RESTORE,
            WindowState.NORMAL: win32con.SW_SHOWNORMAL,
        }

        cmd = cmd_map[state]
        win32gui.ShowWindow(hwnd, cmd)
        logger.info("Set window '%s' to state '%s'", win.title, state.value)

        # Refresh bounds
        return self.find_window(hwnd)

    def launch_app(
        self,
        app_name: str,
        args: list[str] | None = None,
        wait_seconds: float = 2.0,
    ) -> AppLaunchResult:
        """Launch a Windows desktop application safely.

        Args:
            app_name: Application name or path (e.g. 'notepad', 'calc', 'mspaint').
            args: Optional command line arguments.
            wait_seconds: Seconds to wait for application window to appear.
        """
        app_clean = app_name.strip()
        # Security validation: reject shell injection characters
        if re.search(r"[&|;><`\$\"]", app_clean):
            raise SafetyError(f"Application name contains invalid or unsafe characters: '{app_clean}'")

        cmd = [app_clean]
        if args:
            for arg in args:
                if re.search(r"[&|;><`\$]", str(arg)):
                    raise SafetyError(f"Argument contains unsafe characters: '{arg}'")
                cmd.append(str(arg))

        try:
            # Spawn process safely without shell=True
            proc = subprocess.Popen(cmd, shell=False)
            logger.info("Spawned application '%s' with PID %d", app_clean, proc.pid)
        except Exception as exc:
            logger.error("Failed to launch application '%s': %s", app_clean, exc)
            return AppLaunchResult(
                success=False,
                app_name=app_clean,
                pid=None,
                hwnd=None,
                window_title=None,
                message=f"Failed to launch application '{app_clean}': {exc}",
            )

        # Wait for window to appear if requested
        found_window: WindowInfo | None = None
        if wait_seconds > 0 and HAS_WIN32:
            start_time = time.time()
            app_lower = app_clean.lower().replace(".exe", "")
            while time.time() - start_time < wait_seconds:
                windows = self.list_windows()
                for w in windows:
                    # Match by PID if window process ID matches
                    try:
                        _, win_pid = win32process.GetWindowThreadProcessId(w.handle)
                        if win_pid == proc.pid:
                            found_window = w
                            break
                    except Exception:
                        pass
                    # Substring match by app name in title
                    if app_lower in w.title.lower():
                        found_window = w
                        break
                if found_window is not None:
                    break
                time.sleep(0.3)

        hwnd_val = found_window.handle if found_window else None
        title_val = found_window.title if found_window else None

        return AppLaunchResult(
            success=True,
            app_name=app_clean,
            pid=proc.pid,
            hwnd=hwnd_val,
            window_title=title_val,
            message=f"Launched '{app_clean}' (PID: {proc.pid}) successfully",
        )

    def close_app(self, query: str | int, graceful: bool = True) -> AppCloseResult:
        """Gracefully close an application window via WM_CLOSE.

        Args:
            query: Window handle or window title substring.
            graceful: If True, sends WM_CLOSE allowing app to save and exit cleanly.
        """
        if not HAS_WIN32:
            raise SafetyError("pywin32 is required to close desktop application windows")

        win = self.find_window(query)
        hwnd = win.handle

        try:
            if graceful:
                # Send WM_CLOSE message
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                logger.info("Sent WM_CLOSE to window '%s' (handle=%d)", win.title, hwnd)
            else:
                # Force close by process ID
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid > 0:
                    import ctypes
                    PROCESS_TERMINATE = 0x0001
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                    if handle:
                        ctypes.windll.kernel32.TerminateProcess(handle, 0)
                        ctypes.windll.kernel32.CloseHandle(handle)
                        logger.info("Terminated process PID %d for window '%s'", pid, win.title)

            return AppCloseResult(
                success=True,
                target=str(query),
                closed=True,
                message=f"Closed window '{win.title}' (handle={hwnd})",
            )
        except Exception as exc:
            logger.error("Failed to close window '%s': %s", win.title, exc)
            return AppCloseResult(
                success=False,
                target=str(query),
                closed=False,
                message=f"Failed to close window '{win.title}': {exc}",
            )
