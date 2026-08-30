"""
Shared screen-boundary / spacing constraints.

This module is the single place that decides "will N things of size S fit
in width W" — every component that lays out a row/grid of elements calls
into here rather than reimplementing the arithmetic (and risking getting
it wrong in one template but not another).
"""
from __future__ import annotations

from dataclasses import dataclass

from manim_engine.renderer.config import (
    MAX_CONTENT_HEIGHT,
    MAX_CONTENT_WIDTH,
    MIN_CELL_SIZE,
)


@dataclass(frozen=True)
class FitResult:
    cell_size: float
    total_width: float
    shrunk: bool  # True if we had to shrink below the requested size
    below_min: bool  # True if even the shrunk size is below legibility floor


def fit_row(
    count: int,
    requested_size: float,
    *,
    max_width: float = MAX_CONTENT_WIDTH,
    spacing_ratio: float = 0.15,
) -> FitResult:
    """
    Compute the cell size for `count` equally-sized cells in a row so the
    row never exceeds `max_width`. `spacing_ratio` reserves gap space
    between cells as a fraction of cell size.

    This is the single highest-leverage fix for the "objects run
    off-screen" failure mode (README §10) — called from every component's
    __init__/build(), never left to the template author to get right.
    """
    if count <= 0:
        return FitResult(requested_size, 0.0, False, False)

    # total_width = count * size + (count - 1) * (size * spacing_ratio)
    # solve for size given total_width == max_width
    denom = count + (count - 1) * spacing_ratio
    max_size_that_fits = max_width / denom if denom > 0 else requested_size

    size = min(requested_size, max_size_that_fits)
    shrunk = size < requested_size
    below_min = size < MIN_CELL_SIZE

    total_width = count * size + (count - 1) * (size * spacing_ratio)
    return FitResult(cell_size=size, total_width=total_width, shrunk=shrunk, below_min=below_min)


def fit_grid(
    rows: int,
    cols: int,
    requested_size: float,
    *,
    max_width: float = MAX_CONTENT_WIDTH,
    max_height: float = MAX_CONTENT_HEIGHT,
    spacing_ratio: float = 0.2,
) -> FitResult:
    """Same idea as fit_row but bounded on both axes (trees, graphs)."""
    row_fit = fit_row(cols, requested_size, max_width=max_width, spacing_ratio=spacing_ratio)
    col_fit = fit_row(rows, requested_size, max_width=max_height, spacing_ratio=spacing_ratio)
    size = min(row_fit.cell_size, col_fit.cell_size)
    shrunk = size < requested_size
    below_min = size < MIN_CELL_SIZE
    return FitResult(cell_size=size, total_width=size * cols, shrunk=shrunk, below_min=below_min)


def clamp_position(x: float, y: float, *, half_width: float = MAX_CONTENT_WIDTH / 2,
                    half_height: float = MAX_CONTENT_HEIGHT / 2) -> tuple[float, float]:
    """Last-resort clamp for any computed position, so a layout bug in one
    component can't push a mobject off-frame even if the size math above
    was somehow bypassed."""
    return (
        max(-half_width, min(half_width, x)),
        max(-half_height, min(half_height, y)),
    )
