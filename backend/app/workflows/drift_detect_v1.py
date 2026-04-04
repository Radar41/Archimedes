from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from backend.app.workflows.activities.drift import (
    collect_drift_inputs,
    compare_canonical_and_external_state,
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
    async def run(self, subject_id: str) -> dict:
        inputs = await workflow.execute_activity(
            collect_drift_inputs,
            subject_id,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACTIVITY_RETRY,
        )
        return await workflow.execute_activity(
            compare_canonical_and_external_state,
            inputs,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACTIVITY_RETRY,
        )
