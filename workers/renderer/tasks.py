"""
Celery task: the async entry point that wires the (synchronous, DB-agnostic)
pipeline orchestrator into the job's Postgres row + Redis pub/sub event
stream that the WebSocket gateway (apps/api/websocket/gateway.py) reads
from.

Deliberate separation of concerns: workers/renderer/pipeline/orchestrator.py
knows nothing about Celery, Postgres, or Redis — it's pure functions
operating on dataclasses and the filesystem (debug_runs/). This task is
the only place that bridges "pipeline result" to "job record in the
database" and "live event for connected clients." That separation is what
makes the debug CLI (debug_cli/run_pipeline.py) able to exercise the
exact same pipeline code with zero infrastructure.
"""
from __future__ import annotations

import asyncio
import json

import redis as redis_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from apps.api.database import AsyncSessionLocal
from apps.api.models.db import Job, JobEvent, JobStatus
from workers.celery_app import REDIS_URL, celery_app
from workers.renderer.pipeline.orchestrator import (
    run_pipeline_from_manual_classification,
    run_pipeline_from_prompt,
)

logger = get_task_logger(__name__)

_STATUS_BY_STAGE = {
    "classify": JobStatus.CLASSIFYING,
    "plan_scene": JobStatus.PLANNING_SCENE,
    "repair": JobStatus.REPAIRING,
    "render": JobStatus.RENDERING,
    "validate_render": JobStatus.VALIDATING_RENDER,
}


def _publish_event(job_id: str, payload: dict) -> None:
    """Publish to a per-job Redis pub/sub channel that the WebSocket
    gateway subscribes to. Uses the sync redis client because Celery
    tasks run in a plain thread/process worker, not an event loop."""
    try:
        client = redis_sync.Redis.from_url(REDIS_URL)
        client.publish(f"job_events:{job_id}", json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish job event for %s (non-fatal)", job_id)


async def _record_event(job_id: str, stage: str, event_type: str, message: str | None) -> None:
    async with AsyncSessionLocal() as session:
        event = JobEvent(job_id=job_id, stage=stage, event_type=event_type, message=message)
        session.add(event)
        await session.commit()
    _publish_event(job_id, {"stage": stage, "event_type": event_type, "message": message})


async def _update_job_status(job_id: str, status: JobStatus, **fields) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("Job %s not found when updating status", job_id)
            return
        job.status = status
        for k, v in fields.items():
            setattr(job, k, v)
        await session.commit()
    _publish_event(job_id, {"stage": "job", "event_type": "status_changed", "message": status.value})


async def _upload_and_finalize(job_id: str, *, local_video_path: str, extra_fields: dict) -> None:
    """Shared by both the fresh-pipeline path and the manual-scene-resume
    path: uploads the rendered video to object storage (MinIO/S3), then
    marks the job COMPLETED with the durable video_url. A failure here
    (bucket unreachable, credentials wrong) is a distinct failure mode
    from a render or quality failure — the render itself succeeded, so
    the job is marked FAILED with a specific "upload failed" message
    rather than reusing whatever generic error path a render failure
    would take, since the debugging story for "S3 is down" is completely
    different from "the render crashed."
    """
    from apps.api.storage.s3_client import StorageError, upload_video

    await _update_job_status(job_id, JobStatus.UPLOADING, **extra_fields)
    await _record_event(job_id, "upload", "started", None)

    loop = asyncio.get_event_loop()
    try:
        upload_result = await loop.run_in_executor(
            None, lambda: upload_video(local_video_path, job_id=job_id)
        )
    except StorageError as e:
        await _update_job_status(
            job_id, JobStatus.FAILED,
            error_message=f"Render succeeded but upload to object storage failed: {e}",
        )
        await _record_event(job_id, "upload", "failed", str(e))
        return

    await _update_job_status(
        job_id, JobStatus.COMPLETED,
        video_path=local_video_path,
        video_url=upload_result.url,
        video_object_key=upload_result.object_key,
        error_message=None,
    )
    await _record_event(job_id, "upload", "completed", upload_result.url)
    await _record_event(job_id, "pipeline", "completed", upload_result.url)


async def _backfill_events_from_manifest(job_id: str, manifest_dict: dict) -> None:
    """The interior pipeline stages (plan_scene, render, validate_render)
    run synchronously inside run_pipeline_from_prompt/
    run_pipeline_from_manual_classification via run_in_executor, so they
    only ever produce StageLogger/RenderManifest artifacts — not
    Postgres job_events rows, since that executor call is opaque to this
    task layer until it returns. Rather than thread event-publishing
    callbacks through the whole synchronous pipeline (a much larger
    change for marginal benefit), backfill job_events from the completed
    manifest's stage list once the call returns. This is what makes
    GET /jobs/{id}/events — and therefore the frontend's PipelineTrace —
    show real history immediately after a page load, not just for
    stages that happened to fire while a WebSocket was connected."""
    for stage in manifest_dict.get("stages", []):
        event_type = "completed" if stage.get("success") else ("failed" if stage.get("success") is False else "started")
        await _record_event(job_id, stage["stage"], event_type, stage.get("error"))


async def _run_and_persist(
    job_id: str, *, prompt: str | None, manual: dict | None, api_key: str | None, provider: str | None
) -> None:
    await _update_job_status(job_id, JobStatus.CLASSIFYING)
    await _record_event(job_id, "classify", "started", None)

    loop = asyncio.get_event_loop()

    if manual is not None:
        result = await loop.run_in_executor(
            None,
            lambda: run_pipeline_from_manual_classification(
                job_id, manual["visualization_type"], manual["input"], manual["title"],
                api_key=api_key, provider=provider,
            ),
        )
    else:
        result = await loop.run_in_executor(
            None, lambda: run_pipeline_from_prompt(job_id, prompt, api_key=api_key, provider=provider)
        )

    manifest_dict = result.manifest.to_dict()
    await _backfill_events_from_manifest(job_id, manifest_dict)

    if result.needs_manual_input:
        extra_fields = {}
        if manual is not None:
            extra_fields["input_params"] = manual["input"]
            extra_fields["title"] = manual["title"]
        await _update_job_status(
            job_id, JobStatus.NEEDS_MANUAL_INPUT,
            error_message=result.error, manifest_json=manifest_dict,
            visualization_type=result.manifest.visualization_type,
            **extra_fields,
        )
        await _record_event(job_id, result.needs_manual_input, "needs_manual_input", result.error)
        return

    if not result.success:
        status = JobStatus.QUALITY_FAILED if result.manifest.final_status == "quality_failed" else JobStatus.FAILED
        await _update_job_status(
            job_id, status, error_message=result.error, manifest_json=manifest_dict,
            visualization_type=result.manifest.visualization_type,
            repair_attempts=result.manifest.repair_attempts,
        )
        await _record_event(job_id, "pipeline", "failed", result.error)
        return

    await _update_job_status(
        job_id, JobStatus.VALIDATING_RENDER,
        scene_json=result.scene.model_dump(mode="json") if result.scene else None,
        manifest_json=manifest_dict,
        visualization_type=result.manifest.visualization_type,
        repair_attempts=result.manifest.repair_attempts,
    )
    await _upload_and_finalize(job_id, local_video_path=result.video_path, extra_fields={})


@shared_task(bind=True, name="workers.renderer.tasks.render_from_prompt", max_retries=2)
def render_from_prompt_task(self, job_id: str, prompt: str, api_key: str | None = None, provider: str | None = None):
    try:
        asyncio.run(_run_and_persist(job_id, prompt=prompt, manual=None, api_key=api_key, provider=provider))
    except Exception as exc:
        logger.exception("Infra-level failure for job %s, retrying", job_id)
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, name="workers.renderer.tasks.render_from_manual", max_retries=2)
def render_from_manual_task(
    self, job_id: str, visualization_type: str, input_params: dict, title: str,
    api_key: str | None = None, provider: str | None = None,
):
    try:
        asyncio.run(
            _run_and_persist(
                job_id, prompt=None,
                manual={"visualization_type": visualization_type, "input": input_params, "title": title},
                api_key=api_key, provider=provider,
            )
        )
    except Exception as exc:
        logger.exception("Infra-level failure for job %s, retrying", job_id)
        raise self.retry(exc=exc, countdown=10)


