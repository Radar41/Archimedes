from __future__ import annotations

from temporalio import activity

from backend.app.adapters.asana.service import create_story, update_task
from backend.app.db import SessionLocal
from backend.app.services.inbound_sync import run_inbound_sync


def _require_idempotency_key(payload: dict) -> str:
    idempotency_key = payload.get("idempotency_key")
    if not idempotency_key:
        raise ValueError("idempotency_key is required for Asana workflow activities.")
    return str(idempotency_key)


@activity.defn
async def sync_tasks_activity(payload: dict) -> dict:
    _require_idempotency_key(payload)
    project_gid = str(payload["project_gid"])
    with SessionLocal() as session:
        return await run_inbound_sync(session=session, project_gid=project_gid)


@activity.defn
async def post_evidence_comment_activity(payload: dict) -> dict:
    idempotency_key = _require_idempotency_key(payload)
    return await create_story(
        task_gid=str(payload["task_gid"]),
        text=str(payload["text"]),
        idempotency_key=idempotency_key,
    )


@activity.defn
async def update_task_status_activity(payload: dict) -> dict:
    idempotency_key = _require_idempotency_key(payload)
    return await update_task(
        task_gid=str(payload["task_gid"]),
        updates={"completed": bool(payload["completed"])},
        idempotency_key=idempotency_key,
    )
