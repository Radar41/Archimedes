from __future__ import annotations

from temporalio import activity

from backend.app.workflows.activities.asana_activities import sync_tasks_activity


@activity.defn
async def fetch_asana_project_snapshot(project_gid: str) -> dict:
    return await sync_tasks_activity(
        {"project_gid": project_gid, "idempotency_key": f"asana-sync:{project_gid}"}
    )


@activity.defn
async def upsert_shadow_tasks(snapshot: dict) -> dict:
    return snapshot
