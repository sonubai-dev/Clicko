"""Tests for safety validation and concurrency controls."""

from __future__ import annotations

import threading

import pytest

from local_computer_autopilot.computer.safety import (
    ActionLock,
    SafetyError,
    validate_click_type,
    validate_coordinates,
    validate_duration,
    validate_key,
    validate_key_combo,
    validate_scroll_amount,
    validate_text_length,
)
from local_computer_autopilot.config import SafetyLimits


# ── Coordinate validation ─────────────────────────────────────────────────


class TestValidateCoordinates:
    def test_valid_origin(self):
        validate_coordinates(0, 0, 1920, 1080)

    def test_valid_max(self):
        validate_coordinates(1919, 1079, 1920, 1080)

    def test_negative_x(self):
        with pytest.raises(SafetyError, match="x=-1 is out of bounds"):
            validate_coordinates(-1, 0, 1920, 1080)

    def test_negative_y(self):
        with pytest.raises(SafetyError, match="y=-1 is out of bounds"):
            validate_coordinates(0, -1, 1920, 1080)

    def test_x_at_boundary(self):
        with pytest.raises(SafetyError, match="x=1920 is out of bounds"):
            validate_coordinates(1920, 0, 1920, 1080)

    def test_y_at_boundary(self):
        with pytest.raises(SafetyError, match="y=1080 is out of bounds"):
            validate_coordinates(0, 1080, 1920, 1080)

    def test_x_far_out(self):
        with pytest.raises(SafetyError, match="x=9999 is out of bounds"):
            validate_coordinates(9999, 0, 1920, 1080)


# ── Click type validation ─────────────────────────────────────────────────


class TestValidateClickType:
    def test_all_allowed_types(self):
        limits = SafetyLimits()
        for ct in ("left", "right", "middle", "double"):
            validate_click_type(ct, limits)

    def test_unknown_type(self):
        limits = SafetyLimits()
        with pytest.raises(SafetyError, match="not allowed"):
            validate_click_type("triple", limits)

    def test_empty_type(self):
        limits = SafetyLimits()
        with pytest.raises(SafetyError, match="not allowed"):
            validate_click_type("", limits)


# ── Duration validation ───────────────────────────────────────────────────


class TestValidateDuration:
    def test_valid_zero(self):
        validate_duration(0.0, SafetyLimits())

    def test_valid_max(self):
        validate_duration(5.0, SafetyLimits())

    def test_valid_mid(self):
        validate_duration(2.5, SafetyLimits())

    def test_negative(self):
        with pytest.raises(SafetyError, match="out of bounds"):
            validate_duration(-0.1, SafetyLimits())

    def test_over_max(self):
        with pytest.raises(SafetyError, match="out of bounds"):
            validate_duration(5.1, SafetyLimits())


# ── Text length validation ────────────────────────────────────────────────


class TestValidateTextLength:
    def test_valid_short(self):
        validate_text_length("hello", SafetyLimits())

    def test_valid_max(self):
        validate_text_length("a" * 1000, SafetyLimits())

    def test_empty(self):
        with pytest.raises(SafetyError, match="must not be empty"):
            validate_text_length("", SafetyLimits())

    def test_over_max(self):
        with pytest.raises(SafetyError, match="exceeds maximum"):
            validate_text_length("a" * 1001, SafetyLimits())

    def test_way_over_max(self):
        with pytest.raises(SafetyError, match="exceeds maximum"):
            validate_text_length("a" * 10000, SafetyLimits())


# ── Scroll validation ─────────────────────────────────────────────────────


class TestValidateScrollAmount:
    def test_valid_positive(self):
        validate_scroll_amount(5, SafetyLimits())

    def test_valid_negative(self):
        validate_scroll_amount(-5, SafetyLimits())

    def test_valid_max(self):
        validate_scroll_amount(20, SafetyLimits())

    def test_valid_min(self):
        validate_scroll_amount(-20, SafetyLimits())

    def test_zero(self):
        validate_scroll_amount(0, SafetyLimits())

    def test_over_max(self):
        with pytest.raises(SafetyError, match="exceeds maximum"):
            validate_scroll_amount(21, SafetyLimits())

    def test_under_min(self):
        with pytest.raises(SafetyError, match="exceeds maximum"):
            validate_scroll_amount(-21, SafetyLimits())


# ── Key validation ─────────────────────────────────────────────────────────


class TestValidateKey:
    def test_valid_keys(self):
        limits = SafetyLimits()
        for key in ("enter", "tab", "space", "a", "f1", "ctrl", "alt", "shift"):
            validate_key(key, limits)

    def test_invalid_key(self):
        with pytest.raises(SafetyError, match="not in the allowlist"):
            validate_key("launch_missiles", SafetyLimits())

    def test_empty_key(self):
        with pytest.raises(SafetyError, match="must not be empty"):
            validate_key("", SafetyLimits())

    def test_case_insensitive(self):
        validate_key("ENTER", SafetyLimits())
        validate_key("Ctrl", SafetyLimits())


# ── Key combo validation ──────────────────────────────────────────────────


class TestValidateKeyCombo:
    def test_valid_combo(self):
        validate_key_combo(["ctrl", "s"], SafetyLimits())

    def test_valid_triple_combo(self):
        validate_key_combo(["ctrl", "shift", "s"], SafetyLimits())

    def test_empty_combo(self):
        with pytest.raises(SafetyError, match="must not be empty"):
            validate_key_combo([], SafetyLimits())

    def test_too_many_keys(self):
        with pytest.raises(SafetyError, match="exceeding maximum"):
            validate_key_combo(["ctrl", "alt", "shift", "win", "a"], SafetyLimits())

    def test_invalid_key_in_combo(self):
        with pytest.raises(SafetyError, match="not in the allowlist"):
            validate_key_combo(["ctrl", "nuke"], SafetyLimits())


# ── Action lock ────────────────────────────────────────────────────────────


class TestActionLock:
    def test_acquire_and_release(self):
        lock = ActionLock()
        assert not lock.is_held
        with lock.acquire():
            assert lock.is_held
        assert not lock.is_held

    def test_concurrent_acquire_fails(self):
        lock = ActionLock()
        with lock.acquire():
            with pytest.raises(SafetyError, match="already in progress"):
                lock.acquire().__enter__()

    def test_release_on_exception(self):
        lock = ActionLock()
        with pytest.raises(ValueError):
            with lock.acquire():
                raise ValueError("test error")
        # Lock should be released after exception
        assert not lock.is_held


# ── Text logging safety ───────────────────────────────────────────────────


class TestTextNotLogged:
    def test_text_not_in_log(self, caplog):
        """Ensure the actual text content is not written to logs."""
        secret_text = "MySecretPassword123!"
        with caplog.at_level("DEBUG", logger="local_computer_autopilot.safety"):
            validate_text_length(secret_text, SafetyLimits())
        for record in caplog.records:
            assert secret_text not in record.getMessage(), (
                f"Secret text leaked in log: {record.getMessage()}"
            )
