"""
BaseVisualizationScene: shared scaffolding every template scene extends —
background color, title, caption bar, and the geometric bbox-overlap
self-check (§10/§15) run automatically after construct() so every
template gets it for free rather than each one remembering to call it.
"""
from __future__ import annotations

from pathlib import Path

from manim import Scene

from manim_engine.components.common.caption_bar import CaptionBar
from manim_engine.components.common.title_bar import TitleBar
from manim_engine.debug.frame_quality import FrameIssue, Severity, check_mobject_bbox_overlap
from manim_engine.renderer.config import COLOR_BACKGROUND


class BaseVisualizationScene(Scene):
    """
    Subclasses set `self.scene_data` (a packages.scene_schema.Scene) before
    construct() runs (the compiler does this via a partial/closure — see
    manim_engine/renderer/compiler.py) and implement `build_visualization()`
    instead of `construct()` directly, so this base class can wrap the
    call with consistent setup/teardown and construction-time validation.
    """

    scene_data = None  # set externally by the compiler before .render()
    # narration text -> pre-synthesized mp3 path (see
    # workers/renderer/pipeline/audio.py); also set externally by the
    # compiler. Empty by default so scenes render silently (captions
    # only) when narration audio wasn't generated or is disabled.
    audio_map: dict[str, str] = {}

    def construct(self):
        self.camera.background_color = COLOR_BACKGROUND
        self.construction_warnings: list[str] = []
        self.title_bar = TitleBar(self.scene_data.title)
        self.add(self.title_bar)
        self.caption_bar = CaptionBar()

        self.build_visualization()

        # Construction-time geometric self-check — cheap, exact, and runs
        # once at the end rather than per-frame (positions are largely
        # static once .animate calls complete within this method's scope;
        # per-step checks are also invoked explicitly inside templates
        # wherever a template performs a layout-sensitive operation).
        self._run_construction_checks()

    def build_visualization(self) -> None:
        raise NotImplementedError("Templates must implement build_visualization()")

    def _run_construction_checks(self) -> None:
        top_level_children = []
        for m in self.mobjects:
            # Filter out Manim's internal zero-area bookkeeping mobjects
            # (bare `Mobject` placeholders left behind by animation
            # compilation) — only compare things with actual visual
            # extent, or every render falsely reports 100% overlap
            # between two degenerate zero-size points at the origin.
            if not (hasattr(m, "get_left") and hasattr(m, "get_right")):
                continue
            try:
                width = m.width
                height = m.height
            except Exception:
                continue
            if width <= 1e-6 or height <= 1e-6:
                continue
            top_level_children.append(m)

        issues = check_mobject_bbox_overlap(top_level_children, min_overlap_fraction=0.4)
        for issue in issues:
            if issue.severity == Severity.ERROR:
                self.construction_warnings.append(issue.message)

    def narrate(self, text: str):
        """Sets the on-screen caption and, when a pre-synthesized voice
        clip exists for this exact text, schedules it to play alongside
        it via Manim's own audio mixer (Scene.add_sound mixes straight
        into the rendered movie file — no separate muxing step needed).

        time_offset=0 means "starting now" — add_sound schedules relative
        to the scene's *current* elapsed time, not absolute zero, so this
        lines the clip up with the caption's fade-in regardless of how
        far into the scene this call happens.

        Falls back to caption-only (no exception, no audio) whenever
        audio_map has no entry for this text or TTS was disabled/failed
        for this line — see workers/renderer/pipeline/audio.py.
        """
        audio_path = self.audio_map.get(text) if self.audio_map else None
        if audio_path and Path(audio_path).exists():
            self.add_sound(audio_path, time_offset=0)
        return self.caption_bar.set_caption(text)

    def safe_play(self, *animations) -> None:
        """Wraps self.play() to tolerate zero animations gracefully.

        Manim's Scene.play() raises ValueError("Called Scene.play with no
        animations") if given an empty argument list. Several component
        methods (e.g. HashMapVisualizer.lookup() for a key that was never
        inserted) legitimately return [] when there's nothing to animate
        for a given step — a real case found via the integration test
        suite (hashmap_ops with a not-found lookup). Every template
        should call self.safe_play(*anims) instead of self.play(*anims)
        so a semantically-empty step never crashes the render.
        """
        anims = [a for a in animations if a is not None]
        if not anims:
            return
        self.play(*anims)
