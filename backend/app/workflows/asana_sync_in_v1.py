from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from backend.app.workflows.activities.asana_activities import sync_tasks_activity
    from backend.app.workflows.drift_detect_v1 import DriftDetectV1Workflow

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


def _generate_change_events(before_snapshot: dict[str, dict], after_snapshot: dict[str, dict]) -> list[dict[str, Any]]:
    change_events: list[dict[str, Any]] = []
    all_keys = sorted(set(before_snapshot) | set(after_snapshot))
    for asana_gid in all_keys:
        before = before_snapshot.get(asana_gid)
        after = after_snapshot.get(asana_gid)
        if before == after:
            continue
        if before is None:
            event_type = "created"
            changed_fields = sorted(after.keys())
        elif after is None:
            event_type = "deleted"
            changed_fields = sorted(before.keys())
        else:
            event_type = "updated"
            changed_fields = sorted(
                field for field in set(before) | set(after) if before.get(field) != after.get(field)
            )
        change_events.append(
            {
                "event_type": event_type,
                "asana_gid": asana_gid,
                "changed_fields": changed_fields,
                "before": before,
                "after": after,
            }
        )
    return change_events


@workflow.defn
class AsanaSyncInV1Workflow:
    @workflow.run
    async def run(self, project_gid: str) -> dict:
        sync_payload = await workflow.execute_activity(
            sync_tasks_activity,
            {"project_gid": project_gid, "idempotency_key": f"asana-sync:{project_gid}"},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_ACTIVITY_RETRY,
        )
        change_events = _generate_change_events(
            sync_payload["before_snapshot"],
            sync_payload["after_snapshot"],
        )
        drift_result: dict[str, Any] | None = None
        if change_events:
            drift_result = await workflow.execute_child_workflow(
                DriftDetectV1Workflow.run,
                {"project_gid": project_gid, "change_events": change_events},
                id=f"drift-detect:{project_gid}:{len(change_events)}",
            )

        return {
            **sync_payload["sync_result"],
            "change_events": change_events,
            "drift_triggered": bool(change_events),
            "drift_result": drift_result,
        }
