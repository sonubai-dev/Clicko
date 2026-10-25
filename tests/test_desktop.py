"""Unit tests for Desktop and Window navigation subsystem."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.desktop.models import WindowInfo, WindowState
from local_computer_autopilot.desktop.window_manager import WindowManager


@pytest.fixture()
def mock_win32():
    mock_gui = MagicMock()
    mock_con = MagicMock()

    # Setup simulated windows:
    # HWND 101: "Untitled - Notepad" (100, 100, 800, 600)
    # HWND 102: "Calculator" (50, 50, 400, 500)
    # HWND 103: "Calculator Pro" (ambiguity test)
    # HWND 999: "" (hidden/empty title)
    windows_data = [
        (101, "Untitled - Notepad", (100, 100, 900, 700), True),
        (102, "Calculator", (50, 50, 450, 550), True),
        (103, "Calculator Pro", (60, 60, 460, 560), True),
        (999, "", (0, 0, 10, 10), False),
    ]

    def fake_enum(callback, extra):
        for hwnd, title, rect, visible in windows_data:
            mock_gui.IsWindowVisible.return_value = visible
            mock_gui.GetWindowText.return_value = title
            mock_gui.GetWindowRect.return_value = rect
            callback(hwnd, extra)

    mock_gui.EnumWindows.side_effect = fake_enum
    mock_gui.GetForegroundWindow.return_value = 101
    mock_gui.IsIconic.return_value = False

    with patch.dict(
        "sys.modules",
        {"win32gui": mock_gui, "win32con": mock_con, "win32process": MagicMock()},
    ):
        with patch("local_computer_autopilot.desktop.window_manager.HAS_WIN32", True), \
             patch("local_computer_autopilot.desktop.window_manager.win32gui", mock_gui), \
             patch("local_computer_autopilot.desktop.window_manager.win32con", mock_con):
            mgr = WindowManager()
            mgr._mock_gui = mock_gui
            mgr._mock_con = mock_con
            yield mgr


class TestWindowManager:
    def test_list_windows(self, mock_win32):
        wins = mock_win32.list_windows()
        # Should include Notepad, Calculator, Calculator Pro (skips empty 999)
        assert len(wins) == 3
        notepad = next(w for w in wins if "Notepad" in w.title)
        assert notepad.handle == 101
        assert notepad.width == 800
        assert notepad.height == 600
        assert notepad.is_active is True

    def test_find_window_exact(self, mock_win32):
        win = mock_win32.find_window("Untitled - Notepad")
        assert win.handle == 101

    def test_find_window_handle(self, mock_win32):
        win = mock_win32.find_window(102)
        assert win.title == "Calculator"

    def test_find_window_substring(self, mock_win32):
        win = mock_win32.find_window("notepad")
        assert win.handle == 101

    def test_find_window_ambiguous(self, mock_win32):
        # Query "Calc" matches both Calculator and Calculator Pro
        with pytest.raises(SafetyError, match="Multiple windows matched"):
            mock_win32.find_window("Calc")

    def test_find_window_not_found(self, mock_win32):
        with pytest.raises(SafetyError, match="No window found"):
            mock_win32.find_window("NonExistentApp123")

    def test_focus_window(self, mock_win32):
        win = mock_win32.focus_window("notepad")
        assert win.handle == 101
        mock_win32._mock_gui.SetForegroundWindow.assert_called_with(101)

    def test_set_window_state(self, mock_win32):
        mock_win32.set_window_state(101, WindowState.MAXIMIZE)
        mock_win32._mock_gui.ShowWindow.assert_called_with(101, mock_win32._mock_con.SW_MAXIMIZE)

    def test_get_window_bounds(self, mock_win32):
        bounds = mock_win32.get_window_bounds(101)
        assert bounds.x == 100
        assert bounds.y == 100
        assert bounds.width == 800
        assert bounds.height == 600

    def test_launch_app_success(self, mock_win32):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 4321
            mock_popen.return_value = mock_proc
            res = mock_win32.launch_app("notepad.exe", wait_seconds=0)
            assert res.success is True
            assert res.pid == 4321
            mock_popen.assert_called_with(["notepad.exe"], shell=False)

    def test_launch_app_injection_rejected(self, mock_win32):
        with pytest.raises(SafetyError, match="unsafe characters"):
            mock_win32.launch_app("notepad.exe; rm -rf /")

    def test_close_app_graceful(self, mock_win32):
        res = mock_win32.close_app("notepad", graceful=True)
        assert res.success is True
        assert res.closed is True
        mock_win32._mock_gui.PostMessage.assert_called_with(101, mock_win32._mock_con.WM_CLOSE, 0, 0)
