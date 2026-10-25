"""Reliable execution utilities: retries with backoff and timeouts."""

from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import Any, Callable, TypeVar

from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.execution.cancellation import CancellationToken

logger = logging.getLogger("local_computer_autopilot.execution")

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    cancellation_token: CancellationToken | None = None,
) -> T:
    """Execute a callable with exponential backoff on transient failure.

    Checks cancellation token before each retry.
    """
    delay = initial_delay
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        if cancellation_token:
            cancellation_token.check_cancelled()

        try:
            return fn()
        except retryable_exceptions as e:
            last_exception = e
            if attempt == max_retries:
                logger.warning(
                    "Exhausted all %d retry attempts. Final error: %s",
                    max_retries,
                    e,
                )
                raise

            logger.info(
                "Attempt %d/%d failed with %s: %s. Retrying in %.2fs...",
                attempt,
                max_retries,
                type(e).__name__,
                e,
                delay,
            )

            # Sleep in small increments to allow responsive cancellation
            sleep_end = time.time() + delay
            while time.time() < sleep_end:
                if cancellation_token:
                    cancellation_token.check_cancelled()
                time.sleep(min(0.05, max(0.0, sleep_end - time.time())))

            delay *= backoff_factor

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected failure in retry loop")


def run_with_timeout(
    fn: Callable[[], T],
    timeout_seconds: float = 10.0,
    cancellation_token: CancellationToken | None = None,
) -> T:
    """Run a callable with a strict bounded timeout using a thread worker."""
    if cancellation_token:
        cancellation_token.check_cancelled()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as e:
        logger.error("Operation exceeded hard timeout of %.2fs", timeout_seconds)
        executor.shutdown(wait=False, cancel_futures=True)
        raise SafetyError(f"Operation timed out after {timeout_seconds:.1f}s") from e
    finally:
        executor.shutdown(wait=False)
