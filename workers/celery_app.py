"""Celery app config. Broker/backend both point at Redis by default
(matches docker-compose.yml's `redis` service) — a single Redis instance
is sufficient at MVP scale; splitting broker/backend onto separate
instances is a scaling change for later, not a v1 concern."""
from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "vizr",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.renderer.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Infra-level retry (§21) — distinct from the application-level LLM
    # repair loop (§14). This covers transient failures: a dropped DB
    # connection, Redis hiccup, worker OOM-killed mid-render.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
    task_time_limit=600,   # hard kill
    task_soft_time_limit=540,  # allow cleanup
)
