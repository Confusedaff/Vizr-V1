"""
render.py — Pipeline stage: compile a validated Scene to a Manim scene
instance and run it, then validate the output. Two execution modes,
selected by the SANDBOX_MODE environment variable:

  - "subprocess" (default): run in a plain Python subprocess on the same
    host. A Manim crash/hang can't take down the worker process itself,
    but the render shares the host's filesystem/network/user.
  - "docker": run inside the isolated `aiviz-sandbox` container (see
    manim_engine/renderer/sandbox.py and
    infrastructure/docker/Dockerfile.sandbox) — no network, read-only
    root, non-root user, capped CPU/memory/pids. This is the harder
    isolation boundary; use it when rendering content from less-trusted
    sources than this project's own schema-driven pipeline, or simply
    for defense-in-depth in production.

If SANDBOX_MODE=docker but the sandbox image isn't built/available,
render_scene() logs a warning and falls back to subprocess mode rather
than failing every render — this makes local development (no Docker
daemon) work identically to production (Docker available) without a
separate code path, at the cost of silently weaker isolation in that
fallback case, which is why it's logged clearly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from packages.scene_schema import Scene
from manim_engine.renderer.config import RENDER_FPS, RENDER_RESOLUTION, RENDERER_VERSION
from manim_engine.renderer.validate_render import RenderValidationResult, validate_render

SANDBOX_MODE = os.environ.get("SANDBOX_MODE", "subprocess")  # "subprocess" | "docker"

_RENDER_SUBPROCESS_TEMPLATE = '''
import sys
import json

sys.path.insert(0, {project_root!r})

from manim import config
config.pixel_width = {width}
config.pixel_height = {height}
config.frame_rate = {fps}
config.disable_caching = True
config.media_dir = {media_dir!r}
config.verbosity = "INFO"

from packages.scene_schema import Scene
from manim_engine.renderer.compiler import scene_to_manim

scene_json = json.loads({scene_json_repr})
scene = Scene(**scene_json)
manim_scene = scene_to_manim(scene)
manim_scene.render()

result = {{
    "construction_warnings": manim_scene.construction_warnings,
    "video_path": str(manim_scene.renderer.file_writer.movie_file_path),
}}
print("__RENDER_RESULT_JSON__" + json.dumps(result))
'''


@dataclass
class RenderStageResult:
    success: bool
    video_path: str | None
    construction_warnings: list[str]
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None = None
    sandbox_mode_used: str = "subprocess"


def render_scene(
    scene: Scene,
    *,
    output_dir: Path,
    project_root: Path,
    resolution: tuple[int, int] = RENDER_RESOLUTION,
    fps: int = RENDER_FPS,
    timeout_seconds: int = 180,
) -> RenderStageResult:
    if SANDBOX_MODE == "docker":
        sandboxed_result = _try_render_scene_docker(
            scene, output_dir=output_dir, resolution=resolution, fps=fps, timeout_seconds=timeout_seconds
        )
        if sandboxed_result is not None:
            return sandboxed_result
        # Fall through to subprocess mode — logged inside the helper.

    return _render_scene_subprocess(
        scene, output_dir=output_dir, project_root=project_root,
        resolution=resolution, fps=fps, timeout_seconds=timeout_seconds,
    )


def _try_render_scene_docker(
    scene: Scene, *, output_dir: Path, resolution: tuple[int, int], fps: int, timeout_seconds: int,
) -> RenderStageResult | None:
    """Returns None (signaling "fall back to subprocess") if the sandbox
    image isn't available; otherwise always returns a RenderStageResult
    (success or failure) from the sandboxed attempt."""
    from manim_engine.renderer.sandbox import SandboxUnavailableError, render_scene_sandboxed

    try:
        sandbox_result = render_scene_sandboxed(
            scene.model_dump(mode="json"), output_dir=output_dir,
            resolution=resolution, fps=fps, timeout_seconds=timeout_seconds,
        )
    except SandboxUnavailableError as e:
        import logging

        logging.getLogger(__name__).warning(
            "SANDBOX_MODE=docker requested but sandbox unavailable (%s); "
            "falling back to subprocess mode for this render.", e,
        )
        return None

    return RenderStageResult(
        success=sandbox_result.success,
        video_path=sandbox_result.video_path,
        construction_warnings=sandbox_result.construction_warnings,
        stdout=sandbox_result.stdout,
        stderr=sandbox_result.stderr,
        duration_seconds=sandbox_result.duration_seconds,
        error=sandbox_result.error,
        sandbox_mode_used="docker",
    )


def _render_scene_subprocess(
    scene: Scene,
    *,
    output_dir: Path,
    project_root: Path,
    resolution: tuple[int, int] = RENDER_RESOLUTION,
    fps: int = RENDER_FPS,
    timeout_seconds: int = 180,
) -> RenderStageResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    media_dir = output_dir / "media"

    script = _RENDER_SUBPROCESS_TEMPLATE.format(
        project_root=str(project_root),
        width=resolution[0],
        height=resolution[1],
        fps=fps,
        media_dir=str(media_dir),
        scene_json_repr=repr(json.dumps(scene.model_dump(mode="json"))),
    )
    script_path = output_dir / "render_scene.py"
    script_path.write_text(script)

    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(project_root),
        )
    except subprocess.TimeoutExpired as e:
        return RenderStageResult(
            success=False,
            video_path=None,
            construction_warnings=[],
            stdout=e.stdout or "",
            stderr=(e.stderr or "") + f"\n[render timed out after {timeout_seconds}s]",
            duration_seconds=time.time() - started,
            error="TIMEOUT",
        )

    duration = time.time() - started

    if proc.returncode != 0:
        return RenderStageResult(
            success=False,
            video_path=None,
            construction_warnings=[],
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
            error="RENDER_PROCESS_FAILED",
        )

    marker = "__RENDER_RESULT_JSON__"
    result_line = next((line for line in proc.stdout.splitlines() if line.startswith(marker)), None)
    if result_line is None:
        return RenderStageResult(
            success=False,
            video_path=None,
            construction_warnings=[],
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
            error="NO_RESULT_MARKER",
        )

    parsed = json.loads(result_line[len(marker):])
    return RenderStageResult(
        success=True,
        video_path=parsed["video_path"],
        construction_warnings=parsed.get("construction_warnings", []),
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=duration,
    )
