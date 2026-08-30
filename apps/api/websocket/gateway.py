"""
WebSocket gateway: clients connect to /ws/jobs/{job_id}?token=... and
receive every JobEvent (stage started/progress/completed/failed) as it
happens, sourced from the Redis pub/sub channel the Celery task publishes
to (workers/renderer/tasks.py::_publish_event).

Auth note: WebSocket connections can't send an Authorization header from
a browser EventSource/WebSocket API, so the access token is passed as a
query parameter instead (?token=...) and validated the same way as the
REST routes (apps.api.auth.security.decode_access_token) before the
connection is accepted. Job ownership is checked against Postgres before
subscribing, so a valid token for someone else's job still gets rejected.

This gateway is a thin bridge, not a source of truth — the Postgres
`job_events` table (and the debug_runs/ filesystem artifacts) remain the
durable record; a client that reconnects after missing events should
call GET /jobs/{job_id}/events to catch up, then open the socket for
anything after that.
"""
from __future__ import annotations

import json

import redis.asyncio as redis_async
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from apps.api.auth.security import InvalidTokenError, decode_access_token
from apps.api.database import AsyncSessionLocal
from apps.api.models.db import Job
from workers.celery_app import REDIS_URL

router = APIRouter()


async def _authorize_job_access(token: str | None, job_id: str) -> bool:
    if not token:
        return False
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        return False

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Job.id).where(Job.id == job_id, Job.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None


@router.websocket("/ws/jobs/{job_id}")
async def job_events_ws(websocket: WebSocket, job_id: str, token: str | None = None) -> None:
    authorized = await _authorize_job_access(token, job_id)
    if not authorized:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    client = redis_async.Redis.from_url(REDIS_URL)
    pubsub = client.pubsub()
    channel = f"job_events:{job_id}"
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if message is not None:
                payload = message["data"]
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                await websocket.send_text(payload)
            else:
                # Heartbeat so the client (and any proxy) knows the
                # connection is still alive even during long render waits.
                await websocket.send_text(json.dumps({"stage": "gateway", "event_type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await client.close()
