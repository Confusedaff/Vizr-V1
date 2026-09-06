"""
sandbox.py — host-side runner that executes a render inside the
`vizr-sandbox` Docker image (infrastructure/docker/Dockerfile.sandbox)
via `docker run`, with the isolation flags spelled out explicitly below.

This is the "harder" isolation option compared to
workers/renderer/pipeline/render.py's subprocess-based approach: a bare
subprocess shares the host's filesystem, network, and user, whereas this
gives each render its own network-less, read-only-root, non-root,
resource-capped container. Use `render_scene_sandboxed()` in place of
`render_scene()` when SANDBOX_MODE=docker (see workers/renderer/pipeline/
render.py, which dispatches between the two based on that env var).

IMPORTANT — verification status: this module was built and its `docker
run` argument construction is unit-tested (tests/test_sandbox.py mocks
subprocess.run and asserts the exact flags), but it has NOT been
exercised against a live render in this development environment, which
has no Docker daemon available. Before relying on this in production,
run it against a real render at least once and confirm:
  1. `docker build -f infrastructure/docker/Dockerfile.sandbox -t
     vizr-sandbox .` succeeds
  2. A real Scene renders successfully through `render_scene_sandboxed()`
  3. The quality-gate/validation results match what the non-sandboxed
     path produces for the same Scene (they should be bit-for-bit
     identical, since it's the same renderer code — divergence would
     indicate an environment difference worth investigating, e.g. a
     missing font in the slimmer sandbox image)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

SANDBOX_IMAGE = "vizr-sandbox:latest"
RESULT_MARKER = "__SANDBOX_RESULT_JSON__"

# Resource limits — deliberately conservative. A render that needs more
# than this is almost certainly a bug (runaway loop, absurd scene size
# that should have been caught by schema limits) rather than a
# legitimate large job; tune upward only with evidence.
CPU_LIMIT = "2"
MEMORY_LIMIT = "2g"
PIDS_LIMIT = "128"


class SandboxError(Exception):
    pass


class SandboxUnavailableError(SandboxError):
    """Raised when the `docker` CLI itself isn't usable (not installed,
    daemon not running, image not built). Callers should treat this as a
    reason to fall back to the non-sandboxed subprocess path, not as a
    render failure — see render.py's dispatch logic."""


@dataclass
class SandboxRenderResult:
    success: bool
    video_path: str | None
    construction_warnings: list[str]
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None = None


def check_sandbox_available() -> bool:
    """Cheap pre-flight check: is `docker` runnable and is the sandbox
    image present? Called once per worker process (not per render) to
    decide whether to attempt the sandboxed path at all."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", SANDBOX_IMAGE],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_docker_run_args(
    *, input_dir: Path, output_dir: Path, container_name: str,
    cpu_limit: str = CPU_LIMIT, memory_limit: str = MEMORY_LIMIT, pids_limit: str = PIDS_LIMIT,
) -> list[str]:
    """Isolated for direct unit testing (tests/test_sandbox.py) — the
    exact flag set is the security-relevant part of this module, so it's
    worth asserting on directly rather than only indirectly via a live
    docker run that can't execute in most CI/dev environments."""
    return [
        "docker", "run",
        "--rm",
        "--name", container_name,
        "--network", "none",                     # no network access at all
        "--read-only",                            # root filesystem is read-only
        "--tmpfs", "/tmp:size=512m",               # writable scratch space only
        "--user", "sandboxuser",
        "--cap-drop", "ALL",                       # drop all Linux capabilities
        "--security-opt", "no-new-privileges",
        f"--cpus={cpu_limit}",
        f"--memory={memory_limit}",
        f"--pids-limit={pids_limit}",
        "-v", f"{input_dir}:/input:ro",
        "-v", f"{output_dir}:/output:rw",
        SANDBOX_IMAGE,
    ]


