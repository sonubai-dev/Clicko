"""Tests for ComputerController — all PyAutoGUI calls are mocked."""

from __future__ import annotations

import importlib
import io
import sys
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

Size = namedtuple("Size", ["width", "height"])
MOCK_W, MOCK_H = 1920, 1080


@pytest.fixture()
def controller():
    """Create a ComputerController with fully mocked PyAutoGUI."""
    mock_pag = MagicMock()
    mock_pag.size.return_value = Size(MOCK_W, MOCK_H)
    mock_pag.FAILSAFE = True
    mock_pag.PAUSE = 0.0

    # Mock screenshot
    mock_image = MagicMock()
    mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(b"\x89PNG_FAKE_DATA"))
    mock_pag.screenshot.return_value = mock_image

    with patch.dict("sys.modules", {"pyautogui": mock_pag}):
        # Re-import to pick up the mock
        import local_computer_autopilot.computer.controller as ctrl_mod
        importlib.reload(ctrl_mod)

        from local_computer_autopilot.config import AppConfig
        config = AppConfig(pyautogui_failsafe=True, pyautogui_pause=0.0)
        ctrl = ctrl_mod.ComputerController(config)
        ctrl._mock = mock_pag  # expose for assertions
        ctrl._SafetyError = ctrl_mod.SafetyError  # keep reference to correct class
        yield ctrl


def _safety_error(controller):
    """Get the SafetyError class matching the controller's module."""
    return controller._SafetyError


# ── Screen info ────────────────────────────────────────────────────────────


class TestGetScreenInfo:
    def test_returns_dimensions(self, controller):
        info = controller.get_screen_info()
        assert info.width == MOCK_W
        assert info.height == MOCK_H

    def test_returns_model(self, controller):
        info = controller.get_screen_info()
        d = info.model_dump()
        assert "width" in d and "height" in d


# ── Screenshot ─────────────────────────────────────────────────────────────


class TestScreenshot:
    def test_returns_png_bytes(self, controller):
        data = controller.take_screenshot()
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert b"PNG" in data

    def test_does_not_save_to_disk(self, controller):
        controller.take_screenshot()
        mock_img = controller._mock.screenshot.return_value
        mock_img.save.assert_called_once()
        args = mock_img.save.call_args
        assert isinstance(args[0][0], io.BytesIO)


# ── Mouse move ─────────────────────────────────────────────────────────────


class TestMoveMouse:
    def test_valid_move(self, controller):
        result = controller.move_mouse(100, 200, duration=0.5)
        assert result.success is True
        controller._mock.moveTo.assert_called_once_with(100, 200, duration=0.5)

    def test_out_of_bounds_x(self, controller):
        with pytest.raises(_safety_error(controller), match="out of bounds"):
            controller.move_mouse(2000, 100)

    def test_out_of_bounds_y(self, controller):
        with pytest.raises(_safety_error(controller), match="out of bounds"):
            controller.move_mouse(100, 2000)

    def test_negative_coords(self, controller):
        with pytest.raises(_safety_error(controller), match="out of bounds"):
            controller.move_mouse(-1, -1)

    def test_duration_too_long(self, controller):
        with pytest.raises(_safety_error(controller), match="out of bounds"):
            controller.move_mouse(100, 100, duration=10.0)

    def test_zero_duration(self, controller):
        result = controller.move_mouse(100, 100, duration=0.0)
        assert result.success is True


# ── Click ──────────────────────────────────────────────────────────────────


