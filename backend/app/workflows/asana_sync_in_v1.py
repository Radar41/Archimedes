from __future__ import annotations

from datetime import timedelta

from temporalio import activity, workflow


@activity.defn
async def fetch_asana_project_snapshot(project_gid: str) -> dict:
    raise NotImplementedError("Temporal activity placeholder for inbound Asana sync fetch.")


@activity.defn
async def upsert_shadow_tasks(snapshot: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for shadow task upsert.")


@workflow.defn
class AsanaSyncInV1Workflow:
    @workflow.run
    async def run(self, project_gid: str) -> dict:
        snapshot = await workflow.execute_activity(
            fetch_asana_project_snapshot,
            project_gid,
            start_to_close_timeout=timedelta(minutes=2),
        )
        return await workflow.execute_activity(
            upsert_shadow_tasks,
            snapshot,
            start_to_close_timeout=timedelta(minutes=2),
        )
