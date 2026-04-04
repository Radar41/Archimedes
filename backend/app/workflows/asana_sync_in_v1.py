from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from backend.app.workflows.activities.asana_sync import (
    fetch_asana_project_snapshot,
    upsert_shadow_tasks,
)

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


@workflow.defn
class AsanaSyncInV1Workflow:
    @workflow.run
    async def run(self, project_gid: str) -> dict:
        snapshot = await workflow.execute_activity(
            fetch_asana_project_snapshot,
            project_gid,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACTIVITY_RETRY,
        )
        return await workflow.execute_activity(
            upsert_shadow_tasks,
            snapshot,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACTIVITY_RETRY,
        )
