"""Shared test fixtures and mocks — all PyAutoGUI calls are mocked."""

from __future__ import annotations

import sys
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from local_computer_autopilot.config import AppConfig, SafetyLimits, ToolPolicy


# ── Mock PyAutoGUI before importing controller ───────────────────────────

Size = namedtuple("Size", ["width", "height"])

MOCK_SCREEN_WIDTH = 1920
MOCK_SCREEN_HEIGHT = 1080


@pytest.fixture()
def mock_pyautogui():
    """Provide a fully mocked pyautogui module for tests."""
    with patch.dict("sys.modules", {}):
        mock = MagicMock()
        mock.size.return_value = Size(MOCK_SCREEN_WIDTH, MOCK_SCREEN_HEIGHT)
        mock.FAILSAFE = True
        mock.PAUSE = 0.1
        # screenshot returns a mock image with a save method
        mock_image = MagicMock()
        mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(b"\x89PNG_FAKE"))
        mock.screenshot.return_value = mock_image
        with patch.dict("sys.modules", {"pyautogui": mock}):
            yield mock


@pytest.fixture()
def config() -> AppConfig:
    """Standard test configuration."""
    return AppConfig(
        pyautogui_failsafe=True,
        pyautogui_pause=0.0,
    )


@pytest.fixture()
def safety_limits() -> SafetyLimits:
    """Standard safety limits for validation tests."""
    return SafetyLimits()


@pytest.fixture()
def tool_policy() -> ToolPolicy:
    """Standard tool policy with all tools enabled."""
    return ToolPolicy()
