"""
HashMapVisualizer: renders key->value entries as a vertically stacked list
of "slots" that appear as they're inserted, with lookups shown as a
highlight-and-check or highlight-and-x based on found/not-found.

Used by: hashmap_ops, and as an auxiliary panel in two_sum (which
conceptually uses a hashmap for the O(n) approach).
"""
from __future__ import annotations

from manim import DOWN, LEFT, Cross, FadeIn, Rectangle, Text, VGroup, VMobject

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

SLOT_HEIGHT = 0.7
SLOT_WIDTH = 3.2
MAX_VISIBLE_SLOTS = 8  # beyond this, we scroll/compact rather than overflow the frame

# How far below the top of the safe frame the first hashmap slot starts —
# leaves room for the TitleBar every template places at the top, so a
# HashMapVisualizer never collides with it (this was a real bug caught by
# the mobject_bbox_overlap construction check during development: see
# manim_engine/templates/two_sum.py history).
TOP_OFFSET = 1.6


def _make_checkmark(color, size: float = 0.28) -> VMobject:
    """Minimal hand-built checkmark glyph — avoids depending on a font
    rendering a check character consistently across environments."""
    mark = VMobject(color=color, stroke_width=6)
    mark.set_points_as_corners(
        [
            [-size * 0.5, 0.0, 0],
            [-size * 0.1, -size * 0.4, 0],
            [size * 0.6, size * 0.5, 0],
        ]
    )
    return mark


class HashMapVisualizer(VGroup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entries: dict[int, VGroup] = {}
        self._order: list[int] = []

    def _slot_height(self) -> float:
        # Compact rows once we approach the available vertical space
        # (below the title), rather than letting the map grow off-screen
        # as entries accumulate.
        available_height = MAX_CONTENT_HEIGHT - TOP_OFFSET
        projected = max(len(self._order) + 1, 1) * (SLOT_HEIGHT + 0.15)
        if projected > available_height:
            scale = available_height / projected
            return max(SLOT_HEIGHT * scale, 0.3)
        return SLOT_HEIGHT

    def insert(self, key: int, value: int):
        height = self._slot_height()
        box = Rectangle(
            width=SLOT_WIDTH,
            height=height,
            fill_color=COLOR_CELL_FILL,
            fill_opacity=1.0,
            stroke_color=COLOR_CELL_STROKE,
            stroke_width=2,
        )
        font_size = min(FONT_SIZE_CELL, int(height * 34))
        label = Text(f"{key}  →  {value}", font_size=max(font_size, 10), color=COLOR_TEXT_PRIMARY)
        label.move_to(box.get_center())
        entry = VGroup(box, label)

        top_y = MAX_CONTENT_HEIGHT / 2 - TOP_OFFSET - height / 2
        entry.move_to([0.0, top_y - len(self._order) * (height + 0.15), 0])

        self.entries[key] = entry
        self._order.append(key)
        self.add(entry)

        # Re-flow existing entries to the (possibly new, smaller) slot height
        reflow_anims = []
        for i, k in enumerate(self._order):
            target_y = top_y - i * (height + 0.15)
            reflow_anims.append(self.entries[k].animate.move_to([0.0, target_y, 0]))
        return reflow_anims if reflow_anims else [FadeIn(entry)]

    def lookup(self, key: int, found: bool):
        if key not in self.entries:
            return []
        entry = self.entries[key]
        color = SEMANTIC_COLORS["success"] if found else SEMANTIC_COLORS["danger"]
        box = entry[0]
        anims = [box.animate.set_stroke(color, width=4)]
        if found:
            mark = _make_checkmark(COLOR_SUCCESS)
        else:
            mark = Cross(stroke_color=COLOR_DANGER, stroke_width=4, scale_factor=0.18)
        mark.next_to(entry, direction=[1, 0, 0], buff=0.15)
        self.add(mark)
        anims.append(FadeIn(mark))
        return anims