async def _resume_from_manual_scene(job_id: str, scene_dict: dict) -> None:
    from pathlib import Path

    from packages.scene_schema import Scene
    from manim_engine.debug.manifest import RenderManifest
    from manim_engine.debug.stage_logger import StageLogger
    from manim_engine.renderer.config import RENDERER_VERSION
    from workers.renderer.pipeline.orchestrator import _render_and_validate

    scene = Scene(**scene_dict)
    logger_ = StageLogger(job_id)
    manifest = RenderManifest(
        job_id=job_id, visualization_type=scene.visualization_type, renderer_version=RENDERER_VERSION
    )
    manifest.add_note("resumed from manually-submitted scene JSON")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: _render_and_validate(scene=scene, logger=logger_, manifest=manifest, resolution=None)
    )

    manifest_dict = result.manifest.to_dict()
    await _backfill_events_from_manifest(job_id, manifest_dict)
    if not result.success:
        status = JobStatus.QUALITY_FAILED if result.manifest.final_status == "quality_failed" else JobStatus.FAILED
        await _update_job_status(job_id, status, error_message=result.error, manifest_json=manifest_dict)
        await _record_event(job_id, "pipeline", "failed", result.error)
        return

    await _update_job_status(
        job_id, JobStatus.VALIDATING_RENDER,
        scene_json=scene.model_dump(mode="json"), manifest_json=manifest_dict,
    )
    await _upload_and_finalize(job_id, local_video_path=result.video_path, extra_fields={})


@shared_task(bind=True, name="workers.renderer.tasks.resume_from_manual_scene", max_retries=2)
def _resume_from_manual_scene_task(self, job_id: str, scene_dict: dict):
    try:
        asyncio.run(_resume_from_manual_scene(job_id, scene_dict))
    except Exception as exc:
        logger.exception("Infra-level failure resuming job %s, retrying", job_id)
        raise self.retry(exc=exc, countdown=10)
