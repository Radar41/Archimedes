from __future__ import annotations

from temporalio import activity

from backend.app.db import SessionLocal
from backend.app.services.inbound_sync import run_inbound_sync


@activity.defn
async def fetch_asana_project_snapshot(project_gid: str) -> dict:
    with SessionLocal() as session:
        return await run_inbound_sync(session=session, project_gid=project_gid)


@activity.defn
async def upsert_shadow_tasks(snapshot: dict) -> dict:
    return snapshot
