"""
orchestrator.py — runs the full pipeline (classify -> plan_scene ->
validate -> [repair loop] -> render -> validate_render) for one job,
writing every stage's input/output/timing through StageLogger into
debug_runs/{job_id}/.

This is called identically by:
  - the Celery task (workers/renderer/tasks.py) for real async jobs
  - the debug CLI (debug_cli/run_pipeline.py) for local/manual runs
  - tests (tests/test_pipeline_integration.py)

Two entry points reflecting the two supported starting points:
  - run_pipeline_from_prompt(): natural-language prompt -> classify (LLM
    or raises NeedsManualInput) -> plan_scene (LLM or raises
    NeedsManualInput) -> ...
  - run_pipeline_from_scene(): caller already has a full Scene (e.g. from
    manual input, or a previously-planned scene being re-rendered) ->
    skips straight to render.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from packages.scene_schema import Scene
from packages.scene_schema.errors import SceneValidationError
from manim_engine.debug.manifest import RenderManifest
from manim_engine.debug.stage_logger import StageLogger
from manim_engine.renderer.config import RENDERER_VERSION
from manim_engine.renderer.validate_render import validate_render
from workers.renderer.llm.client import LLMClient
from workers.renderer.pipeline.audio import generate_narration_audio
from workers.renderer.pipeline.classify import (
    ClassificationResult,
    NeedsManualInput,
    classify_from_manual_input,
    classify_prompt,
)
from workers.renderer.pipeline.plan_scene import assemble_and_validate_scene, plan_scene
from workers.renderer.pipeline.render import render_scene
from workers.renderer.pipeline.repair import repair_scene

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class PipelineResult:
    success: bool
    manifest: RenderManifest
    scene: Scene | None = None
    video_path: str | None = None
    job_dir: Path | None = None
    error: str | None = None
    needs_manual_input: str | None = None  # stage name, if a manual-input fallback is needed


def run_pipeline_from_prompt(
    job_id: str,
    prompt: str,
    *,
    api_key: str | None = None,
    provider: str | None = None,
    debug_root: Path | None = None,
    resolution=None,
) -> PipelineResult:
    logger = StageLogger(job_id, root=debug_root)
    manifest = RenderManifest(job_id=job_id, prompt=prompt, renderer_version=RENDERER_VERSION)
    client = LLMClient(api_key=api_key, provider=provider)

    # -- Stage: classify --------------------------------------------------
    stage = logger.stage("classify")
    stage.write_input({"prompt": prompt})
    timing = manifest.start_stage("classify")
    try:
        classification = classify_prompt(prompt, llm_client=client)
        stage.write_output(classification.__dict__)
        manifest.finish_stage(timing, success=True)
        logger.stage_finished("classify", success=True)
    except NeedsManualInput as e:
        stage.finalize(success=False, error=str(e))
        manifest.finish_stage(timing, success=False, error=str(e))
        logger.stage_finished("classify", success=False, error=str(e))
        manifest.final_status = "needs_manual_input"
        manifest.save(logger.manifest_path())
        return PipelineResult(
            success=False, manifest=manifest, error=str(e), needs_manual_input="classify",
            job_dir=logger.root,
        )
    except Exception as e:
        stage.finalize(success=False, error=str(e))
        manifest.finish_stage(timing, success=False, error=str(e))
        logger.stage_finished("classify", success=False, error=str(e))
        manifest.final_status = "failed"
        manifest.save(logger.manifest_path())
        return PipelineResult(success=False, manifest=manifest, error=str(e), job_dir=logger.root)

    stage.finalize(success=True)
    manifest.visualization_type = classification.visualization_type

    return _continue_from_classification(
        job_id=job_id, classification=classification, client=client,
        logger=logger, manifest=manifest, resolution=resolution,
    )


def run_pipeline_from_manual_classification(
    job_id: str,
    visualization_type: str,
    input_params: dict,
    title: str,
    *,
    api_key: str | None = None,
    provider: str | None = None,
    debug_root: Path | None = None,
    resolution=None,
) -> PipelineResult:
    logger = StageLogger(job_id, root=debug_root)
    manifest = RenderManifest(
        job_id=job_id, visualization_type=visualization_type, renderer_version=RENDERER_VERSION
    )
    manifest.add_note("classification supplied manually (no LLM key)")
    client = LLMClient(api_key=api_key, provider=provider)

    classification = classify_from_manual_input(visualization_type, input_params, title)
    return _continue_from_classification(
        job_id=job_id, classification=classification, client=client,
        logger=logger, manifest=manifest, resolution=resolution,
    )


def _continue_from_classification(
    *, job_id, classification: ClassificationResult, client: LLMClient,
    logger: StageLogger, manifest: RenderManifest, resolution,
) -> PipelineResult:
    # -- Stage: plan_scene --------------------------------------------------
    stage = logger.stage("plan_scene")
    stage.write_input(classification.__dict__)
    timing = manifest.start_stage("plan_scene")
    try:
        scene = plan_scene(classification, llm_client=client)
        stage.write_output(scene.model_dump(mode="json"))
        manifest.finish_stage(timing, success=True)
        logger.stage_finished("plan_scene", success=True)
    except NeedsManualInput as e:
        stage.finalize(success=False, error=str(e))
        manifest.finish_stage(timing, success=False, error=str(e))
        manifest.final_status = "needs_manual_input"
        manifest.save(logger.manifest_path())
        return PipelineResult(
            success=False, manifest=manifest, error=str(e), needs_manual_input="plan_scene",
            job_dir=logger.root,
        )
    except SceneValidationError as e:
        # Try the repair loop before giving up entirely.
        stage.finalize(success=False, error=e.message)
        manifest.finish_stage(timing, success=False, error=e.message)
        return _attempt_repair_and_continue(
            classification=classification, client=client, logger=logger, manifest=manifest,
            broken_steps=[], broken_narration=[], error=e, resolution=resolution,
        )
    except Exception as e:
        stage.finalize(success=False, error=str(e))
        manifest.finish_stage(timing, success=False, error=str(e))
        manifest.final_status = "failed"
        manifest.save(logger.manifest_path())
        return PipelineResult(success=False, manifest=manifest, error=str(e), job_dir=logger.root)

    stage.finalize(success=True)
    return _render_and_validate(scene=scene, logger=logger, manifest=manifest, resolution=resolution)


def _attempt_repair_and_continue(
    *, classification, client, logger, manifest, broken_steps, broken_narration, error, resolution,
) -> PipelineResult:
    stage = logger.stage("plan_scene")  # repair happens within the same conceptual stage
    timing = manifest.start_stage("repair", attempt=1)
    repair_result = repair_scene(
        visualization_type=classification.visualization_type,
        title=classification.title,
        input_params=classification.input_params,
        broken_steps=broken_steps,
        broken_narration=broken_narration,
        error=error,
        llm_client=client,
    )
    manifest.repair_attempts = repair_result.attempt_count
    stage.write_output({"attempts": [a.__dict__ for a in repair_result.attempts]}, "repair_attempts.json")

    if not repair_result.succeeded:
        manifest.finish_stage(timing, success=False, error="repair exhausted attempts")
        manifest.final_status = "failed"
        manifest.save(logger.manifest_path())
        return PipelineResult(
            success=False, manifest=manifest,
            error=f"Scene planning failed validation and repair did not succeed: {error}",
            job_dir=logger.root,
        )

    manifest.finish_stage(timing, success=True)
    return _render_and_validate(
        scene=repair_result.scene, logger=logger, manifest=manifest, resolution=resolution
    )


def _render_and_validate(*, scene: Scene, logger: StageLogger, manifest: RenderManifest, resolution) -> PipelineResult:
    # -- Stage: audio (narration text-to-speech) -------------------------
    # Runs before render and outside any sandbox: edge-tts needs network
    # access that the Docker sandbox (SANDBOX_MODE=docker) deliberately
    # denies the render step itself. Never fatal — a TTS hiccup degrades
    # to the pipeline's pre-existing behavior (captions, no audio), it
    # never fails the job.
    audio_stage = logger.stage("audio")
    audio_timing = manifest.start_stage("audio")
    audio_result = generate_narration_audio(scene, output_dir=audio_stage.stage_dir)
    audio_stage.write_output({
        "voice": audio_result.voice,
        "lines_synthesized": len(audio_result.audio_map),
        "lines_requested": len(audio_result.audio_map) + len(audio_result.errors),
        "errors": audio_result.errors,
    })
    manifest.finish_stage(audio_timing, success=True)
    audio_stage.finalize(success=True)
    logger.stage_finished("audio", success=True)
    if audio_result.errors:
        manifest.add_note(
            f"narration audio: {len(audio_result.errors)} line(s) failed to synthesize, "
            "continuing with captions only for those lines"
        )

    # -- Stage: render --------------------------------------------------
    stage = logger.stage("render")
    stage.write_input(scene.model_dump(mode="json"))
    timing = manifest.start_stage("render")

    render_kwargs = {"audio_map": audio_result.audio_map}
    if resolution:
        render_kwargs["resolution"] = resolution

    render_result = render_scene(scene, output_dir=stage.stage_dir, project_root=PROJECT_ROOT, **render_kwargs)
    stage.write_text("stdout.log", render_result.stdout)
    stage.write_text("stderr.log", render_result.stderr)

    if not render_result.success:
        stage.finalize(success=False, error=render_result.error, extra={"stderr_tail": render_result.stderr[-2000:]})
        manifest.finish_stage(timing, success=False, error=render_result.error)
        manifest.final_status = "failed"
        manifest.save(logger.manifest_path())
        return PipelineResult(
            success=False, manifest=manifest,
            error=f"Render failed ({render_result.error}). See {stage.stage_dir}/stderr.log",
            scene=scene, job_dir=logger.root,
        )

    manifest.finish_stage(timing, success=True)
    stage.finalize(success=True, extra={"video_path": render_result.video_path})
    if render_result.construction_warnings:
        for w in render_result.construction_warnings:
            manifest.add_note(f"construction warning: {w}")

    # -- Stage: validate_render --------------------------------------------------
    stage2 = logger.stage("validate_render")
    timing2 = manifest.start_stage("validate_render")
    worst_frames_dir = stage2.stage_dir / "worst_frames"
    validation = validate_render(
        render_result.video_path,
        construction_warnings=render_result.construction_warnings,
        save_frames_dir=worst_frames_dir,
    )
    validation.save_json(stage2.stage_dir / "report.json")
    manifest.finish_stage(timing2, success=validation.valid, error=None if validation.valid else "; ".join(validation.failure_reasons))
    stage2.finalize(success=validation.valid, error=None if validation.valid else "; ".join(validation.failure_reasons))

    manifest.video_path = render_result.video_path
    manifest.video_duration_seconds = validation.duration_seconds
    manifest.quality_passed = validation.valid
    if validation.quality_report:
        manifest.quality_error_count = validation.quality_report.error_count
        manifest.quality_warning_count = validation.quality_report.warning_count

    manifest.final_status = "completed" if validation.valid else "quality_failed"
    manifest.save(logger.manifest_path())

    return PipelineResult(
        success=validation.valid,
        manifest=manifest,
        scene=scene,
        video_path=render_result.video_path if validation.valid else None,
        job_dir=logger.root,
        error=None if validation.valid else validation.as_repair_context(),
    )
