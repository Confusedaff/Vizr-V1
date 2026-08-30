"""TitleBar: consistent title placement, top-safe-margin anchored."""
from __future__ import annotations

from manim import UP, Text, VGroup

from manim_engine.renderer.config import COLOR_TEXT_PRIMARY, FONT_SIZE_TITLE
from manim_engine.renderer.layout import MAX_CONTENT_HEIGHT, MAX_CONTENT_WIDTH


class TitleBar(VGroup):
    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        text = Text(title, font_size=FONT_SIZE_TITLE, color=COLOR_TEXT_PRIMARY, weight="BOLD")
        if text.width > MAX_CONTENT_WIDTH:
            text.scale(MAX_CONTENT_WIDTH / text.width)
        text.move_to([0, MAX_CONTENT_HEIGHT / 2 - text.height / 2, 0])
        self.add(text)
        self.text = text
