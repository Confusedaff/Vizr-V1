"""Async SQLAlchemy engine/session setup. DATABASE_URL follows the
standard postgresql+asyncpg:// scheme; docker-compose.yml sets this to
point at the `db` service."""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://aiviz:aiviz@localhost:5432/aiviz"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables if they don't exist. For an MVP this stands in for
    Alembic migrations (infrastructure/docker/init-db.sql also creates
    the database itself) — a real production deployment should switch to
    `alembic upgrade head` in the entrypoint instead of this."""
    from apps.api.models.db import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
