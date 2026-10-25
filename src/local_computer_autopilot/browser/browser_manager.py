"""Browser automation subsystem using local Playwright."""

from __future__ import annotations

import logging
from typing import Any

from local_computer_autopilot.browser.models import (
    BrowserState,
    PageElementResult,
    TabInfo,
)
from local_computer_autopilot.computer.safety import SafetyError

logger = logging.getLogger("local_computer_autopilot.browser")

try:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class BrowserManager:
    """Manages local browser automation sessions via Playwright."""

    def __init__(self, default_channel: str = "msedge") -> None:
        self.default_channel = default_channel
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._active_page: Page | None = None
        self._pages: list[Page] = []
        self._headless: bool = False
        self._channel_in_use: str = default_channel

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    def _ensure_browser(self, headless: bool = False) -> None:
        if self.is_running and self._headless == headless:
            return

        if not HAS_PLAYWRIGHT:
            raise SafetyError("Playwright is not installed. Install with: pip install playwright")

        # Clean up existing instance if stale, disconnected, or changing headless state
        if self._playwright is not None or self._browser is not None:
            self.close()

        self._headless = headless
        self._playwright = sync_playwright().start()

        # Try default channel (msedge), fallback to chrome, then standard chromium
        channels_to_try = [self.default_channel, "chrome", None]
        last_error = None

        for ch in channels_to_try:
            try:
                launch_kwargs: dict[str, Any] = {"headless": headless}
                if ch:
                    launch_kwargs["channel"] = ch
                self._browser = self._playwright.chromium.launch(**launch_kwargs)
                self._channel_in_use = ch or "chromium"
                logger.info("Launched local browser using channel '%s' (headless=%s)", self._channel_in_use, headless)
                break
            except Exception as e:
                last_error = e
                continue

        if not self._browser:
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            raise SafetyError(f"Failed to launch browser with any channel: {last_error}")

        self._context = self._browser.new_context()
        self._active_page = self._context.new_page()
        self._pages = [self._active_page]

    def open_url(self, url: str, headless: bool = False) -> BrowserState:
        """Open a URL in the browser, starting it if necessary."""
        self._ensure_browser(headless=headless)
        if not self._active_page:
            raise SafetyError("No active browser page")

        logger.info("Navigating to URL: %s", url)
        self._active_page.goto(url, wait_until="load", timeout=30000)
        return self.get_state()

    def new_tab(self, url: str | None = None) -> TabInfo:
        """Open a new browser tab."""
        self._ensure_browser(headless=self._headless)
        if not self._context:
            raise SafetyError("Browser context is not initialized")

        new_page = self._context.new_page()
        self._pages.append(new_page)
        self._active_page = new_page

        if url:
            new_page.goto(url, wait_until="load", timeout=30000)

        idx = len(self._pages) - 1
        return TabInfo(
            tab_index=idx,
            title=new_page.title(),
            url=new_page.url,
            is_active=True,
        )

    def list_tabs(self) -> list[TabInfo]:
        """List all currently open tabs."""
        if not self.is_running:
            return []

        tabs: list[TabInfo] = []
        for i, page in enumerate(self._pages):
            try:
                tabs.append(
                    TabInfo(
                        tab_index=i,
                        title=page.title() or "Untitled",
                        url=page.url or "about:blank",
                        is_active=(page == self._active_page),
                    )
                )
            except Exception:
                continue
        return tabs

    def switch_tab(self, tab_index: int) -> TabInfo:
        """Switch active focus to a specific tab by index."""
        if not self.is_running or not self._pages:
            raise SafetyError("No browser session active")

        if tab_index < 0 or tab_index >= len(self._pages):
            raise SafetyError(f"Tab index {tab_index} out of range (0 to {len(self._pages) - 1})")

        self._active_page = self._pages[tab_index]
        self._active_page.bring_to_front()
        return TabInfo(
            tab_index=tab_index,
            title=self._active_page.title(),
            url=self._active_page.url,
            is_active=True,
        )

    def close_tab(self, tab_index: int | None = None) -> None:
        """Close specified tab or the current active tab."""
        if not self.is_running or not self._pages:
            return

        target_idx = tab_index if tab_index is not None else self._pages.index(self._active_page) if self._active_page in self._pages else 0
        if 0 <= target_idx < len(self._pages):
            page_to_close = self._pages.pop(target_idx)
            page_to_close.close()
            if self._pages:
                self._active_page = self._pages[-1]
            else:
                self.close()

    def click(self, selector: str) -> PageElementResult:
        """Click an element matching the CSS or XPath selector."""
        if not self.is_running or not self._active_page:
            raise SafetyError("No active browser session to click element")

        try:
            self._active_page.wait_for_selector(selector, timeout=10000)
            self._active_page.click(selector, timeout=5000)
            logger.info("Clicked element matching selector: %s", selector)
            return PageElementResult(
                success=True,
                selector=selector,
                message=f"Clicked element matching '{selector}'",
            )
        except Exception as e:
            raise SafetyError(f"Failed to click element '{selector}': {e}") from e

    def type_text(self, selector: str, text: str) -> PageElementResult:
        """Type text into an input element. Text content is NEVER logged."""
        if not self.is_running or not self._active_page:
            raise SafetyError("No active browser session to type into element")

        try:
            self._active_page.wait_for_selector(selector, timeout=10000)
            self._active_page.fill(selector, text, timeout=5000)
            # Never log the text content
            logger.info("Typed text into selector '%s' (length=%d)", selector, len(text))
            return PageElementResult(
                success=True,
                selector=selector,
                message=f"Typed {len(text)} characters into '{selector}'",
            )
        except Exception as e:
            raise SafetyError(f"Failed to type into element '{selector}': {e}") from e

    def get_content(self, selector: str | None = None) -> PageElementResult:
        """Get inner text of page or specific selector."""
        if not self.is_running or not self._active_page:
            raise SafetyError("No active browser session")

        try:
            if selector:
                self._active_page.wait_for_selector(selector, timeout=5000)
                content = self._active_page.inner_text(selector, timeout=5000)
                msg = f"Retrieved text for selector '{selector}'"
            else:
                content = self._active_page.inner_text("body", timeout=5000)
                msg = "Retrieved page body text"

            return PageElementResult(
                success=True,
                selector=selector or "body",
                message=msg,
                content=content,
            )
        except Exception as e:
            raise SafetyError(f"Failed to get content for '{selector}': {e}") from e

    def take_screenshot(self) -> bytes:
        """Capture screenshot of the active browser viewport."""
        if not self.is_running or not self._active_page:
            raise SafetyError("No active browser session for screenshot")
        return self._active_page.screenshot(type="png")

    def get_state(self) -> BrowserState:
        """Get summary of the current browser state."""
        if not self.is_running or not self._active_page:
            return BrowserState(
                is_open=False,
                headless=self._headless,
                channel=self._channel_in_use,
                active_tab_title=None,
                active_tab_url=None,
                tab_count=0,
            )

        return BrowserState(
            is_open=True,
            headless=self._headless,
            channel=self._channel_in_use,
            active_tab_title=self._active_page.title() if self._active_page else None,
            active_tab_url=self._active_page.url if self._active_page else None,
            tab_count=len(self._pages),
        )

    def close(self) -> None:
        """Close browser context, browser process, and Playwright driver."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.debug("Error while closing browser: %s", e)
        finally:
            self._browser = None
            self._context = None
            self._playwright = None
            self._active_page = None
            self._pages = []
            logger.info("Browser session closed")
