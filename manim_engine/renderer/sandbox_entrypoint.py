"""
Entrypoint executed *inside* the sandbox container (see
infrastructure/docker/Dockerfile.sandbox). Reads a Scene JSON file from
/input/scene.json (mounted read-only), renders it, and writes the
resulting video to /output/ (mounted read-write, owned by the
unprivileged sandbox user).

This is intentionally the smallest possible surface: no argument
parsing beyond fixed, well-known paths, no dynamic code execution beyond
what manim_engine.renderer.compiler already does deterministically from
validated Scene JSON. If this file's job could be done by a shell
one-liner, it would be — but reading the mounted scene, invoking the
compiler, and translating any exception into a structured JSON result on
stdout wants just enough Python to do that cleanly.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

INPUT_SCENE_PATH = Path("/input/scene.json")
OUTPUT_DIR = Path("/output")
RESULT_MARKER = "__SANDBOX_RESULT_JSON__"


def main() -> int:
    from manim import config

    try:
        scene_json = json.loads(INPUT_SCENE_PATH.read_text())
    except Exception as e:
        print(RESULT_MARKER + json.dumps({"success": False, "error": f"Could not read scene input: {e}"}))
        return 1

    width = int(scene_json.pop("__render_width", 1920))
    height = int(scene_json.pop("__render_height", 1080))
    fps = int(scene_json.pop("__render_fps", 30))
    # Narration text -> path, relative to /input (see sandbox.py, which
    # copies the clips there since this container has no network of its
    # own to synthesize them with). Resolve back to absolute paths here.
    audio_map = {
        text: str(INPUT_SCENE_PATH.parent / rel)
        for text, rel in scene_json.pop("__audio_map", {}).items()
    }

    config.pixel_width = width
    config.pixel_height = height
    config.frame_rate = fps
    config.disable_caching = True
    config.media_dir = str(OUTPUT_DIR / "media")
    config.verbosity = "INFO"

    try:
        from packages.scene_schema import Scene
        from manim_engine.renderer.compiler import scene_to_manim

        scene = Scene(**scene_json)
        manim_scene = scene_to_manim(scene, audio_map=audio_map)
        manim_scene.render()

        video_path = str(manim_scene.renderer.file_writer.movie_file_path)
        result = {
            "success": True,
            "video_path": video_path,
            "construction_warnings": manim_scene.construction_warnings,
        }
        print(RESULT_MARKER + json.dumps(result))
        return 0
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        print(RESULT_MARKER + json.dumps(result))
        return 1


if __name__ == "__main__":
    sys.exit(main())
