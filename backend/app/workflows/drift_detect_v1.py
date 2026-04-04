from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from backend.app.workflows.activities.drift import (
        collect_drift_inputs,
        compare_canonical_and_external_state,
        record_drift_findings,
    )

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


@workflow.defn
class DriftDetectV1Workflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict:
        inputs = await workflow.execute_activity(
            collect_drift_inputs,
            payload,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_ACTIVITY_RETRY,
        )
        comparison = await workflow.execute_activity(
            compare_canonical_and_external_state,
            inputs,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_ACTIVITY_RETRY,
        )
        persistence = {"created_flags": 0, "audit_events": 0}
        if comparison["drift_detected"]:
            persistence = await workflow.execute_activity(
                record_drift_findings,
                comparison,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_ACTIVITY_RETRY,
            )
        return {
            "project_gid": payload.get("project_gid"),
            "drift_detected": comparison["drift_detected"],
            "drifts": comparison["drifts"],
            **persistence,
        }