def render_scene_sandboxed(
    scene_dict: dict,
    *,
    output_dir: Path,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 30,
    timeout_seconds: int = 180,
    audio_map: dict[str, str] | None = None,
) -> SandboxRenderResult:
    """`audio_map` (narration text -> mp3 file path on the *host*, from
    workers/renderer/pipeline/audio.py) is copied into the read-only
    /input mount below, since the sandbox container has no network
    (`--network none`) and so cannot reach edge-tts's endpoint itself —
    TTS synthesis always happens on the host, before this function runs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not check_sandbox_available():
        raise SandboxUnavailableError(
            f"Docker sandbox image {SANDBOX_IMAGE!r} is not available. "
            "Build it with: docker build -f infrastructure/docker/Dockerfile.sandbox "
            "-t vizr-sandbox . — or set SANDBOX_MODE=subprocess to use the "
            "non-sandboxed render path instead."
        )

    input_dir = Path(tempfile.mkdtemp(prefix="vizr-sandbox-input-"))

    # Copy narration clips into the input mount and rewrite the map to
    # the container-relative paths sandbox_entrypoint.py will resolve
    # against /input — the host paths in `audio_map` mean nothing inside
    # the container's own filesystem.
    container_audio_map: dict[str, str] = {}
    if audio_map:
        audio_dir = input_dir / "audio"
        audio_dir.mkdir(exist_ok=True)
        for i, (text, host_path) in enumerate(audio_map.items()):
            src = Path(host_path)
            if not src.exists():
                continue
            dest_name = f"{i}{src.suffix or '.mp3'}"
            shutil.copyfile(src, audio_dir / dest_name)
            container_audio_map[text] = f"audio/{dest_name}"

    scene_with_render_opts = {
        **scene_dict,
        "__render_width": resolution[0],
        "__render_height": resolution[1],
        "__render_fps": fps,
        "__audio_map": container_audio_map,
    }
    (input_dir / "scene.json").write_text(json.dumps(scene_with_render_opts))

    container_name = f"vizr-render-{uuid.uuid4().hex[:12]}"
    args = build_docker_run_args(input_dir=input_dir, output_dir=output_dir, container_name=container_name)

    started = time.time()
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as e:
        # Best-effort: make sure a timed-out container doesn't linger.
        subprocess.run(["docker", "kill", container_name], capture_output=True, timeout=10)
        shutil.rmtree(input_dir, ignore_errors=True)
        return SandboxRenderResult(
            success=False, video_path=None, construction_warnings=[],
            stdout=e.stdout or "", stderr=(e.stderr or "") + f"\n[sandbox timed out after {timeout_seconds}s]",
            duration_seconds=time.time() - started, error="TIMEOUT",
        )
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    duration = time.time() - started

    if proc.returncode not in (0, 1):  # 1 is our own "render failed cleanly" exit code
        return SandboxRenderResult(
            success=False, video_path=None, construction_warnings=[],
            stdout=proc.stdout, stderr=proc.stderr, duration_seconds=duration,
            error=f"CONTAINER_EXIT_{proc.returncode}",
        )

    result_line = next((l for l in proc.stdout.splitlines() if l.startswith(RESULT_MARKER)), None)
    if result_line is None:
        return SandboxRenderResult(
            success=False, video_path=None, construction_warnings=[],
            stdout=proc.stdout, stderr=proc.stderr, duration_seconds=duration,
            error="NO_RESULT_MARKER",
        )

    parsed = json.loads(result_line[len(RESULT_MARKER):])
    if not parsed.get("success"):
        return SandboxRenderResult(
            success=False, video_path=None, construction_warnings=[],
            stdout=proc.stdout, stderr=parsed.get("traceback", proc.stderr),
            duration_seconds=duration, error=parsed.get("error", "SANDBOX_RENDER_FAILED"),
        )

    # video_path inside the container is under /output/media/...; the
    # host-visible path is output_dir/media/... since output_dir was
    # bind-mounted to /output.
    container_video_path = Path(parsed["video_path"])
    relative = container_video_path.relative_to("/output")
    host_video_path = output_dir / relative

    return SandboxRenderResult(
        success=True,
        video_path=str(host_video_path),
        construction_warnings=parsed.get("construction_warnings", []),
        stdout=proc.stdout, stderr=proc.stderr, duration_seconds=duration,
    )
