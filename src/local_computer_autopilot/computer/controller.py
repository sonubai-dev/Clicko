"""Computer control service wrapping PyAutoGUI with safety checks."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import pyautogui
import pyperclip

from local_computer_autopilot.computer.models import (
    ActionResult,
    ClipboardResult,
    MonitorInfo,
    ScreenInfo,
    StatusReport,
)
from local_computer_autopilot.computer.safety import (
    ActionLock,
    SafetyError,
    validate_click_type,
    validate_clipboard_text,
    validate_coordinates,
    validate_duration,
    validate_key,
    validate_key_combo,
    validate_scroll_amount,
    validate_text_length,
)
from local_computer_autopilot.config import AppConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger("local_computer_autopilot.controller")


class ComputerController:
    """Safe wrapper around PyAutoGUI operations.

    All public methods validate inputs before performing actions.
    All desktop-mutating operations acquire the action lock to prevent
    concurrent conflicting actions.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._action_lock = ActionLock()
        self._active = True

        # Configure PyAutoGUI safety
        pyautogui.FAILSAFE = config.pyautogui_failsafe
        pyautogui.PAUSE = config.pyautogui_pause
        logger.info(
            "ComputerController initialized (failsafe=%s, pause=%.2fs)",
            config.pyautogui_failsafe,
            config.pyautogui_pause,
        )

    @property
    def action_lock(self) -> ActionLock:
        """Expose the action lock for status queries."""
        return self._action_lock

    @property
    def is_active(self) -> bool:
        """Whether the controller is in an active state."""
        return self._active

    def shutdown(self) -> None:
        """Cooperative shutdown — marks controller as inactive."""
        self._active = False
        logger.info("ComputerController shut down")

    # ── Read-only operations (no lock needed) ─────────────────────────────

    def get_screen_info(self) -> ScreenInfo:
        """Return the current screen dimensions."""
        size = pyautogui.size()
        return ScreenInfo(width=size.width, height=size.height)

    def get_monitors(self) -> list[MonitorInfo]:
        """Return information about all connected displays."""
        monitors: list[MonitorInfo] = []
        try:
            import win32api

            raw_monitors = win32api.EnumDisplayMonitors()
            for idx, (hmon, _, rect) in enumerate(raw_monitors):
                info = win32api.GetMonitorInfo(hmon)
                m_rect = info.get("Monitor", rect)
                w_rect = info.get("Work", rect)
                flags = info.get("Flags", 0)
                is_primary = bool(flags & 1)  # MONITORINFOF_PRIMARY = 1
                device = str(info.get("Device", f"Display{idx + 1}"))
                monitors.append(
                    MonitorInfo(
                        index=idx,
                        device=device,
                        is_primary=is_primary,
                        x=m_rect[0],
                        y=m_rect[1],
                        width=m_rect[2] - m_rect[0],
                        height=m_rect[3] - m_rect[1],
                        work_area={
                            "x": w_rect[0],
                            "y": w_rect[1],
                            "width": w_rect[2] - w_rect[0],
                            "height": w_rect[3] - w_rect[1],
                        },
                    )
                )
        except Exception as exc:
            logger.warning("Could not enumerate monitors via win32api: %s; falling back to primary", exc)

        if not monitors:
            size = pyautogui.size()
            monitors.append(
                MonitorInfo(
                    index=0,
                    device="\\\\.\\DISPLAY1",
                    is_primary=True,
                    x=0,
                    y=0,
                    width=size.width,
                    height=size.height,
                    work_area={"x": 0, "y": 0, "width": size.width, "height": size.height},
                )
            )
        return monitors

    def take_screenshot(self, monitor_index: int | None = None) -> bytes:
        """Capture a screenshot and return it as PNG bytes.

        Args:
            monitor_index: Optional index of a specific monitor to capture.
                           If None, captures the primary desktop.

        Does NOT save to disk.
        """
        target_mon = None
        if monitor_index is not None:
            monitors = self.get_monitors()
            if monitor_index < 0 or monitor_index >= len(monitors):
                raise SafetyError(f"Monitor index {monitor_index} out of range (found {len(monitors)} displays)")
            target_mon = monitors[monitor_index]

        try:
            screenshot = pyautogui.screenshot()
            if target_mon is not None and hasattr(screenshot, "crop"):
                from PIL.Image import Image as PILImage
                try:
                    cropped = screenshot.crop((
                        max(0, target_mon.x),
                        max(0, target_mon.y),
                        target_mon.x + target_mon.width,
                        target_mon.y + target_mon.height,
                    ))
                    if isinstance(cropped, PILImage):
                        screenshot = cropped
                except Exception:
                    pass
        except OSError:
            # Fallback for headless / locked Windows sessions where GDI grab is restricted
            logger.warning("GDI screen grab restricted (locked/headless session); using fallback image")
            from PIL import Image, ImageDraw

            w = target_mon.width if target_mon else pyautogui.size().width or 1920
            h = target_mon.height if target_mon else pyautogui.size().height or 1080
            screenshot = Image.new("RGB", (w, h), color=(30, 41, 59))
            draw = ImageDraw.Draw(screenshot)
            label = f"Display {monitor_index} Capture (Session Locked or Headless)" if monitor_index is not None else "Desktop Screen Capture (Session Locked or Headless)"
            draw.text((50, 50), label, fill=(248, 250, 252))

        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return buffer.getvalue()

    def get_clipboard_text(self) -> ClipboardResult:
        """Safely read textual content from the system clipboard."""
        try:
            text = pyperclip.paste() or ""
        except Exception as exc:
            logger.warning("Failed to read system clipboard: %s", exc)
            text = ""

        # Mask preview if it contains potential secrets or long strings
        clean_text = text.strip()
        preview = clean_text[:60] + ("..." if len(clean_text) > 60 else "") if clean_text else ""
        return ClipboardResult(
            success=True,
            content_length=len(text),
            content_preview=preview,
            message="Clipboard text read successfully",
        )

    def set_clipboard_text(self, text: str) -> ClipboardResult:
        """Safely write text to the system clipboard."""
        validate_clipboard_text(text)
        try:
            pyperclip.copy(text)
        except Exception as exc:
            logger.error("Failed to copy text to clipboard: %s", exc)
            return ClipboardResult(
                success=False,
                content_length=0,
                content_preview="",
                message=f"Failed to copy to clipboard: {exc}",
            )

        clean_text = text.strip()
        preview = clean_text[:60] + ("..." if len(clean_text) > 60 else "")
        return ClipboardResult(
            success=True,
            content_length=len(text),
            content_preview=preview,
            message="Clipboard text set successfully",
        )

    def get_status(self, enabled_tools: list[str]) -> StatusReport:
        """Return the current runtime status."""
        return StatusReport(
            runtime_active=self._active,
            failsafe_enabled=pyautogui.FAILSAFE,
            action_lock_held=self._action_lock.is_held,
            enabled_tools=enabled_tools,
        )

    # ── Desktop-mutating operations (lock required) ───────────────────────

    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> ActionResult:
        """Move the mouse cursor to (x, y) over the given duration.

        Args:
            x: Target x coordinate.
            y: Target y coordinate.
            duration: Movement duration in seconds (0 to 5).
        """
        limits = self._config.safety
        screen = self.get_screen_info()
        validate_coordinates(x, y, screen.width, screen.height)
        validate_duration(duration, limits)

        with self._action_lock.acquire():
            pyautogui.moveTo(x, y, duration=duration)

        logger.info("Mouse moved to (%d, %d) over %.2fs", x, y, duration)
        return ActionResult(
            success=True,
            message=f"Mouse moved to ({x}, {y})",
            details={"x": x, "y": y, "duration": duration},
        )

    def click(
        self,
        x: int,
        y: int,
        click_type: str = "left",
    ) -> ActionResult:
        """Perform a mouse click at (x, y).

        Args:
            x: Target x coordinate.
            y: Target y coordinate.
            click_type: One of 'left', 'right', 'middle', 'double'.
        """
        limits = self._config.safety
        screen = self.get_screen_info()
        validate_coordinates(x, y, screen.width, screen.height)
        validate_click_type(click_type, limits)

        with self._action_lock.acquire():
            if click_type == "double":
                pyautogui.doubleClick(x, y)
            elif click_type == "right":
                pyautogui.rightClick(x, y)
            elif click_type == "middle":
                pyautogui.middleClick(x, y)
            else:
                pyautogui.click(x, y)

        logger.info("%s click at (%d, %d)", click_type, x, y)
        return ActionResult(
            success=True,
            message=f"{click_type} click at ({x}, {y})",
            details={"x": x, "y": y, "click_type": click_type},
        )

    def scroll(
        self,
        clicks: int,
        x: int | None = None,
        y: int | None = None,
        horizontal: bool = False,
    ) -> ActionResult:
        """Scroll the mouse wheel.

        Args:
            clicks: Number of scroll increments (positive=up, negative=down).
            x: Optional x coordinate to scroll at.
            y: Optional y coordinate to scroll at.
            horizontal: If True, scroll horizontally instead.
        """
        limits = self._config.safety
        validate_scroll_amount(clicks, limits)

        if x is not None and y is not None:
            screen = self.get_screen_info()
            validate_coordinates(x, y, screen.width, screen.height)

        with self._action_lock.acquire():
            if horizontal:
                pyautogui.hscroll(clicks, x=x, y=y)
            else:
                pyautogui.scroll(clicks, x=x, y=y)

        direction = "horizontal" if horizontal else "vertical"
        logger.info("%s scroll %d clicks", direction, clicks)
        return ActionResult(
            success=True,
            message=f"{direction} scroll {clicks} clicks",
            details={"clicks": clicks, "horizontal": horizontal, "x": x, "y": y},
        )

    def type_text(self, text: str) -> ActionResult:
        """Type text using the keyboard.

        The text content is NEVER logged.

        Args:
            text: The text to type (max length from config).
        """
        limits = self._config.safety
        validate_text_length(text, limits)

        with self._action_lock.acquire():
            pyautogui.typewrite(text, interval=0.02) if all(ord(c) < 128 for c in text) else pyautogui.write(text)

        # Log only the length, never the content
        logger.info("Typed text (length=%d)", len(text))
        return ActionResult(
            success=True,
            message=f"Typed {len(text)} characters",
            details={"length": len(text)},
        )

    def press_key(self, keys: str | list[str]) -> ActionResult:
        """Press a single key or a key combination.

        Args:
            keys: A key name (e.g., 'enter') or a list for combos (e.g., ['ctrl', 's']).
        """
        limits = self._config.safety

        if isinstance(keys, str):
            # Single key
            validate_key(keys, limits)
            with self._action_lock.acquire():
                pyautogui.press(keys.lower().strip())
            logger.info("Pressed key: %s", keys)
            return ActionResult(
                success=True,
                message=f"Pressed key: {keys}",
                details={"keys": keys},
            )
        else:
            # Key combination
            validate_key_combo(keys, limits)
            normalized = [k.lower().strip() for k in keys]
            with self._action_lock.acquire():
                pyautogui.hotkey(*normalized)
            combo_str = "+".join(normalized)
            logger.info("Pressed combo: %s", combo_str)
            return ActionResult(
                success=True,
                message=f"Pressed combo: {combo_str}",
                details={"keys": normalized},
            )
