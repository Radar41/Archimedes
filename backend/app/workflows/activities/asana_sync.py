from __future__ import annotations

from temporalio import activity

from backend.app.db import SessionLocal
from backend.app.services.inbound_sync import consume_pending_inbox_events, run_inbound_sync


@activity.defn
async def fetch_asana_project_snapshot(project_gid: str) -> dict:
    with SessionLocal() as session:
        return await run_inbound_sync(session=session, project_gid=project_gid)


@activity.defn
async def upsert_shadow_tasks(snapshot: dict) -> dict:
    project_gid = str(snapshot["project_gid"])
    changed_task_gids = snapshot.get("changed_task_gids")
    with SessionLocal() as session:
        sync_result = await run_inbound_sync(
            session=session,
            project_gid=project_gid,
            changed_task_gids=list(changed_task_gids) if changed_task_gids else None,
        )
    return {
        "project_gid": project_gid,
        "sync_result": sync_result,
        "changed_task_gids": sync_result["task_gids"],
    }


@activity.defn
async def consume_inbox_events(project_gid: str) -> dict:
    with SessionLocal() as session:
        return await consume_pending_inbox_events(session=session, project_gid=project_gid)
