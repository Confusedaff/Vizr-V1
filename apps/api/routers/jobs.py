"""Jobs router: create jobs (from prompt or manual classification),
check status, list events, and submit manual scene input for jobs stuck
at NEEDS_MANUAL_INPUT.

Every route requires authentication and every job is scoped to the
requesting user — a user can only see/act on their own jobs. A job
belonging to another user returns 404 (not 403), so this endpoint never
even confirms whether a given job_id exists for someone else."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import get_current_user
from apps.api.database import get_db
from apps.api.models.db import Job, JobEvent, JobStatus, User
from apps.api.schemas.job_schemas import (
    CreateJobFromManualRequest,
    CreateJobFromPromptRequest,
    JobEventResponse,
    JobResponse,
    SubmitManualSceneRequest,
)
from packages.scene_schema import VISUALIZATION_TYPES
from workers.renderer.tasks import render_from_manual_task, render_from_prompt_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_owned_job(job_id: str, user: User, db: AsyncSession) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.post("", response_model=JobResponse, status_code=201)
async def create_job_from_prompt(
    body: CreateJobFromPromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    job = Job(
        id=str(uuid.uuid4()), user_id=current_user.id, prompt=body.prompt, status=JobStatus.PENDING
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    render_from_prompt_task.delay(job.id, body.prompt, body.api_key, body.provider)
    return job


@router.post("/manual", response_model=JobResponse, status_code=201)
async def create_job_from_manual(
    body: CreateJobFromManualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    if body.visualization_type not in VISUALIZATION_TYPES:
        raise HTTPException(400, f"Unknown visualization_type. Must be one of {VISUALIZATION_TYPES}")

    job = Job(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        visualization_type=body.visualization_type,
        input_params=body.input,
        title=body.title,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    render_from_manual_task.delay(job.id, body.visualization_type, body.input, body.title, body.api_key, body.provider)
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Job]:
    result = await db.execute(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Job:
    return await _get_owned_job(job_id, current_user, db)


@router.get("/{job_id}/events", response_model=list[JobEventResponse])
async def get_job_events(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[JobEvent]:
    await _get_owned_job(job_id, current_user, db)  # ownership check
    result = await db.execute(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at)
    )
    return list(result.scalars().all())


@router.get("/{job_id}/manifest")
async def get_job_manifest(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    """Returns the full RenderManifest — the same granular per-stage
    timing/status data available via the debug CLI's `inspect` command,
    exposed over HTTP for the web UI's debug panel."""
    job = await _get_owned_job(job_id, current_user, db)
    return job.manifest_json or {}


@router.post("/{job_id}/refresh-url", response_model=JobResponse)
async def refresh_video_url(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Job:
    """Presigned URLs expire (S3_PRESIGNED_URL_EXPIRY_SECONDS). This
    generates a fresh one from the stored object_key without re-uploading
    the video — cheap, and doesn't touch the render pipeline at all."""
    job = await _get_owned_job(job_id, current_user, db)
    if not job.video_object_key:
        raise HTTPException(409, "Job has no uploaded video to refresh a URL for")

    from apps.api.storage.s3_client import StorageError, get_presigned_url

    try:
        job.video_url = get_presigned_url(job.video_object_key)
    except StorageError as e:
        raise HTTPException(502, f"Could not refresh video URL: {e}")

    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/manual-scene", response_model=JobResponse)
async def submit_manual_scene(
    job_id: str,
    body: SubmitManualSceneRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    """Resolves a job that paused at NEEDS_MANUAL_INPUT (no LLM key
    available for plan_scene) by accepting hand-written steps/narration,
    validating them, and resuming straight to the render stage."""
    job = await _get_owned_job(job_id, current_user, db)
    if job.status != JobStatus.NEEDS_MANUAL_INPUT:
        raise HTTPException(409, f"Job is not awaiting manual input (status={job.status.value})")

    from workers.renderer.pipeline.classify import classify_from_manual_input
    from workers.renderer.pipeline.plan_scene import assemble_and_validate_scene
    from packages.scene_schema.errors import SceneValidationError

    try:
        scene = assemble_and_validate_scene(
            visualization_type=job.visualization_type,
            title=job.title or "Visualization",
            input_params=job.input_params or {},
            steps=body.steps,
            narration=body.narration,
        )
    except SceneValidationError as e:
        raise HTTPException(422, e.message)

    from workers.renderer.tasks import _resume_from_manual_scene_task

    job.status = JobStatus.RENDERING
    await db.commit()
    _resume_from_manual_scene_task.delay(job.id, scene.model_dump(mode="json"))
    return job
