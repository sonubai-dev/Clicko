"""Vision and visual verification subsystem."""

from local_computer_autopilot.vision.models import (
    BoundingBox,
    TemplateLocateResult,
    VisualDiffResult,
)
from local_computer_autopilot.vision.verifier import (
    compare_images,
    crop_region,
    locate_template,
    wait_for_visual_change,
)

__all__ = [
    "BoundingBox",
    "TemplateLocateResult",
    "VisualDiffResult",
    "compare_images",
    "crop_region",
    "locate_template",
    "wait_for_visual_change",
]
