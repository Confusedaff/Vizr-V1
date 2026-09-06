"""
Debug router: exposes the granular debuggability tooling
(manim_engine/debug/) over HTTP, so a frontend debug panel — or a curl
call — can inspect a job's pipeline without shelling into the server's
filesystem.

This mirrors exactly what debug_cli/run_pipeline.py does locally; same
underlying functions, different transport. Every job-scoped route
requires the requesting user to own that job (checked against the
Postgres Job row, not just presence on disk) — debug artifacts can
contain prompt text and scene content, so they're as sensitive as the
job itself.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import get_current_user
from apps.api.database import get_db
from apps.api.models.db import Job, User
from manim_engine.debug.frame_quality import analyze_video
from manim_engine.debug.manifest import RenderManifest

router = APIRouter(prefix="/debug", tags=["debug"])

DEBUG_RUNS_ROOT = Path("debug_runs")


async def _check_job_ownership(job_id: str, user: User, db: AsyncSession) -> None:
    result = await db.execute(select(Job.id).where(Job.id == job_id, Job.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, "Job not found")


@router.get("/jobs/{job_id}/manifest")
async def get_manifest(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    await _check_job_ownership(job_id, current_user, db)
    path = DEBUG_RUNS_ROOT / job_id / "manifest.json"
    if not path.exists():
        raise HTTPException(404, f"No debug manifest found for job {job_id}")
    return RenderManifest.load(path).to_dict()


@router.get("/jobs/{job_id}/stages")
async def list_stages(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    """Lists every stage directory and its files — the filesystem-level
    view of debug_runs/{job_id}/, useful for a UI that wants to let a
    developer drill into e.g. 06_render/stderr.log directly."""
    await _check_job_ownership(job_id, current_user, db)
    job_dir = DEBUG_RUNS_ROOT / job_id
    if not job_dir.exists():
        raise HTTPException(404, f"No debug directory found for job {job_id}")
    stages = {}
    for stage_dir in sorted(job_dir.iterdir()):
        if stage_dir.is_dir():
            stages[stage_dir.name] = [f.name for f in stage_dir.iterdir()]
    return stages


@router.get("/jobs/{job_id}/stages/{stage_name}/{file_name}")
async def get_stage_file(
    job_id: str,
    stage_name: str,
    file_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _check_job_ownership(job_id, current_user, db)
    # Reject path-traversal attempts in the stage/file segments explicitly
    # — FastAPI path params can still contain "..", so this is not purely
    # defense-in-depth.
    if ".." in stage_name or ".." in file_name or "/" in stage_name or "/" in file_name:
        raise HTTPException(400, "Invalid path segment")

    path = DEBUG_RUNS_ROOT / job_id / stage_name / file_name
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    if path.suffix == ".json":
        import json

        return json.loads(path.read_text())
    return {"content": path.read_text(errors="replace")}


@router.get("/jobs/{job_id}/quality-report")
async def get_quality_report(
    job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    await _check_job_ownership(job_id, current_user, db)
    path = DEBUG_RUNS_ROOT / job_id / "07_validate_render" / "report.json"
    if not path.exists():
        raise HTTPException(404, "No quality report found for this job")
    import json

    return json.loads(path.read_text())


@router.post("/check-video-quality")
async def check_video_quality(
    file: UploadFile, current_user: User = Depends(get_current_user)
) -> dict:
    """Ad-hoc quality check for an arbitrary uploaded video — useful for
    debugging a render pulled from elsewhere (e.g. downloaded from S3)
    without needing the original job_id. Requires auth (any logged-in
    user) but has no job to check ownership against."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        report = analyze_video(tmp_path, sample_fps=2.0)
        return report.to_dict()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
