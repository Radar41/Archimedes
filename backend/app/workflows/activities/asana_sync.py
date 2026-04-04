from __future__ import annotations

from temporalio import activity


@activity.defn
async def fetch_asana_project_snapshot(project_gid: str) -> dict:
    raise NotImplementedError("Temporal activity placeholder for inbound Asana sync fetch.")


@activity.defn
async def upsert_shadow_tasks(snapshot: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for shadow task upsert.")
