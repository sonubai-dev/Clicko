"""Unit tests for local browser automation subsystem."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch
import pytest

from local_computer_autopilot.browser.browser_manager import BrowserManager
from local_computer_autopilot.computer.safety import SafetyError


@pytest.fixture()
def mock_browser_manager():
    """Mock Playwright infrastructure for isolated unit testing."""
    mock_page = MagicMock()
    mock_page.title.return_value = "Example Page"
    mock_page.url = "https://example.com"
    mock_page.inner_text.return_value = "Welcome to Example Domain"
    mock_page.screenshot.return_value = b"\x89PNG_BROWSER_SCREENSHOT"

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.is_connected.return_value = True
    mock_browser.new_context.return_value = mock_context

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    with patch("local_computer_autopilot.browser.browser_manager.HAS_PLAYWRIGHT", True), \
         patch("local_computer_autopilot.browser.browser_manager.sync_playwright") as mock_sync:
        mock_sync.return_value.start.return_value = mock_playwright
        mgr = BrowserManager(default_channel="msedge")
        mgr._mock_page = mock_page
        mgr._mock_browser = mock_browser
        yield mgr


class TestBrowserManager:
    def test_open_url(self, mock_browser_manager):
        state = mock_browser_manager.open_url("https://example.com")
        assert state.is_open is True
        assert state.active_tab_title == "Example Page"
        assert state.active_tab_url == "https://example.com"
        mock_browser_manager._mock_page.goto.assert_called_with(
            "https://example.com", wait_until="load", timeout=30000
        )

    def test_new_tab_and_list_tabs(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        tab2 = mock_browser_manager.new_tab("https://example.org")
        assert tab2.tab_index == 1

        tabs = mock_browser_manager.list_tabs()
        assert len(tabs) == 2

    def test_switch_tab(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        mock_browser_manager.new_tab("https://example.org")

        switched = mock_browser_manager.switch_tab(0)
        assert switched.tab_index == 0
        assert switched.is_active is True

    def test_switch_tab_out_of_range(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        with pytest.raises(SafetyError, match="out of range"):
            mock_browser_manager.switch_tab(99)

    def test_close_tab(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        mock_browser_manager.new_tab("https://example.org")
        assert len(mock_browser_manager.list_tabs()) == 2

        mock_browser_manager.close_tab(0)
        assert len(mock_browser_manager.list_tabs()) == 1

    def test_click_element(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        res = mock_browser_manager.click("button#submit")
        assert res.success is True
        mock_browser_manager._mock_page.click.assert_called_with("button#submit", timeout=5000)

    def test_type_text_privacy_leak_protection(self, mock_browser_manager, caplog):
        mock_browser_manager.open_url("https://example.com")
        secret_text = "SuperSecretPassword123"

        with caplog.at_level(logging.DEBUG):
            res = mock_browser_manager.type_text("input#password", secret_text)

        assert res.success is True
        assert secret_text not in res.message
        # Confirm password text was not written into any log entry
        for record in caplog.records:
            assert secret_text not in record.getMessage()

    def test_get_content(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        res = mock_browser_manager.get_content("h1")
        assert res.success is True
        assert res.content == "Welcome to Example Domain"

    def test_take_screenshot(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        png = mock_browser_manager.take_screenshot()
        assert isinstance(png, bytes)
        assert len(png) > 0

    def test_close_browser(self, mock_browser_manager):
        mock_browser_manager.open_url("https://example.com")
        mock_browser_manager.close()
        assert mock_browser_manager.is_running is False
