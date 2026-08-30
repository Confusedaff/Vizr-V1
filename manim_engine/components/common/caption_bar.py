"""CaptionBar: bottom-anchored narration line, replaced (not stacked) as
steps advance so captions never accumulate and overlap.

IMPORTANT: because Manim's `Scene.play()` implicitly adds any mobject
passed to an animation into the Scene's top-level mobject list (separate
from this VGroup's own internal `.submobjects`), a naive
Transform(old_text, new_text) leaves the *previous* Text instances
registered in the Scene forever, even though visually they were morphed
away. Over a multi-step scene this accumulates into a pile of invisible
"ghost" mobjects sitting at the caption's screen position — which is
exactly the kind of hard-to-see bug the mobject_bbox_overlap debug check
(manim_engine/debug/frame_quality.py) is designed to catch, and which
surfaced this bug during development. Fixed here by returning a
FadeOut+FadeIn pair instead of Transform, and by the caller (BaseVisualizationScene)
explicitly registering/deregistering the CaptionBar's mobjects."""
from __future__ import annotations

from manim import AnimationGroup, FadeIn, FadeOut, Text, VGroup

from manim_engine.renderer.config import COLOR_TEXT_MUTED, FONT_SIZE_CAPTION
from manim_engine.renderer.layout import MAX_CONTENT_HEIGHT, MAX_CONTENT_WIDTH


class CaptionBar(VGroup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current: Text | None = None

    def set_caption(self, text: str):
        new_text = Text(text, font_size=FONT_SIZE_CAPTION, color=COLOR_TEXT_MUTED)
        if new_text.width > MAX_CONTENT_WIDTH:
            new_text.scale(MAX_CONTENT_WIDTH / new_text.width)
        new_text.move_to([0, -MAX_CONTENT_HEIGHT / 2 + new_text.height / 2, 0])

        if self._current is None:
            self._current = new_text
            self.add(new_text)
            return FadeIn(new_text)
        else:
            old = self._current
            self._current = new_text
            self.remove(old)
            self.add(new_text)
            # FadeOut(old) + FadeIn(new_text) as a group ensures `old` is
            # actually released from the Scene's mobject list (FadeOut
            # removes its target on completion), unlike Transform which
            # leaves the source mobject resident.
            return AnimationGroup(FadeOut(old), FadeIn(new_text))
