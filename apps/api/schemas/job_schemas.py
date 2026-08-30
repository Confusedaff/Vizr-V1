"""API-layer request/response models — distinct from packages/scene_schema,
which is the *rendering* contract. These are the *HTTP* contract."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from apps.api.models.db import JobStatus
from packages.scene_schema import VISUALIZATION_TYPES


class CreateJobFromPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    api_key: str | None = Field(
        default=None,
        description="Optional per-request Anthropic API key. If omitted, "
        "the server falls back to any operator-configured key, and if "
        "none is available, the job will pause with status "
        "'needs_manual_input' at the classify stage.",
    )


class CreateJobFromManualRequest(BaseModel):
    visualization_type: str = Field(description=f"One of {VISUALIZATION_TYPES}")
    input: dict = Field(default_factory=dict)
    title: str = Field(default="Visualization", max_length=100)
    api_key: str | None = None


class SubmitManualSceneRequest(BaseModel):
    """Used to resolve a job stuck at NEEDS_MANUAL_INPUT (plan_scene
    stage) by supplying steps/narration directly."""

    steps: list[dict]
    narration: list[str] = Field(default_factory=list)


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    prompt: str | None
    visualization_type: str | None
    video_path: str | None
    video_url: str | None
    error_message: str | None
    repair_attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobEventResponse(BaseModel):
    stage: str
    event_type: str
    message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
