"""Cooperative cancellation token for safe runtime interruption."""

from __future__ import annotations

import threading

from local_computer_autopilot.computer.safety import SafetyError


class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason: str = ""

    def cancel(self, reason: str = "Operation cancelled by user or safety system") -> None:
        """Trigger cancellation."""
        self._reason = reason
        self._event.set()

    def reset(self) -> None:
        """Reset token to uncancelled state."""
        self._reason = ""
        self._event.clear()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._event.is_set()

    @property
    def reason(self) -> str:
        """Return the cancellation reason."""
        return self._reason

    def check_cancelled(self) -> None:
        """Raise SafetyError if cancellation was triggered."""
        if self._event.is_set():
            raise SafetyError(f"Action aborted: {self._reason}")
