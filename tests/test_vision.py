"""Unit tests for visual verification subsystem."""

from __future__ import annotations

import io
from PIL import Image, ImageDraw
import pytest

from local_computer_autopilot.vision.models import BoundingBox
from local_computer_autopilot.vision.verifier import (
    compare_images,
    crop_region,
    locate_template,
    wait_for_visual_change,
)


def _create_test_image(color=(255, 255, 255), width=200, height=200) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_rectangle(img_bytes: bytes, xy: tuple[int, int, int, int], fill=(255, 0, 0)) -> bytes:
    with Image.open(io.BytesIO(img_bytes)) as img:
        img_copy = img.copy()
        draw = ImageDraw.Draw(img_copy)
        draw.rectangle(xy, fill=fill)
        buf = io.BytesIO()
        img_copy.save(buf, format="PNG")
        return buf.getvalue()


class TestVisionCrop:
    def test_crop_valid_region(self):
        base = _create_test_image(width=100, height=100)
        cropped_bytes = crop_region(base, BoundingBox(x=10, y=10, width=50, height=50))
        with Image.open(io.BytesIO(cropped_bytes)) as cropped:
            assert cropped.size == (50, 50)

    def test_crop_exceeding_bounds(self):
        base = _create_test_image(width=100, height=100)
        cropped_bytes = crop_region(base, BoundingBox(x=80, y=80, width=50, height=50))
        with Image.open(io.BytesIO(cropped_bytes)) as cropped:
            # Should be clamped within 100x100
            assert cropped.size == (20, 20)


class TestVisionCompare:
    def test_identical_images(self):
        img1 = _create_test_image((100, 100, 100))
        img2 = _create_test_image((100, 100, 100))
        res = compare_images(img1, img2)
        assert res.has_changed is False
        assert res.diff_ratio == 0.0
        assert res.changed_bbox is None

    def test_different_images(self):
        img1 = _create_test_image((0, 0, 0), width=100, height=100)
        # Draw a 20x20 red square in 100x100 image (4% of pixels)
        img2 = _draw_rectangle(img1, (10, 10, 30, 30), fill=(255, 0, 0))

        res = compare_images(img1, img2, threshold=0.01)
        assert res.has_changed is True
        assert res.diff_ratio > 0.01
        assert res.changed_bbox is not None
        assert res.changed_bbox.x >= 10
        assert res.changed_bbox.y >= 10

    def test_threshold_suppresses_small_changes(self):
        img1 = _create_test_image((0, 0, 0), width=100, height=100)
        # Draw a tiny 2x2 box (0.04% of pixels)
        img2 = _draw_rectangle(img1, (10, 10, 12, 12), fill=(255, 0, 0))

        res = compare_images(img1, img2, threshold=0.05)
        # diff_ratio is ~0.0004, which is below 0.05
        assert res.has_changed is False
        assert res.diff_ratio < 0.05

    def test_compare_with_roi(self):
        img1 = _create_test_image((0, 0, 0), width=200, height=200)
        # Draw rectangle at 150, 150
        img2 = _draw_rectangle(img1, (150, 150, 180, 180), fill=(255, 255, 255))

        # Check an ROI at 0, 0, 100, 100 where no change happened
        roi_no_change = BoundingBox(x=0, y=0, width=100, height=100)
        res_no = compare_images(img1, img2, bbox=roi_no_change)
        assert res_no.has_changed is False

        # Check ROI at 140, 140, 60, 60 where change occurred
        roi_changed = BoundingBox(x=140, y=140, width=60, height=60)
        res_yes = compare_images(img1, img2, bbox=roi_changed)
        assert res_yes.has_changed is True


class TestVisionWait:
    def test_wait_succeeds_when_change_happens(self):
        baseline = _create_test_image((0, 0, 0), width=100, height=100)
        changed = _draw_rectangle(baseline, (10, 10, 50, 50), fill=(255, 255, 255))

        calls = [baseline, baseline, changed]

        def get_screen():
            if len(calls) > 1:
                return calls.pop(0)
            return calls[0]

        res = wait_for_visual_change(
            get_screenshot_fn=get_screen,
            before_bytes=baseline,
            threshold=0.01,
            timeout=1.0,
            poll_interval=0.05,
        )
        assert res.has_changed is True
        assert "Visual change confirmed" in res.message

    def test_wait_times_out_when_no_change(self):
        baseline = _create_test_image((0, 0, 0), width=50, height=50)

        res = wait_for_visual_change(
            get_screenshot_fn=lambda: baseline,
            before_bytes=baseline,
            threshold=0.01,
            timeout=0.2,
            poll_interval=0.05,
        )
        assert res.has_changed is False
        assert "Timed out" in res.message


class TestVisionLocate:
    def test_locate_template_success(self):
        # Create a haystack image
        haystack = _create_test_image((20, 30, 40), width=100, height=100)
        # Create a distinct 10x10 needle
        needle = _create_test_image((255, 100, 50), width=10, height=10)
        # Paste needle at (25, 35) in haystack
        with Image.open(io.BytesIO(haystack)) as h_img, Image.open(io.BytesIO(needle)) as n_img:
            h_img.paste(n_img, (25, 35))
            buf = io.BytesIO()
            h_img.save(buf, format="PNG")
            haystack_with_needle = buf.getvalue()

        result = locate_template(haystack_with_needle, needle)
        assert result.found is True
        assert result.x == 25 + 5
        assert result.y == 35 + 5
        assert result.box is not None
        assert result.box.x == 25
        assert result.box.y == 35
        assert result.box.width == 10
        assert result.box.height == 10

    def test_locate_template_not_found(self):
        haystack = _create_test_image((0, 0, 0), width=50, height=50)
        needle = _create_test_image((255, 255, 255), width=10, height=10)
        result = locate_template(haystack, needle)
        assert result.found is False
        assert result.x is None
        assert "not located" in result.message

    def test_locate_template_with_roi(self):
        haystack = _create_test_image((0, 0, 0), width=100, height=100)
        needle = _create_test_image((255, 0, 0), width=10, height=10)
        with Image.open(io.BytesIO(haystack)) as h_img, Image.open(io.BytesIO(needle)) as n_img:
            h_img.paste(n_img, (60, 60))
            buf = io.BytesIO()
            h_img.save(buf, format="PNG")
            haystack_with_needle = buf.getvalue()

        # ROI covering 50, 50, 40, 40
        roi = BoundingBox(x=50, y=50, width=40, height=40)
        result = locate_template(haystack_with_needle, needle, bbox=roi)
        assert result.found is True
        assert result.x == 65
        assert result.y == 65
