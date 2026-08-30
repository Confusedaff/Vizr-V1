"""
StackVisualizer: a vertically-growing stack of value cells, bottom-anchored
so pushes grow upward and never collide with the title (same TOP_OFFSET
pattern used by HashMapVisualizer/TreeVisualizer/GraphVisualizer after
those collisions were found during development).

Used by: valid_parentheses (and any future stack-based algorithm —
monotonic stack problems, expression evaluation, etc. all fit this same
push/pop/peek shape).
"""
from __future__ import annotations

from manim import UP, Cross, FadeIn, FadeOut, Rectangle, Text, VGroup

from manim_engine.renderer.config import (
    COLOR_CELL_FILL,
    COLOR_CELL_STROKE,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CELL,
    SEMANTIC_COLORS,
)
from manim_engine.renderer.layout import MAX_CONTENT_HEIGHT

SLOT_HEIGHT = 0.65
SLOT_WIDTH = 1.4
BOTTOM_Y = -MAX_CONTENT_HEIGHT / 2 + 0.5  # base of the stack, safely above the frame's bottom edge
MAX_VISIBLE_SLOTS = 9  # compact once the stack would otherwise grow past the title


def _make_checkmark(color, size: float = 0.22):
    from manim import VMobject

    mark = VMobject(color=color, stroke_width=5)
    mark.set_points_as_corners(
        [[-size * 0.5, 0.0, 0], [-size * 0.1, -size * 0.4, 0], [size * 0.6, size * 0.5, 0]]
    )
    return mark


class StackVisualizer(VGroup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._entries: list[VGroup] = []

    def _slot_height(self) -> float:
        projected = (len(self._entries) + 1) * (SLOT_HEIGHT + 0.08)
        available = MAX_CONTENT_HEIGHT - 1.4  # leave title clearance
        if projected > available:
            return max(SLOT_HEIGHT * (available / projected), 0.3)
        return SLOT_HEIGHT

    def push(self, value: str):
        height = self._slot_height()
        box = Rectangle(
            width=SLOT_WIDTH, height=height,
            fill_color=COLOR_CELL_FILL, fill_opacity=1.0,
            stroke_color=COLOR_CELL_STROKE, stroke_width=2,
        )
        font_size = min(FONT_SIZE_CELL, int(height * 40))
        label = Text(value, font_size=max(font_size, 10), color=COLOR_TEXT_PRIMARY)
        label.move_to(box.get_center())
        entry = VGroup(box, label)

        y = BOTTOM_Y + height / 2 + len(self._entries) * (height + 0.08)
        entry.move_to([0, y, 0])
        self._entries.append(entry)
        self.add(entry)

        # Re-flow existing entries if slot height changed.
        reflow_anims = []
        for i, e in enumerate(self._entries):
            target_y = BOTTOM_Y + height / 2 + i * (height + 0.08)
            reflow_anims.append(e.animate.move_to([0, target_y, 0]))
        return reflow_anims if len(reflow_anims) > 1 else [FadeIn(entry, shift=UP * 0.2)]

    def pop(self, matched: bool | None = None):
        if not self._entries:
            return []
        entry = self._entries.pop()
        self.remove(entry)

        anims = []
        if matched is not None:
            box = entry[0]
            color = SEMANTIC_COLORS["success"] if matched else SEMANTIC_COLORS["danger"]
            anims.append(box.animate.set_stroke(color, width=4))
        anims.append(FadeOut(entry, shift=UP * 0.2))
        return anims

    def is_empty(self) -> bool:
        return len(self._entries) == 0
