"""
PointerGroup: named, labeled pointers (arrow + label) that sit below an
ArrayVisualizer and can be moved to point at a new index.

Used by: two_pointers, binary_search, sliding_window, two_sum,
merge_sort (i/j merge pointers).
"""
from __future__ import annotations

from manim import DOWN, UP, Arrow, FadeIn, FadeOut, Text, VGroup

from manim_engine.renderer.config import COLOR_POINTER, FONT_SIZE_LABEL


class PointerGroup(VGroup):
    """Holds zero or more named pointers. Each pointer is an
    (arrow, label) pair anchored beneath a specific array cell."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pointers: dict[str, VGroup] = {}

    def _make_pointer(self, target_point, label_text: str, color=COLOR_POINTER) -> VGroup:
        arrow = Arrow(
            start=target_point + DOWN * 1.1,
            end=target_point + DOWN * 0.55,
            color=color,
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.4,
        )
        label = Text(label_text, font_size=FONT_SIZE_LABEL, color=color)
        label.next_to(arrow, DOWN, buff=0.08)
        return VGroup(arrow, label)

    def set_pointer(self, name: str, target_point, label: str | None = None):
        """Returns an animation. If the pointer already exists, animates a
        morph from its current shape/position to the new target (handles
        both moving to a new index and relabeling in one step). Otherwise
        animates a FadeIn of a newly created pointer."""
        label_text = label if label is not None else name
        fresh = self._make_pointer(target_point, label_text)
        if name in self._pointers:
            old = self._pointers[name]
            anim = old.animate.become(fresh)
            return anim
        else:
            self._pointers[name] = fresh
            self.add(fresh)
            return FadeIn(fresh, shift=UP * 0.2)

    def remove_pointer(self, name: str):
        if name not in self._pointers:
            return None
        mobj = self._pointers.pop(name)
        self.remove(mobj)
        return FadeOut(mobj)

    def has(self, name: str) -> bool:
        return name in self._pointers
