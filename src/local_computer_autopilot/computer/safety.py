"""Safety validation and concurrency controls."""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Generator

from local_computer_autopilot.config import SafetyLimits

logger = logging.getLogger("local_computer_autopilot.safety")


class SafetyError(Exception):
    """Raised when a safety validation check fails."""


class ActionLock:
    """Prevents concurrent conflicting desktop actions using a non-blocking lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def is_held(self) -> bool:
        """Check whether the lock is currently held (non-blocking peek)."""
        if self._lock.acquire(blocking=False):
            self._lock.release()
            return False
        return True

    @contextmanager
    def acquire(self) -> Generator[None, None, None]:
        """Acquire the action lock; raises SafetyError if already held."""
        if not self._lock.acquire(blocking=False):
            raise SafetyError(
                "Another desktop action is already in progress. "
                "Wait for it to complete before starting a new one."
            )
        try:
            yield
        finally:
            self._lock.release()


def validate_coordinates(
    x: int, y: int, screen_width: int, screen_height: int
) -> None:
    """Validate that coordinates are within screen bounds.

    Raises SafetyError if coordinates are out of bounds.
    """
    if not isinstance(x, int) or not isinstance(y, int):
        raise SafetyError(f"Coordinates must be integers, got x={type(x).__name__}, y={type(y).__name__}")
    if x < 0 or x >= screen_width:
        raise SafetyError(
            f"x={x} is out of bounds (valid range: 0 to {screen_width - 1})"
        )
    if y < 0 or y >= screen_height:
        raise SafetyError(
            f"y={y} is out of bounds (valid range: 0 to {screen_height - 1})"
        )


def validate_click_type(click_type: str, limits: SafetyLimits) -> None:
    """Validate that the click type is in the allowlist.

    Raises SafetyError for unknown click types.
    """
    if click_type not in limits.allowed_click_types:
        allowed = ", ".join(sorted(limits.allowed_click_types))
        raise SafetyError(
            f"Click type '{click_type}' is not allowed. "
            f"Allowed types: {allowed}"
        )


def validate_duration(duration: float, limits: SafetyLimits) -> None:
    """Validate that a movement duration is within bounds.

    Raises SafetyError if the duration is out of the allowed range.
    """
    if not isinstance(duration, (int, float)):
        raise SafetyError(f"Duration must be a number, got {type(duration).__name__}")
    if duration < limits.min_move_duration or duration > limits.max_move_duration:
        raise SafetyError(
            f"Duration {duration}s is out of bounds "
            f"(valid range: {limits.min_move_duration} to {limits.max_move_duration}s)"
        )


def validate_text_length(text: str, limits: SafetyLimits) -> None:
    """Validate that the text does not exceed the maximum allowed length.

    Never logs the text content itself.
    Raises SafetyError if the text is too long or empty.
    """
    if not isinstance(text, str):
        raise SafetyError(f"Text must be a string, got {type(text).__name__}")
    if len(text) == 0:
        raise SafetyError("Text must not be empty")
    if len(text) > limits.max_text_length:
        raise SafetyError(
            f"Text length {len(text)} exceeds maximum of {limits.max_text_length} characters"
        )
    # Log only the length, NEVER the content
    logger.debug("Text validated: length=%d", len(text))


def validate_scroll_amount(clicks: int, limits: SafetyLimits) -> None:
    """Validate that a scroll amount is within bounds.

    Raises SafetyError if the scroll amount is out of bounds.
    """
    if not isinstance(clicks, int):
        raise SafetyError(f"Scroll clicks must be an integer, got {type(clicks).__name__}")
    if abs(clicks) > limits.max_scroll_clicks:
        raise SafetyError(
            f"Scroll amount {clicks} exceeds maximum of ±{limits.max_scroll_clicks} clicks"
        )


def validate_key(key: str, limits: SafetyLimits) -> None:
    """Validate that a single key name is in the allowlist.

    Raises SafetyError if the key is not recognized.
    """
    if not isinstance(key, str):
        raise SafetyError(f"Key must be a string, got {type(key).__name__}")
    key_lower = key.lower().strip()
    if not key_lower:
        raise SafetyError("Key name must not be empty")
    if key_lower not in limits.allowed_keys:
        raise SafetyError(
            f"Key '{key}' is not in the allowlist. "
            f"See documentation for allowed key names."
        )


def validate_key_combo(keys: list[str], limits: SafetyLimits) -> None:
    """Validate a key combination (e.g., ['ctrl', 'shift', 's']).

    Raises SafetyError if any key is invalid or the combo exceeds the max size.
    """
    if not isinstance(keys, list):
        raise SafetyError(f"Key combo must be a list, got {type(keys).__name__}")
    if len(keys) == 0:
        raise SafetyError("Key combo must not be empty")
    if len(keys) > limits.max_combo_keys:
        raise SafetyError(
            f"Key combo has {len(keys)} keys, exceeding maximum of {limits.max_combo_keys}"
        )
    for key in keys:
        validate_key(key, limits)


def validate_clipboard_text(text: str, max_length: int = 5000) -> None:
    """Validate text intended for clipboard writing.

    Raises SafetyError if invalid or exceeding length bounds.
    """
    if not isinstance(text, str):
        raise SafetyError(f"Clipboard text must be a string, got {type(text).__name__}")
    if len(text) > max_length:
        raise SafetyError(
            f"Clipboard text length {len(text)} exceeds maximum allowed {max_length} characters"
        )


def validate_coordinates_in_monitors(
    x: int, y: int, monitor_boxes: list[tuple[int, int, int, int]]
) -> None:
    """Validate that coordinates fall inside at least one monitor boundary.

    monitor_boxes is a list of (left, top, right, bottom) tuples.
    Raises SafetyError if (x, y) is not contained in any active monitor.
    """
    if not isinstance(x, int) or not isinstance(y, int):
        raise SafetyError(f"Coordinates must be integers, got x={type(x).__name__}, y={type(y).__name__}")
    for left, top, right, bottom in monitor_boxes:
        if left <= x < right and top <= y < bottom:
            return
    raise SafetyError(
        f"Coordinates ({x}, {y}) fall outside all configured monitor bounds"
    )
