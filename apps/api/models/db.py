"""
SQLAlchemy models. Jobs are scoped to a User via JWT-authenticated
requests (see apps/api/auth/). `video_path` holds the local/volume path a
render produced (used during rendering); once uploaded, `video_url` holds
the durable MinIO/S3 object URL clients should actually use — see
apps/api/storage/s3_client.py.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship(back_populates="user")


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    PLANNING_SCENE = "planning_scene"
    VALIDATING_SCENE = "validating_scene"
    NEEDS_MANUAL_INPUT = "needs_manual_input"
    RENDERING = "rendering"
    VALIDATING_RENDER = "validating_render"
    REPAIRING = "repairing"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    QUALITY_FAILED = "quality_failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    visualization_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.PENDING, index=True
    )
    scene_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    video_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_attempts: Mapped[int] = mapped_column(Integer, default=0)
    manifest_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User | None"] = relationship(back_populates="jobs")
    events: Mapped[list["JobEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobEvent(Base):
    """Append-only event log per job — what the WebSocket gateway
    broadcasts live, and what a REST client can page through for a job's
    full history without needing debug_runs/ filesystem access."""

    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(32))  # started|progress|completed|failed
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    job: Mapped["Job"] = relationship(back_populates="events")
