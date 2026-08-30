"""Tests for manim_engine/debug/frame_quality.py — validated during
development against real Manim renders, codified here as regression
tests so recalibrating a threshold later can't silently reintroduce the
false-positive issues found in that process (see module docstrings for
the calibration history)."""
import numpy as np
from PIL import Image

from manim_engine.debug.frame_quality import (
    Severity,
    analyze_frame,
    check_blank_frame,
    check_mobject_bbox_overlap,
    check_offscreen_clipping,
    check_overlap_density,
)

BG = (14, 17, 22)


def make_bg_frame(w=854, h=480):
    return np.full((h, w, 3), BG, dtype=np.uint8)


def test_blank_frame_detected():
    frame = make_bg_frame()
    issues = check_blank_frame(frame)
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_frame_with_content_not_flagged_blank():
    frame = make_bg_frame()
    frame[100:300, 100:300] = (245, 247, 250)
    issues = check_blank_frame(frame)
    assert issues == []


def test_offscreen_clipping_detected_at_right_edge():
    frame = make_bg_frame()
    frame[100:300, -10:] = (255, 255, 255)
    issues = check_offscreen_clipping(frame)
    assert any(i.check == "offscreen_clipping" for i in issues)


def test_no_clipping_for_centered_content():
    frame = make_bg_frame()
    frame[200:280, 400:454] = (255, 255, 255)  # well within a 854x480 frame
    issues = check_offscreen_clipping(frame)
    assert issues == []


def test_overlap_density_no_false_positive_on_solid_cells():
    """Regression test: a row of adjacent solid-filled cells (like
    ArrayVisualizer output) must NOT trigger the overlap-density check —
    this was a real false positive found during development."""
    img = Image.new("RGB", (854, 480), BG)
    import PIL.ImageDraw as ImageDraw

    d = ImageDraw.Draw(img)
    x = 100
    for _ in range(5):
        d.rectangle([x, 200, x + 80, 280], fill=(27, 34, 48), outline=(61, 74, 92), width=2)
        x += 90
    arr = np.asarray(img)
    issues = check_overlap_density(arr)
    assert issues == [], f"false positive: {[i.message for i in issues]}"


def test_mobject_bbox_overlap_detects_true_overlap():
    from manim import Rectangle

    a = Rectangle(width=0.9, height=0.9).move_to([0, 0, 0])
    b = Rectangle(width=0.9, height=0.9).move_to([0.2, 0, 0])  # heavy overlap
    issues = check_mobject_bbox_overlap([a, b])
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_mobject_bbox_overlap_no_false_positive_adjacent():
    from manim import Rectangle

    a = Rectangle(width=0.9, height=0.9).move_to([0, 0, 0])
    b = Rectangle(width=0.9, height=0.9).move_to([1.0, 0, 0])  # adjacent, not overlapping
    issues = check_mobject_bbox_overlap([a, b])
    assert issues == []


def test_analyze_frame_aggregates_all_checks():
    frame = make_bg_frame()
    report = analyze_frame(frame)
    assert report.has_errors  # blank frame triggers at minimum
