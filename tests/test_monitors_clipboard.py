"""Tests for multi-monitor display management and system clipboard operations."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from local_computer_autopilot.computer.controller import ComputerController
from local_computer_autopilot.computer.models import ClipboardResult, MonitorInfo
from local_computer_autopilot.computer.safety import SafetyError, validate_clipboard_text
from local_computer_autopilot.config import AppConfig


class TestMultiMonitor:
    """Tests for multi-monitor display detection and screenshot targeting."""

    def test_get_monitors_enumeration(self, config: AppConfig) -> None:
        ctrl = ComputerController(config)
        monitors = ctrl.get_monitors()
        assert len(monitors) >= 1
        mon = monitors[0]
        assert isinstance(mon, MonitorInfo)
        assert mon.width > 0
        assert mon.height > 0
        assert mon.index == 0
        assert isinstance(mon.is_primary, bool)

    def test_get_monitors_fallback_when_win32api_fails(self, config: AppConfig) -> None:
        ctrl = ComputerController(config)
        with patch.dict("sys.modules", {"win32api": None}):
            monitors = ctrl.get_monitors()
            assert len(monitors) >= 1
            assert monitors[0].width > 0

    def test_screenshot_specific_monitor(self, config: AppConfig) -> None:
        ctrl = ComputerController(config)
        # Mock pyautogui.screenshot returning a synthetic image
        synth_img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        with patch("local_computer_autopilot.computer.controller.pyautogui.screenshot", return_value=synth_img):
            png_bytes = ctrl.take_screenshot(monitor_index=0)
            assert isinstance(png_bytes, bytes)
            assert len(png_bytes) > 0
            # Verify valid PNG
            img = Image.open(io.BytesIO(png_bytes))
            assert img.format == "PNG"

    def test_screenshot_invalid_monitor_index_raises(self, config: AppConfig) -> None:
        ctrl = ComputerController(config)
        with pytest.raises(SafetyError, match="out of range"):
            ctrl.take_screenshot(monitor_index=999)


class TestClipboard:
    """Tests for system clipboard read and write safety."""

    def test_set_and_get_clipboard_text(self, config: AppConfig) -> None:
        ctrl = ComputerController(config)
        test_msg = "Hello Clicko Autopilot 2026!"
        res_set = ctrl.set_clipboard_text(test_msg)
        assert res_set.success is True
        assert res_set.content_length == len(test_msg)

        res_get = ctrl.get_clipboard_text()
        assert res_get.success is True
        assert res_get.content_length > 0
        assert "Hello" in res_get.content_preview

    def test_clipboard_length_validation_rejects_huge_text(self) -> None:
        huge_str = "A" * 6000
        with pytest.raises(SafetyError, match="exceeds maximum allowed"):
            validate_clipboard_text(huge_str, max_length=5000)

    def test_clipboard_validation_rejects_non_string(self) -> None:
        with pytest.raises(SafetyError, match="must be a string"):
            validate_clipboard_text(12345)  # type: ignore[arg-type]
