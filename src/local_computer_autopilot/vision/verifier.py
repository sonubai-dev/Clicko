"""Visual verification logic using Pillow."""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from typing import Callable

from PIL import Image, ImageChops, ImageStat
import pyscreeze

from local_computer_autopilot.vision.models import BoundingBox, TemplateLocateResult, VisualDiffResult

logger = logging.getLogger("local_computer_autopilot.vision")


def crop_region(image_bytes: bytes, bbox: BoundingBox) -> bytes:
    """Crop an in-memory image to the specified bounding box."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img_w, img_h = img.size
        # Constrain bbox within image bounds
        left = max(0, min(bbox.x, img_w - 1))
        top = max(0, min(bbox.y, img_h - 1))
        right = max(left + 1, min(bbox.x + bbox.width, img_w))
        bottom = max(top + 1, min(bbox.y + bbox.height, img_h))

        cropped = img.crop((left, top, right, bottom))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()


def compare_images(
    before_bytes: bytes,
    after_bytes: bytes,
    bbox: BoundingBox | None = None,
    threshold: float = 0.01,
) -> VisualDiffResult:
    """Compare two images (or sub-regions) and compute difference ratio.

    Args:
        before_bytes: Baseline PNG bytes.
        after_bytes: Secondary PNG bytes to compare against.
        bbox: Optional sub-region to crop and inspect.
        threshold: Fraction of changed pixels considered a meaningful change (0.0 to 1.0).
    """
    if bbox is not None:
        before_bytes = crop_region(before_bytes, bbox)
        after_bytes = crop_region(after_bytes, bbox)

    with Image.open(io.BytesIO(before_bytes)) as img_before, Image.open(
        io.BytesIO(after_bytes)
    ) as img_after:
        # Convert to RGB to ensure compatible channels
        img1 = img_before.convert("RGB")
        img2 = img_after.convert("RGB")

        # Resize if dimensions differ slightly
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)

        diff = ImageChops.difference(img1, img2)
        diff_box = diff.getbbox()

        if diff_box is None:
            return VisualDiffResult(
                has_changed=False,
                diff_ratio=0.0,
                changed_bbox=None,
                message="Images are pixel-identical",
            )

        # Convert diff to grayscale to count non-zero pixels
        diff_gray = diff.convert("L")
        stat = ImageStat.Stat(diff_gray)
        # Fraction of pixels with noticeable difference (> 5 intensity)
        hist = diff_gray.histogram()
        zero_count = hist[0] if len(hist) > 0 else 0
        total_pixels = img1.width * img1.height
        non_zero_pixels = total_pixels - zero_count
        diff_ratio = max(0.0, min(1.0, non_zero_pixels / float(total_pixels)))

        has_changed = diff_ratio >= threshold

        offset_x = bbox.x if bbox else 0
        offset_y = bbox.y if bbox else 0
        changed_bbox = BoundingBox(
            x=diff_box[0] + offset_x,
            y=diff_box[1] + offset_y,
            width=diff_box[2] - diff_box[0],
            height=diff_box[3] - diff_box[1],
        )

        msg = (
            f"Visual change detected ({diff_ratio:.2%} changed)"
            if has_changed
            else f"No significant change ({diff_ratio:.2%} changed, threshold is {threshold:.2%})"
        )

        logger.debug(msg)
        return VisualDiffResult(
            has_changed=has_changed,
            diff_ratio=round(diff_ratio, 4),
            changed_bbox=changed_bbox,
            message=msg,
        )


def wait_for_visual_change(
    get_screenshot_fn: Callable[[], bytes],
    before_bytes: bytes,
    bbox: BoundingBox | None = None,
    threshold: float = 0.01,
    timeout: float = 3.0,
    poll_interval: float = 0.2,
) -> VisualDiffResult:
    """Poll for a visual change against a baseline screenshot until timeout.

    Args:
        get_screenshot_fn: Callable returning current screenshot bytes.
        before_bytes: Baseline screenshot bytes.
        bbox: Optional region to observe.
        threshold: Change ratio threshold.
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between polls.
    """
    start_time = time.time()
    last_result = VisualDiffResult(
        has_changed=False,
        diff_ratio=0.0,
        changed_bbox=None,
        message="Initial baseline",
    )

    while (time.time() - start_time) < timeout:
        current_bytes = get_screenshot_fn()
        last_result = compare_images(
            before_bytes, current_bytes, bbox=bbox, threshold=threshold
        )
        if last_result.has_changed:
            elapsed = time.time() - start_time
            last_result.message = (
                f"Visual change confirmed after {elapsed:.2f}s ({last_result.diff_ratio:.2%})"
            )
            return last_result
        time.sleep(poll_interval)

    elapsed = time.time() - start_time
    last_result.message = (
        f"Timed out after {elapsed:.2f}s waiting for visual change (max diff was {last_result.diff_ratio:.2%})"
    )
    return last_result


def load_image_source(source: str | bytes) -> Image.Image:
    """Load a PIL Image from file path, raw bytes, or base64-encoded string."""
    if isinstance(source, bytes):
        return Image.open(io.BytesIO(source))
    if isinstance(source, str):
        if os.path.isfile(source):
            return Image.open(source)
        # Try base64
        raw = source.strip()
        if "," in raw and "base64" in raw:
            raw = raw.split(",", 1)[1]
        try:
            decoded = base64.b64decode(raw)
            return Image.open(io.BytesIO(decoded))
        except Exception as exc:
            raise ValueError(f"Could not load image from string (not a valid file path or base64): {exc}")
    raise ValueError(f"Unsupported image source type: {type(source).__name__}")


def locate_template(
    haystack_bytes: bytes,
    needle_source: str | bytes,
    bbox: BoundingBox | None = None,
    confidence: float = 0.9,
) -> TemplateLocateResult:
    """Locate a template needle image within the haystack screenshot image.

    Args:
        haystack_bytes: The screen image as PNG bytes.
        needle_source: File path, base64 string, or bytes of template to find.
        bbox: Optional search region of interest (ROI).
        confidence: Match confidence (0.1 to 1.0).
    """
    try:
        needle_img = load_image_source(needle_source).convert("RGB")
    except Exception as exc:
        return TemplateLocateResult(
            found=False,
            message=f"Failed to load needle template image: {exc}",
        )

    try:
        with Image.open(io.BytesIO(haystack_bytes)) as full_haystack:
            haystack_img = full_haystack.convert("RGB")
            offset_x = 0
            offset_y = 0

            if bbox is not None:
                offset_x = bbox.x
                offset_y = bbox.y
                haystack_img = haystack_img.crop((
                    bbox.x,
                    bbox.y,
                    bbox.x + bbox.width,
                    bbox.y + bbox.height,
                ))

            try:
                # Attempt locate with confidence if supported (requires OpenCV), otherwise exact Pillow match
                try:
                    box = pyscreeze.locate(needle_img, haystack_img, confidence=confidence)
                except (TypeError, NotImplementedError):
                    box = pyscreeze.locate(needle_img, haystack_img)
            except Exception:
                box = None

            if box is None:
                return TemplateLocateResult(
                    found=False,
                    message="Template image was not located in screen area",
                )

            # Calculate match coordinates in global screen space
            match_x = int(box.left + offset_x)
            match_y = int(box.top + offset_y)
            match_w = int(box.width)
            match_h = int(box.height)
            center_x = match_x + match_w // 2
            center_y = match_y + match_h // 2

            matched_bbox = BoundingBox(
                x=match_x,
                y=match_y,
                width=match_w,
                height=match_h,
            )

            return TemplateLocateResult(
                found=True,
                x=center_x,
                y=center_y,
                box=matched_bbox,
                confidence=confidence,
                message=f"Template located at center ({center_x}, {center_y})",
            )
    except Exception as exc:
        logger.error("Error during template locate: %s", exc)
        return TemplateLocateResult(
            found=False,
            message=f"Template match error: {exc}",
        )
