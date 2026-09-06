"""
audio.py — Pipeline stage: synthesize spoken narration audio for a Scene's
caption text, using a free, no-API-key text-to-speech engine (edge-tts —
wraps Microsoft Edge's "Read Aloud" neural voices; free, no signup, no
billing, and noticeably more natural than offline engines like espeak/
pyttsx3, at the cost of needing outbound network access).

This stage runs *before* render_scene() and *outside* the Docker sandbox:
SANDBOX_MODE=docker denies the render container all network access by
design (see manim_engine/renderer/sandbox.py's `--network none`), so TTS
has to happen on the worker host. The resulting audio *files* are then
handed to the render step the same way scene.json already is — plain
paths for subprocess mode, copied into the read-only /input mount for
sandboxed mode (see sandbox.py).

Failure is deliberately non-fatal: if edge-tts can't reach its endpoint
(offline dev environment, corporate proxy, transient outage), this logs a
warning per line and returns whatever succeeded. A job should never fail
outright just because narration audio couldn't be generated — the video
still renders with its (silent) caption bar, exactly as it did before
this feature existed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from packages.scene_schema import Scene
from manim_engine.renderer.config import TTS_ENABLED, TTS_VOICE

logger = logging.getLogger(__name__)


@dataclass
class AudioStageResult:
    audio_map: dict[str, str] = field(default_factory=dict)  # narration text -> mp3 file path
    voice: str = TTS_VOICE
    errors: list[str] = field(default_factory=list)


def collect_narratable_text(scene: Scene) -> list[str]:
    """Every string a template's self.narrate() could be called with.

    Every template follows the same two-source pattern (see e.g.
    manim_engine/templates/binary_search.py): the scene's `narration`
    list, consumed one entry per narratable step, plus any individual
    step's own optional `message` (currently only `show_result` steps
    carry one). Order is preserved and duplicates removed — only the
    *set* of strings needing audio matters, since narrate() looks its
    argument up by exact text at render time regardless of when each
    line is actually spoken.
    """
    seen: dict[str, None] = {}
    for line in scene.narration:
        if line:
            seen.setdefault(line, None)
    for step in scene.steps:
        message = getattr(step, "message", None)
        if message:
            seen.setdefault(message, None)
    return list(seen.keys())


def _clip_filename(text: str) -> str:
    # Hash rather than slugify the text itself: narration lines can
    # contain punctuation/unicode that isn't filesystem-safe, and two
    # different lines should never collide onto the same file.
    return f"{hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]}.mp3"


async def _synthesize_all(
    texts: list[str], *, voice: str, out_dir: Path
) -> tuple[dict[str, str], list[str]]:
    import edge_tts

    audio_map: dict[str, str] = {}
    errors: list[str] = []

    # Sequential on purpose: a scene has at most a few dozen short lines
    # (narration is capped at 40 entries — see packages/scene_schema),
    # synthesis of each takes well under a second, and the render step
    # that follows this one takes far longer anyway. A semaphore-bounded
    # concurrent gather would only matter at a scale this project doesn't
    # operate at, and sequential keeps failures easy to attribute to the
    # exact line that caused them.
    for text in texts:
        dest = out_dir / _clip_filename(text)
        try:
            communicate = edge_tts.Communicate(text, voice=voice)
            await communicate.save(str(dest))
            if dest.exists() and dest.stat().st_size > 0:
                audio_map[text] = str(dest)
            else:
                errors.append(f"{text!r}: no audio produced")
        except Exception as e:  # noqa: BLE001 - any failure here degrades to silence, never a hard crash
            errors.append(f"{text!r}: {e}")

    return audio_map, errors


def generate_narration_audio(
    scene: Scene,
    *,
    output_dir: Path,
    voice: str = TTS_VOICE,
    enabled: bool = TTS_ENABLED,
) -> AudioStageResult:
    """Synthesize one mp3 per unique narratable string in `scene`.

    Returns an AudioStageResult whose `audio_map` (text -> file path) is
    always safe to pass straight into render_scene(audio_map=...) — on
    total failure (TTS disabled, no narration in the scene, or every
    synthesis call failing) it's simply empty, and the resulting video
    renders with captions only, same as before this feature existed.
    """
    if not enabled:
        return AudioStageResult(voice=voice)

    texts = collect_narratable_text(scene)
    if not texts:
        return AudioStageResult(voice=voice)

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        audio_map, errors = asyncio.run(_synthesize_all(texts, voice=voice, out_dir=output_dir))
    except Exception as e:
        # Failure at the gather level rather than per-line — e.g. no DNS/
        # network at all, or edge-tts isn't installed. Still non-fatal.
        logger.warning("Narration audio generation failed entirely: %s", e)
        return AudioStageResult(voice=voice, errors=[f"TTS unavailable: {e}"])

    if errors:
        logger.warning("Narration audio: %d/%d line(s) failed: %s", len(errors), len(texts), errors)

    return AudioStageResult(audio_map=audio_map, voice=voice, errors=errors)
