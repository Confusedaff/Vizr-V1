"""
Centralized renderer configuration: colors, fonts, resolution, durations.

Every component reads styling from here rather than hardcoding values —
this is what makes "custom themes" (§37 future roadmap) tractable later,
and what keeps visual consistency across all 10 templates now.

Bump RENDERER_VERSION whenever a change here would visibly change output
(color palette, resolution, fps) — this feeds the cache key (§22).
"""
from __future__ import annotations

import os

RENDERER_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Color palette — deliberately high-contrast, colorblind-conscious.
# Named semantically (not "blue"/"red") so templates express *meaning*,
# and the palette can be swapped without touching template code.
# --------------------------------------------------------------------------

COLOR_BACKGROUND = "#0E1116"
COLOR_CELL_FILL = "#1B2230"
COLOR_CELL_STROKE = "#3D4A5C"
COLOR_TEXT_PRIMARY = "#F5F7FA"
COLOR_TEXT_MUTED = "#9AA5B1"

COLOR_HIGHLIGHT = "#4C9AFF"       # active / "look here" — blue
COLOR_SUCCESS = "#3FB950"        # found / correct — green
COLOR_DANGER = "#F85149"         # eliminated / wrong — red
COLOR_NEUTRAL = "#3D4A5C"        # dimmed / out of range — grey
COLOR_SECONDARY = "#D29922"      # secondary pointer / accent — amber

COLOR_POINTER = "#E3B341"
COLOR_EDGE = "#5B6B82"
COLOR_EDGE_ACTIVE = "#4C9AFF"

SEMANTIC_COLORS = {
    "highlight": COLOR_HIGHLIGHT,
    "success": COLOR_SUCCESS,
    "danger": COLOR_DANGER,
    "neutral": COLOR_NEUTRAL,
    "secondary": COLOR_SECONDARY,
}

# --------------------------------------------------------------------------
# Typography
# --------------------------------------------------------------------------

FONT_PRIMARY = "sans-serif"
FONT_MONO = "monospace"

FONT_SIZE_TITLE = 40
FONT_SIZE_LABEL = 28
FONT_SIZE_CELL = 32
FONT_SIZE_CODE = 24
FONT_SIZE_CAPTION = 22

# --------------------------------------------------------------------------
# Layout / screen-boundary protection
# --------------------------------------------------------------------------

# Manim's default frame is 14.22 x 8 units (16:9 at default camera).
# We keep a safety margin so nothing ever touches the true edge.
FRAME_WIDTH = 14.0
FRAME_HEIGHT = 8.0
SAFE_MARGIN = 0.6
MAX_CONTENT_WIDTH = FRAME_WIDTH - 2 * SAFE_MARGIN     # 12.8
MAX_CONTENT_HEIGHT = FRAME_HEIGHT - 2 * SAFE_MARGIN    # 6.8

DEFAULT_CELL_SIZE = 0.9
MIN_CELL_SIZE = 0.28  # below this, text becomes illegible — see quality gate

# --------------------------------------------------------------------------
# Animation durations (seconds) — sane defaults, rarely overridden
# --------------------------------------------------------------------------

DURATION_BUILD = 0.6
DURATION_HIGHLIGHT = 0.4
DURATION_MOVE = 0.5
DURATION_SWAP = 0.7
DURATION_RESULT = 0.8
PAUSE_SHORT = 0.2
PAUSE_LONG = 0.6

# --------------------------------------------------------------------------
# Render output settings
# --------------------------------------------------------------------------

RENDER_FPS = 30
RENDER_RESOLUTION = (1920, 1080)  # production quality (-qh equivalent)
PREVIEW_RESOLUTION = (854, 480)   # fast local iteration (-ql equivalent)

MIN_VIDEO_DURATION_S = 1.0
MAX_VIDEO_DURATION_S = 90.0

# --------------------------------------------------------------------------
# Narration audio (text-to-speech) — see workers/renderer/pipeline/audio.py
# --------------------------------------------------------------------------

# edge-tts wraps Microsoft Edge's "Read Aloud" neural voices: free, no API
# key/signup/billing, and considerably more natural than offline engines
# like espeak/pyttsx3 — at the cost of needing outbound network access,
# which is why the audio stage runs on the worker host *before* the
# (network-less, when SANDBOX_MODE=docker) render step, not inside it.
TTS_ENABLED = os.environ.get("TTS_ENABLED", "true").strip().lower() not in ("false", "0", "")
# Any edge-tts neural voice name works here; run `edge-tts --list-voices`
# for the full catalog across languages/accents. This one is a natural-
# sounding, general-purpose US English voice.
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AriaNeural")
