from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from temporalio import activity

from backend.app.adapters.asana.service import create_story, update_task
from backend.app.db import SessionLocal
from backend.app.models.shadow import ShadowTask, SyncCursor
from backend.app.services.inbound_sync import run_inbound_sync


def _require_idempotency_key(payload: dict) -> str:
    idempotency_key = payload.get("idempotency_key")
    if not idempotency_key:
        raise ValueError("idempotency_key is required for Asana workflow activities.")
    return str(idempotency_key)


def _serialize_shadow_tasks(session) -> dict[str, dict]:
    tasks = session.execute(select(ShadowTask)).scalars().all()
    return {
        task.asana_gid: {
            "id": str(task.id),
            "asana_gid": task.asana_gid,
            "title": task.title,
            "status": task.status,
            "section": task.section,
            "custom_fields_json": task.custom_fields_json,
            "updated_at": task.updated_at.isoformat(),
        }
        for task in tasks
    }


@activity.defn
async def sync_tasks_activity(payload: dict) -> dict:
    _require_idempotency_key(payload)
    project_gid = str(payload["project_gid"])
    with SessionLocal() as session:
        before_snapshot = _serialize_shadow_tasks(session)
        sync_result = await run_inbound_sync(session=session, project_gid=project_gid)
        cursor = session.execute(
            select(SyncCursor).where(SyncCursor.source == f"asana_project:{project_gid}")
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if cursor is None:
            cursor = SyncCursor(
                source=f"asana_project:{project_gid}",
                cursor_value=now.isoformat(),
                updated_at=now,
            )
        else:
            cursor.cursor_value = now.isoformat()
            cursor.updated_at = now
        session.add(cursor)
        session.commit()
        after_snapshot = _serialize_shadow_tasks(session)
        return {
            "project_gid": project_gid,
            "sync_result": sync_result,
            "before_snapshot": before_snapshot,
            "after_snapshot": after_snapshot,
        }


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
