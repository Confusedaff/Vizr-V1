"""
ArrayVisualizer: a row of labeled cells representing an integer array.

Used directly by: array_traversal, two_sum, two_pointers, binary_search,
sliding_window, bubble_sort, merge_sort. This is the highest-leverage
component in the library — it's the one most exposed to "does this fit on
screen" failures at both extremes (single-element array, 50-element
array), so all boundary-protection logic is exercised here first and
tested explicitly (manim_engine/tests/test_components/test_array_visualizer.py).
"""
from __future__ import annotations

from manim import (
    BLACK,
    DOWN,
    UP,
    Create,
    FadeIn,
    FadeOut,
    Indicate,
    Rectangle,
    Text,
    VGroup,
)

from manim_engine.renderer.config import (
    COLOR_CELL_FILL,
    COLOR_CELL_STROKE,
    COLOR_TEXT_PRIMARY,
    DEFAULT_CELL_SIZE,
    DURATION_BUILD,
    DURATION_HIGHLIGHT,
    DURATION_SWAP,
    FONT_SIZE_CELL,
    SEMANTIC_COLORS,
)
from manim_engine.renderer.layout import fit_row


class ArrayVisualizer(VGroup):
    """
    Build: ArrayVisualizer(values).arrange_on_screen()
    Then use .highlight(indices, color), .clear_highlights(),
    .swap_cells(i, j), .cell_center(i) for pointer/label placement.
    """

    def __init__(self, values: list[int], **kwargs):
        super().__init__(**kwargs)
        self.values = list(values)
        self.cells: list[Rectangle] = []
        self.labels: list[Text] = []
        self._index_labels: list[Text] = []
        self._build()

    def _build(self) -> None:
        n = len(self.values)
        fit = fit_row(n, DEFAULT_CELL_SIZE)
        self._cell_size = fit.cell_size
        self._fit_warning = fit.shrunk
        self._below_legibility_floor = fit.below_min
        gap = self._cell_size * 0.15

        x_cursor = -fit.total_width / 2
        for i, val in enumerate(self.values):
            cell = Rectangle(
                width=self._cell_size,
                height=self._cell_size,
                fill_color=COLOR_CELL_FILL,
                fill_opacity=1.0,
                stroke_color=COLOR_CELL_STROKE,
                stroke_width=2,
            )
            cell.move_to([x_cursor + self._cell_size / 2, 0, 0])

            font_size = min(FONT_SIZE_CELL, int(self._cell_size * 34))
            label = Text(str(val), font_size=max(font_size, 10), color=COLOR_TEXT_PRIMARY)
            label.move_to(cell.get_center())

            idx_label = Text(str(i), font_size=max(int(self._cell_size * 16), 8), color=COLOR_TEXT_PRIMARY)
            idx_label.set_opacity(0.5)
            idx_label.next_to(cell, DOWN, buff=0.08)

            self.cells.append(cell)
            self.labels.append(label)
            self._index_labels.append(idx_label)
            self.add(cell, label, idx_label)

            x_cursor += self._cell_size + gap

    # -- introspection -----------------------------------------------------

    def cell_center(self, index: int):
        return self.cells[index].get_center()

    def has_fit_warning(self) -> bool:
        """True if cells had to shrink to fit — surfaced to the render
        manifest as a quality note even if the frame still passes checks."""
        return self._fit_warning

    def is_below_legibility_floor(self) -> bool:
        return self._below_legibility_floor

    # -- animations ----------------------------------------------------------

    def build_in(self):
        return Create(self, run_time=DURATION_BUILD)

    def highlight(self, indices: list[int], color_name: str = "highlight"):
        color = SEMANTIC_COLORS.get(color_name, SEMANTIC_COLORS["highlight"])
        anims = []
        for i in indices:
            anims.append(self.cells[i].animate.set_fill(color, opacity=1.0).set_stroke(color))
        return anims

    def clear_highlight(self, indices: list[int] | None = None):
        idxs = indices if indices is not None else range(len(self.cells))
        anims = []
        for i in idxs:
            anims.append(
                self.cells[i].animate.set_fill(COLOR_CELL_FILL, opacity=1.0).set_stroke(COLOR_CELL_STROKE)
            )
        return anims

    def indicate(self, indices: list[int]):
        return [Indicate(self.cells[i], color=SEMANTIC_COLORS["highlight"]) for i in indices]

    def swap_cells(self, i: int, j: int):
        """Returns the animation list AND performs the internal bookkeeping
        swap so subsequent cell_center()/highlight() calls by logical index
        stay correct after the visual swap."""
        pos_i = self.cells[i].get_center()
        pos_j = self.cells[j].get_center()
        anims = [
            self.cells[i].animate.move_to(pos_j),
            self.labels[i].animate.move_to(pos_j),
            self._index_labels[i].animate.next_to(self.cells[j], DOWN, buff=0.08),
            self.cells[j].animate.move_to(pos_i),
            self.labels[j].animate.move_to(pos_i),
            self._index_labels[j].animate.next_to(self.cells[i], DOWN, buff=0.08),
        ]
        self.cells[i], self.cells[j] = self.cells[j], self.cells[i]
        self.labels[i], self.labels[j] = self.labels[j], self.labels[i]
        self._index_labels[i], self._index_labels[j] = self._index_labels[j], self._index_labels[i]
        self.values[i], self.values[j] = self.values[j], self.values[i]
        return anims
