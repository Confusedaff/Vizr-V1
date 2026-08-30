"""Tests for manim_engine/renderer/layout.py boundary-protection math."""
from manim_engine.renderer.layout import MAX_CONTENT_WIDTH, fit_row


def test_small_count_uses_requested_size():
    result = fit_row(3, 0.9)
    assert result.cell_size == 0.9
    assert not result.shrunk


def test_large_count_shrinks_to_fit():
    result = fit_row(50, 0.9)
    assert result.shrunk
    assert result.total_width <= MAX_CONTENT_WIDTH + 1e-6


def test_total_width_never_exceeds_max():
    for n in [1, 5, 10, 20, 50]:
        result = fit_row(n, 0.9)
        assert result.total_width <= MAX_CONTENT_WIDTH + 1e-6, f"n={n} overflowed"


def test_single_element_row():
    result = fit_row(1, 0.9)
    assert result.cell_size == 0.9
    assert result.total_width == 0.9


def test_zero_count_handled_gracefully():
    result = fit_row(0, 0.9)
    assert result.total_width == 0.0


def test_below_legibility_floor_flagged_for_extreme_counts():
    result = fit_row(50, 0.9)
    # 50 elements in ~12.8 units of width will push cells very small
    assert result.cell_size < 0.9
