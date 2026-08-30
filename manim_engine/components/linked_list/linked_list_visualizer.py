"""
LinkedListVisualizer: a horizontal chain of value nodes connected by
arrows, with named pointers (e.g. "slow"/"fast") that can advance along
the chain. Used to support linked-list-flavored variants of two_pointers
if/when the LLM classifies a prompt that way (§11 notes two_pointers can
apply to either an array or a linked list).
"""
from __future__ import annotations

from manim import DOWN, Arrow, Circle, Create, FadeIn, Text, VGroup

from manim_engine.renderer.config import (
    COLOR_CELL_FILL,
    COLOR_CELL_STROKE,
    COLOR_EDGE,
    COLOR_POINTER,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CELL,
    FONT_SIZE_LABEL,
)
from manim_engine.renderer.layout import fit_row

NODE_RADIUS = 0.45


class LinkedListVisualizer(VGroup):
    def __init__(self, values: list[int], **kwargs):
        super().__init__(**kwargs)
        self.values = list(values)
        self.node_circles: list[Circle] = []
        self.node_labels: list[Text] = []
        self._pointers: dict[str, VGroup] = {}
        self._build()

    def _build(self) -> None:
        n = len(self.values)
        fit = fit_row(n, NODE_RADIUS * 2, spacing_ratio=0.9)
        radius = fit.cell_size / 2
        self.node_radius = radius
        self._below_legibility_floor = fit.below_min
        gap = radius * 2 * 0.9

        x_cursor = -fit.total_width / 2
        centers = []
        for i, val in enumerate(self.values):
            circle = Circle(
                radius=radius,
                fill_color=COLOR_CELL_FILL,
                fill_opacity=1.0,
                stroke_color=COLOR_CELL_STROKE,
                stroke_width=2,
            )
            cx = x_cursor + radius
            circle.move_to([cx, 0, 0])
            centers.append(cx)
            font_size = min(FONT_SIZE_CELL, int(radius * 55))
            label = Text(str(val), font_size=max(font_size, 8), color=COLOR_TEXT_PRIMARY)
            label.move_to(circle.get_center())
            self.node_circles.append(circle)
            self.node_labels.append(label)
            self.add(circle, label)
            x_cursor += radius * 2 + gap

        for i in range(n - 1):
            arrow = Arrow(
                start=self.node_circles[i].get_right(),
                end=self.node_circles[i + 1].get_left(),
                color=COLOR_EDGE,
                buff=0.05,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.25,
            )
            self.add(arrow)

    def is_below_legibility_floor(self) -> bool:
        return self._below_legibility_floor

    def build_in(self):
        return Create(self)

    def advance_pointer(self, name: str, node_index: int):
        target = self.node_circles[node_index]
        anchor = target.get_center() + DOWN * (self.node_radius + 0.55)
        if name in self._pointers:
            old = self._pointers[name]
            fresh = self._make_pointer(anchor, name)
            return old.animate.become(fresh)
        else:
            fresh = self._make_pointer(anchor, name)
            self._pointers[name] = fresh
            self.add(fresh)
            return FadeIn(fresh)

    def _make_pointer(self, anchor_point, label_text: str) -> VGroup:
        arrow = Arrow(
            start=anchor_point + DOWN * 0.5,
            end=anchor_point,
            color=COLOR_POINTER,
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.4,
        )
        label = Text(label_text, font_size=FONT_SIZE_LABEL, color=COLOR_POINTER)
        label.next_to(arrow, DOWN, buff=0.08)
        return VGroup(arrow, label)
