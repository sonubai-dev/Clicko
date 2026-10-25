"""Models for visual verification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Region of interest coordinates on screen."""
    x: int = Field(ge=0, description="Top-left X coordinate")
    y: int = Field(ge=0, description="Top-left Y coordinate")
    width: int = Field(gt=0, description="Width of bounding box")
    height: int = Field(gt=0, description="Height of bounding box")


class VisualDiffResult(BaseModel):
    """Result of comparing two visual states."""
    has_changed: bool = Field(description="True if difference ratio exceeds threshold")
    diff_ratio: float = Field(description="Fraction of pixels changed (0.0 to 1.0)")
    changed_bbox: BoundingBox | None = Field(default=None, description="Bounding box covering altered region")
    message: str = Field(default="", description="Descriptive status message")


class TemplateLocateResult(BaseModel):
    """Result of locating a template image on screen."""
    found: bool = Field(description="True if template was located")
    x: int | None = Field(default=None, description="Center X coordinate of match")
    y: int | None = Field(default=None, description="Center Y coordinate of match")
    box: BoundingBox | None = Field(default=None, description="Bounding box of matched region")
    confidence: float = Field(default=1.0, description="Match confidence or threshold")
    message: str = Field(default="", description="Descriptive result message")
