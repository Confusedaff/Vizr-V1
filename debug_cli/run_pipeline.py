#!/usr/bin/env python3
"""
Debug CLI — run any part of the pipeline in isolation and inspect the
results, without needing FastAPI/Celery/Postgres/Redis running.

Usage:
  # Full pipeline from a manual scene JSON file (no LLM key needed):
  python debug_cli/run_pipeline.py from-scene --scene-file scene.json --job-id test1

  # Full pipeline from a natural-language prompt (needs ANTHROPIC_API_KEY
  # or --api-key):
  python debug_cli/run_pipeline.py from-prompt --prompt "binary search for 9" --job-id test2

  # Full pipeline from manual classification (no LLM key needed, but still
  # exercises the real plan_scene LLM call unless --scene-file is also given):
  python debug_cli/run_pipeline.py from-manual --type binary_search \\
      --input '{"array":[1,3,5,7,9,11,13],"target":9}' --job-id test3

  # Inspect a completed job's manifest:
  python debug_cli/run_pipeline.py inspect --job-id test1

  # Just validate a scene JSON file against the schema (no rendering):
  python debug_cli/run_pipeline.py validate-scene --scene-file scene.json

  # Just run frame-quality analysis on an existing video:
  python debug_cli/run_pipeline.py check-frames --video path/to/video.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from packages.scene_schema import Scene
from packages.scene_schema.errors import SceneValidationError
from manim_engine.debug.manifest import RenderManifest
from pydantic import ValidationError


def cmd_validate_scene(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.scene_file).read_text())
    try:
        scene = Scene(**data)
    except ValidationError as e:
        err = SceneValidationError.from_pydantic(e)
        print("INVALID:")
        print(err.message)
        return 1
    print(f"VALID: {scene.visualization_type}, {len(scene.steps)} steps")
    return 0


def cmd_check_frames(args: argparse.Namespace) -> int:
    from manim_engine.debug.frame_quality import analyze_video

    report = analyze_video(
        args.video, sample_fps=args.sample_fps,
        save_frames_dir=args.save_frames_dir,
    )
    print(f"sampled {report.total_frames_sampled} frames")
    print(f"passed: {report.passed}  errors: {report.error_count}  warnings: {report.warning_count}")
    for f in report.worst_frames(10):
        print(f"  t={f.timestamp_s:.2f}s frame#{f.frame_index}:")
        for issue in f.issues:
            print(f"    [{issue.severity.value}] {issue.check}: {issue.message}")
    if args.save_json:
        report.save_json(args.save_json)
        print(f"full report saved to {args.save_json}")
    return 0 if report.passed else 1


def cmd_from_scene(args: argparse.Namespace) -> int:
    from workers.renderer.pipeline.orchestrator import _render_and_validate
    from manim_engine.debug.stage_logger import StageLogger
    from manim_engine.renderer.config import RENDERER_VERSION

    data = json.loads(Path(args.scene_file).read_text())
    scene = Scene(**data)
    job_id = args.job_id or f"debug-{uuid.uuid4().hex[:8]}"
    logger = StageLogger(job_id)
    manifest = RenderManifest(
        job_id=job_id, visualization_type=scene.visualization_type, renderer_version=RENDERER_VERSION
    )
    result = _render_and_validate(scene=scene, logger=logger, manifest=manifest, resolution=None)
    print(result.manifest.print_summary())
    return 0 if result.success else 1


def cmd_from_prompt(args: argparse.Namespace) -> int:
    from workers.renderer.pipeline.orchestrator import run_pipeline_from_prompt

    job_id = args.job_id or f"debug-{uuid.uuid4().hex[:8]}"
    result = run_pipeline_from_prompt(job_id, args.prompt, api_key=args.api_key)
    print(result.manifest.print_summary())
    if result.needs_manual_input:
        print(f"\n>>> No LLM key available at stage '{result.needs_manual_input}'.")
        print(">>> Re-run with `from-manual` (and optionally `from-scene`) to supply input by hand.")
    return 0 if result.success else 1


def cmd_from_manual(args: argparse.Namespace) -> int:
    from workers.renderer.pipeline.orchestrator import run_pipeline_from_manual_classification

    job_id = args.job_id or f"debug-{uuid.uuid4().hex[:8]}"
    input_params = json.loads(args.input) if args.input else {}
    result = run_pipeline_from_manual_classification(
        job_id, args.type, input_params, args.title or args.type, api_key=args.api_key,
    )
    print(result.manifest.print_summary())
    if result.needs_manual_input:
        print(f"\n>>> No LLM key available at stage '{result.needs_manual_input}'.")
        print(">>> Use `from-scene` with a hand-written scene JSON instead.")
    return 0 if result.success else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    manifest_path = Path("debug_runs") / args.job_id / "manifest.json"
    if not manifest_path.exists():
        print(f"No manifest found at {manifest_path}")
        return 1
    manifest = RenderManifest.load(manifest_path)
    print(manifest.print_summary())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate-scene")
    p_validate.add_argument("--scene-file", required=True)
    p_validate.set_defaults(func=cmd_validate_scene)

    p_frames = sub.add_parser("check-frames")
    p_frames.add_argument("--video", required=True)
    p_frames.add_argument("--sample-fps", type=float, default=2.0)
    p_frames.add_argument("--save-frames-dir", default=None)
    p_frames.add_argument("--save-json", default=None)
    p_frames.set_defaults(func=cmd_check_frames)

    p_scene = sub.add_parser("from-scene")
    p_scene.add_argument("--scene-file", required=True)
    p_scene.add_argument("--job-id", default=None)
    p_scene.set_defaults(func=cmd_from_scene)

    p_prompt = sub.add_parser("from-prompt")
    p_prompt.add_argument("--prompt", required=True)
    p_prompt.add_argument("--job-id", default=None)
    p_prompt.add_argument("--api-key", default=None)
    p_prompt.set_defaults(func=cmd_from_prompt)

    p_manual = sub.add_parser("from-manual")
    p_manual.add_argument("--type", required=True)
    p_manual.add_argument("--input", default="{}")
    p_manual.add_argument("--title", default=None)
    p_manual.add_argument("--job-id", default=None)
    p_manual.add_argument("--api-key", default=None)
    p_manual.set_defaults(func=cmd_from_manual)

    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--job-id", required=True)
    p_inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
