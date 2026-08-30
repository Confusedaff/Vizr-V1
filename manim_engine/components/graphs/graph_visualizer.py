"""
GraphVisualizer: renders an arbitrary graph (node list + edge list) using
a deterministic circular layout (no physics simulation — determinism
matters more than aesthetic optimality here, and circular layout is
legible for the small graphs (<=20 nodes) this system targets).

Used by: graph_bfs_dfs.
"""
from __future__ import annotations

import math

from manim import Circle, Create, FadeIn, Line, Text, VGroup

from manim_engine.renderer.config import (
    COLOR_CELL_FILL,
    COLOR_CELL_STROKE,
    COLOR_EDGE,
    COLOR_EDGE_ACTIVE,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_CELL,
    SEMANTIC_COLORS,
)
from manim_engine.renderer.layout import MAX_CONTENT_HEIGHT, MAX_CONTENT_WIDTH

NODE_RADIUS = 0.4
MIN_NODE_RADIUS = 0.2
# Reserve space below the TitleBar (same rationale as
# TreeVisualizer.TOP_OFFSET / HashMapVisualizer.TOP_OFFSET) — the graph's
# circular layout is otherwise centered on the full frame and its topmost
# node collides with the title.
TOP_OFFSET = 1.3


class GraphVisualizer(VGroup):
    def __init__(self, nodes: list[int], edges: list[list[int]], **kwargs):
        super().__init__(**kwargs)
        self.node_ids = list(nodes)
        self.edge_list = [tuple(e) for e in edges]
        self.node_circles: dict[int, Circle] = {}
        self.node_labels: dict[int, Text] = {}
        self.order_labels: dict[int, Text] = {}
        self.edge_lines: dict[tuple[int, int], Line] = {}
        self._build()

    def _build(self) -> None:
        n = len(self.node_ids)
        available_height = MAX_CONTENT_HEIGHT - TOP_OFFSET
        # Layout is centered in the available area below the title, so
        # shift the vertical center down by half the reserved offset.
        center_y = -TOP_OFFSET / 2
        layout_radius = min(MAX_CONTENT_WIDTH, available_height) / 2 - NODE_RADIUS
        # Shrink node size as node count grows, so labels stay legible and
        # nodes don't overlap on the circle.
        circumference_per_node = (2 * math.pi * layout_radius) / max(n, 1)
        self.node_radius = max(MIN_NODE_RADIUS, min(NODE_RADIUS, circumference_per_node / 2.6))
        self._below_legibility_floor = self.node_radius <= MIN_NODE_RADIUS + 1e-6

        positions: dict[int, tuple[float, float]] = {}
        for i, node_id in enumerate(self.node_ids):
            angle = 2 * math.pi * i / max(n, 1) + math.pi / 2  # start at top
            x = layout_radius * math.cos(angle)
            y = center_y + layout_radius * math.sin(angle)
            positions[node_id] = (x, y)

        for (a, b) in self.edge_list:
            if a not in positions or b not in positions:
                continue
            line = Line([*positions[a], 0], [*positions[b], 0], color=COLOR_EDGE, stroke_width=3)
            self.edge_lines[(a, b)] = line
            self.edge_lines[(b, a)] = line  # undirected lookup convenience
            self.add(line)

        for node_id in self.node_ids:
            x, y = positions[node_id]
            circle = Circle(
                radius=self.node_radius,
                fill_color=COLOR_CELL_FILL,
                fill_opacity=1.0,
                stroke_color=COLOR_CELL_STROKE,
                stroke_width=2,
            )
            circle.move_to([x, y, 0])
            font_size = min(FONT_SIZE_CELL, int(self.node_radius * 60))
            label = Text(str(node_id), font_size=max(font_size, 8), color=COLOR_TEXT_PRIMARY)
            label.move_to(circle.get_center())
            self.node_circles[node_id] = circle
            self.node_labels[node_id] = label
            self.add(circle, label)

    def is_below_legibility_floor(self) -> bool:
        return self._below_legibility_floor

    def build_in(self):
        return Create(self)

    def visit_node(self, node_id: int, order_label: str | None = None):
        anims = [
            self.node_circles[node_id].animate.set_fill(
                SEMANTIC_COLORS["highlight"], opacity=1.0
            ).set_stroke(SEMANTIC_COLORS["highlight"])
        ]
        if order_label:
            lbl = Text(order_label, font_size=FONT_SIZE_CAPTION, color=SEMANTIC_COLORS["success"])
            lbl.next_to(self.node_circles[node_id], direction=[0, 1, 0], buff=0.12)
            self.order_labels[node_id] = lbl
            self.add(lbl)
            anims.append(FadeIn(lbl))
        return anims

    def traverse_edge(self, from_node: int, to_node: int):
        line = self.edge_lines.get((from_node, to_node))
        if line is None:
            return []
        return [line.animate.set_color(COLOR_EDGE_ACTIVE).set_stroke(width=5)]
