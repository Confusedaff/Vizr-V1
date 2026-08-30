"""
TreeVisualizer: renders a binary tree from a level-order array
(nulls = missing child), with edges drawn parent->child, and supports
visiting a node (highlight) with an order label ("1st", "2nd", ...).

Used by: binary_tree_traversal.
"""
from __future__ import annotations

import math

from manim import Circle, Create, FadeIn, Line, Text, VGroup

from manim_engine.renderer.config import (
    COLOR_CELL_FILL,
    COLOR_CELL_STROKE,
    COLOR_EDGE,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_CELL,
    SEMANTIC_COLORS,
)
from manim_engine.renderer.layout import MAX_CONTENT_HEIGHT, MAX_CONTENT_WIDTH

NODE_RADIUS = 0.45
MIN_NODE_RADIUS = 0.18
# Reserve space below the TitleBar every template places at the top —
# same fix as HashMapVisualizer.TOP_OFFSET; without this the root node
# (and any order_label placed above it during a visit) collides with the
# title, caught by the mobject_bbox_overlap construction check.
TOP_OFFSET = 1.3


def _level_of(index: int) -> int:
    return int(math.log2(index + 1))


class TreeVisualizer(VGroup):
    def __init__(self, values: list[int | None], **kwargs):
        super().__init__(**kwargs)
        self.values = list(values)
        self.node_circles: dict[int, Circle] = {}
        self.node_labels: dict[int, Text] = {}
        self.order_labels: dict[int, Text] = {}
        self.edges: list[Line] = []
        self._build()

    def _build(self) -> None:
        n = len(self.values)
        max_level = _level_of(n - 1) if n > 0 else 0
        num_levels = max_level + 1

        # Shrink node radius if the tree is wide/deep, same principle as
        # fit_row but specialized for a binary-tree layout (width doubles
        # per level, so we size against the widest/deepest level).
        widest_level_count = 2 ** max_level
        available_height = MAX_CONTENT_HEIGHT - TOP_OFFSET
        radius_by_width = MAX_CONTENT_WIDTH / (widest_level_count * 2.4) if widest_level_count else NODE_RADIUS
        radius_by_height = available_height / (num_levels * 2.4) if num_levels else NODE_RADIUS
        self.node_radius = max(MIN_NODE_RADIUS, min(NODE_RADIUS, radius_by_width, radius_by_height))
        self._below_legibility_floor = self.node_radius <= MIN_NODE_RADIUS + 1e-6

        v_spacing = available_height / max(num_levels, 1)
        top_y = MAX_CONTENT_HEIGHT / 2 - TOP_OFFSET - self.node_radius

        positions: dict[int, tuple[float, float]] = {}
        for i, val in enumerate(self.values):
            if val is None:
                continue
            level = _level_of(i)
            pos_in_level = i - (2 ** level - 1)
            slots_in_level = 2 ** level
            # Evenly space nodes in this level across the full content width
            slot_width = MAX_CONTENT_WIDTH / slots_in_level
            x = -MAX_CONTENT_WIDTH / 2 + slot_width * (pos_in_level + 0.5)
            y = top_y - level * v_spacing
            positions[i] = (x, y)

        # Edges first (so nodes draw on top)
        for i, val in enumerate(self.values):
            if val is None:
                continue
            for child in (2 * i + 1, 2 * i + 2):
                if child < n and self.values[child] is not None:
                    line = Line(
                        [*positions[i], 0],
                        [*positions[child], 0],
                        color=COLOR_EDGE,
                        stroke_width=3,
                    )
                    self.edges.append(line)
                    self.add(line)

        for i, val in enumerate(self.values):
            if val is None:
                continue
            x, y = positions[i]
            circle = Circle(
                radius=self.node_radius,
                fill_color=COLOR_CELL_FILL,
                fill_opacity=1.0,
                stroke_color=COLOR_CELL_STROKE,
                stroke_width=2,
            )
            circle.move_to([x, y, 0])
            font_size = min(FONT_SIZE_CELL, int(self.node_radius * 55))
            label = Text(str(val), font_size=max(font_size, 8), color=COLOR_TEXT_PRIMARY)
            label.move_to(circle.get_center())
            self.node_circles[i] = circle
            self.node_labels[i] = label
            self.add(circle, label)

    def is_below_legibility_floor(self) -> bool:
        return self._below_legibility_floor

    def build_in(self):
        return Create(self)

    def visit(self, index: int, order_label: str | None = None):
        anims = [
            self.node_circles[index].animate.set_fill(
                SEMANTIC_COLORS["highlight"], opacity=1.0
            ).set_stroke(SEMANTIC_COLORS["highlight"])
        ]
        if order_label:
            lbl = Text(order_label, font_size=FONT_SIZE_CAPTION, color=SEMANTIC_COLORS["success"])
            lbl.next_to(self.node_circles[index], direction=[0, 1, 0], buff=0.15)
            self.order_labels[index] = lbl
            self.add(lbl)
            anims.append(FadeIn(lbl))
        return anims
