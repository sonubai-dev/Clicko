"""Unit tests for Reliable Execution subsystem."""

from __future__ import annotations

import time
import pytest

from local_computer_autopilot.computer.safety import SafetyError
from local_computer_autopilot.execution.cancellation import CancellationToken
from local_computer_autopilot.execution.retry import retry_with_backoff, run_with_timeout


class TestCancellationToken:
    def test_initial_state(self):
        token = CancellationToken()
        assert token.is_cancelled is False
        assert token.reason == ""
        # Should not raise
        token.check_cancelled()

    def test_cancel_triggers_abort(self):
        token = CancellationToken()
        token.cancel("User emergency stop")
        assert token.is_cancelled is True
        assert token.reason == "User emergency stop"

        with pytest.raises(SafetyError, match="Action aborted: User emergency stop"):
            token.check_cancelled()

    def test_reset(self):
        token = CancellationToken()
        token.cancel("Abort")
        token.reset()
        assert token.is_cancelled is False
        token.check_cancelled()


class TestRetryWithBackoff:
    def test_succeeds_first_attempt(self):
        mock_fn = pytest.mock = lambda: 42
        res = retry_with_backoff(mock_fn, max_retries=3)
        assert res == 42

    def test_succeeds_after_transient_failures(self):
        attempts = 0

        def flaky_fn():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionError("Transient network drop")
            return "recovered"

        res = retry_with_backoff(
            flaky_fn,
            max_retries=4,
            initial_delay=0.01,
            backoff_factor=1.5,
            retryable_exceptions=(ConnectionError,),
        )
        assert res == "recovered"
        assert attempts == 3

    def test_raises_when_retries_exhausted(self):
        def always_fails():
            raise ValueError("Permanent flaw")

        with pytest.raises(ValueError, match="Permanent flaw"):
            retry_with_backoff(
                always_fails,
                max_retries=2,
                initial_delay=0.01,
                retryable_exceptions=(ValueError,),
            )

    def test_aborts_on_cancellation(self):
        token = CancellationToken()
        token.cancel("Halt")

        def fn():
            return "ok"

        with pytest.raises(SafetyError, match="Action aborted: Halt"):
            retry_with_backoff(fn, cancellation_token=token)


class TestRunWithTimeout:
    def test_runs_within_timeout(self):
        def quick():
            return "done"

        res = run_with_timeout(quick, timeout_seconds=1.0)
        assert res == "done"

    def test_raises_on_timeout(self):
        def slow():
            time.sleep(0.5)
            return "late"

        with pytest.raises(SafetyError, match="timed out"):
            run_with_timeout(slow, timeout_seconds=0.1)

    def test_timeout_returns_promptly_without_blocking_on_thread(self):
        def long_sleep():
            time.sleep(2.0)
            return "never"

        start = time.time()
        with pytest.raises(SafetyError, match="timed out"):
            run_with_timeout(long_sleep, timeout_seconds=0.1)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"run_with_timeout took {elapsed:.2f}s, expected < 0.5s"

    def test_aborts_if_token_cancelled_before_run(self):
        token = CancellationToken()
        token.cancel("Cancelled before start")

        def fn():
            return "ok"

        with pytest.raises(SafetyError, match="Action aborted: Cancelled before start"):
            run_with_timeout(fn, timeout_seconds=1.0, cancellation_token=token)
