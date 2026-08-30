"""
DPTableVisualizer: a row of cells (like ArrayVisualizer) that start
empty and fill in one at a time with computed DP values, optionally
drawing a small dependency arrow from the cell(s) a new value was derived
from — this is the one visual difference from plain array_traversal that
justifies a dedicated component rather than reusing ArrayVisualizer
directly: the "empty until computed" state and the dependency arrows are
specific to how a DP table is explained, not how a plain array is walked.

Used by: dynamic_programming_1d.
"""
from __future__ import annotations

from manim import Arrow, FadeIn, Text

from manim_engine.components.arrays.array_visualizer import ArrayVisualizer
from manim_engine.renderer.config import COLOR_TEXT_MUTED, COLOR_TEXT_PRIMARY, FONT_SIZE_CELL, SEMANTIC_COLORS


class DPTableVisualizer(ArrayVisualizer):
    """Extends ArrayVisualizer: cells start showing a muted placeholder
    ('·') instead of their eventual value, filled in via fill_cell()."""

    def __init__(self, size: int, **kwargs):
        # Build with placeholder zeros; labels get swapped to a dim '·'
        # right after construction so cell layout math is identical to a
        # normal array (same sizing/boundary-protection guarantees).
        super().__init__([0] * size, **kwargs)
        for label in self.labels:
            label.become(
                Text("·", font_size=FONT_SIZE_CELL, color=COLOR_TEXT_MUTED).move_to(label.get_center())
            )
        self.filled: set[int] = set()

    def fill_cell(self, index: int, value: int, depends_on: list[int] | None = None):
        anims = []
        old_label = self.labels[index]
        font_size = min(FONT_SIZE_CELL, int(self._cell_size * 34)) or 10
        new_label = Text(str(value), font_size=max(font_size, 10), color=COLOR_TEXT_PRIMARY)
        new_label.move_to(old_label.get_center())
        anims.append(old_label.animate.become(new_label))
        self.values[index] = value
        self.filled.add(index)

        anims += self.highlight([index], "highlight")

        dep_arrows = []
        for dep in depends_on or []:
            if dep == index or dep < 0 or dep >= len(self.cells):
                continue
            arrow = Arrow(
                start=self.cell_center(dep), end=self.cell_center(index),
                color=SEMANTIC_COLORS["secondary"], buff=self._cell_size / 2,
                stroke_width=2, max_tip_length_to_length_ratio=0.15,
            )
            dep_arrows.append(arrow)
        for arrow in dep_arrows:
            self.add(arrow)
        anims += [FadeIn(a) for a in dep_arrows]

        return anims