class TestClick:
    def test_left_click(self, controller):
        result = controller.click(500, 500, "left")
        assert result.success is True
        controller._mock.click.assert_called_once_with(500, 500)

    def test_right_click(self, controller):
        result = controller.click(500, 500, "right")
        assert result.success is True
        controller._mock.rightClick.assert_called_once_with(500, 500)

    def test_double_click(self, controller):
        result = controller.click(500, 500, "double")
        assert result.success is True
        controller._mock.doubleClick.assert_called_once_with(500, 500)

    def test_middle_click(self, controller):
        result = controller.click(500, 500, "middle")
        assert result.success is True
        controller._mock.middleClick.assert_called_once_with(500, 500)

    def test_invalid_click_type(self, controller):
        with pytest.raises(_safety_error(controller), match="not allowed"):
            controller.click(500, 500, "quadruple")

    def test_out_of_bounds(self, controller):
        with pytest.raises(_safety_error(controller), match="out of bounds"):
            controller.click(9999, 9999)


# ── Scroll ─────────────────────────────────────────────────────────────────


class TestScroll:
    def test_vertical_scroll(self, controller):
        result = controller.scroll(5)
        assert result.success is True
        controller._mock.scroll.assert_called_once_with(5, x=None, y=None)

    def test_horizontal_scroll(self, controller):
        result = controller.scroll(3, horizontal=True)
        assert result.success is True
        controller._mock.hscroll.assert_called_once_with(3, x=None, y=None)

    def test_scroll_with_position(self, controller):
        result = controller.scroll(-5, x=100, y=200)
        assert result.success is True

    def test_scroll_over_limit(self, controller):
        with pytest.raises(_safety_error(controller), match="exceeds maximum"):
            controller.scroll(25)

    def test_scroll_at_invalid_coords(self, controller):
        with pytest.raises(_safety_error(controller), match="out of bounds"):
            controller.scroll(3, x=9999, y=9999)


# ── Type text ──────────────────────────────────────────────────────────────


class TestTypeText:
    def test_type_ascii(self, controller):
        result = controller.type_text("hello")
        assert result.success is True
        assert result.details["length"] == 5

    def test_empty_text(self, controller):
        with pytest.raises(_safety_error(controller), match="must not be empty"):
            controller.type_text("")

    def test_text_too_long(self, controller):
        with pytest.raises(_safety_error(controller), match="exceeds maximum"):
            controller.type_text("a" * 1001)

    def test_text_not_in_result(self, controller):
        """Ensure the actual text content is not in the returned result."""
        secret = "SuperSecretText"
        result = controller.type_text(secret)
        assert secret not in result.message
        assert secret not in str(result.details)

    def test_text_not_in_logs(self, controller, caplog):
        """Ensure typed text does not appear in log output."""
        secret = "AnotherSecretText"
        import logging
        with caplog.at_level(logging.DEBUG):
            controller.type_text(secret)
        for record in caplog.records:
            assert secret not in record.getMessage()


# ── Press key ──────────────────────────────────────────────────────────────


class TestPressKey:
    def test_single_key(self, controller):
        result = controller.press_key("enter")
        assert result.success is True
        controller._mock.press.assert_called_once_with("enter")

    def test_key_combo(self, controller):
        result = controller.press_key(["ctrl", "s"])
        assert result.success is True
        controller._mock.hotkey.assert_called_once_with("ctrl", "s")

    def test_invalid_key(self, controller):
        with pytest.raises(_safety_error(controller), match="not in the allowlist"):
            controller.press_key("launch_missiles")

    def test_invalid_key_in_combo(self, controller):
        with pytest.raises(_safety_error(controller), match="not in the allowlist"):
            controller.press_key(["ctrl", "nuke"])

    def test_empty_combo(self, controller):
        with pytest.raises(_safety_error(controller), match="must not be empty"):
            controller.press_key([])

    def test_case_insensitive(self, controller):
        result = controller.press_key("ENTER")
        assert result.success is True


# ── Status ─────────────────────────────────────────────────────────────────


class TestGetStatus:
    def test_returns_status(self, controller):
        status = controller.get_status(["computer_get_screen_info"])
        assert status.runtime_active is True
        assert status.failsafe_enabled is True
        assert status.action_lock_held is False
        assert "computer_get_screen_info" in status.enabled_tools

    def test_after_shutdown(self, controller):
        controller.shutdown()
        status = controller.get_status([])
        assert status.runtime_active is False
