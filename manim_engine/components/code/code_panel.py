"""
CodePanel: monospace pseudocode/code panel with per-line highlighting,
positioned as a side panel so it never overlaps the main visualization.
"""
from __future__ import annotations

from manim import LEFT, Rectangle, Text, VGroup

from manim_engine.renderer.config import (
    COLOR_CELL_STROKE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CODE,
    SEMANTIC_COLORS,
)
from manim_engine.renderer.layout import MAX_CONTENT_HEIGHT

PANEL_WIDTH = 4.6


class CodePanel(VGroup):
    def __init__(self, lines: list[str], **kwargs):
        super().__init__(**kwargs)
        self.code_lines = list(lines)
        self.line_mobjects: list[Text] = []
        self._current_highlight: int | None = None
        self._build()

    def _build(self) -> None:
        n = len(self.code_lines)
        line_height = min(0.42, MAX_CONTENT_HEIGHT / max(n, 1) * 0.9)
        font_size = min(FONT_SIZE_CODE, int(line_height * 60))

        border = Rectangle(
            width=PANEL_WIDTH,
            height=min(MAX_CONTENT_HEIGHT, n * line_height + 0.4),
            stroke_color=COLOR_CELL_STROKE,
            stroke_width=1.5,
            fill_opacity=0,
        )
        self.add(border)
        self._border = border

        top_y = border.get_top()[1] - 0.3
        for i, line in enumerate(self.code_lines):
            text = Text(
                line,
                font="monospace",
                font_size=max(font_size, 10),
                color=COLOR_TEXT_MUTED,
            )
            text.align_to(border, LEFT).shift(LEFT * -0.15)
            text.move_to([border.get_center()[0] - PANEL_WIDTH / 2 + text.width / 2 + 0.2,
                          top_y - i * line_height, 0])
            self.line_mobjects.append(text)
            self.add(text)

    def highlight_line(self, line_index: int):
        anims = []
        if self._current_highlight is not None and self._current_highlight < len(self.line_mobjects):
            prev = self.line_mobjects[self._current_highlight]
            anims.append(prev.animate.set_color(COLOR_TEXT_MUTED))
        if 0 <= line_index < len(self.line_mobjects):
            cur = self.line_mobjects[line_index]
            anims.append(cur.animate.set_color(SEMANTIC_COLORS["highlight"]))
            self._current_highlight = line_index
        return anims
