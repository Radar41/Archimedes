from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from backend.app.workflows.activities.gated_execution import (
        enqueue_or_record_decision,
        evaluate_execution_boundary,
    )

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


@workflow.defn
class GatedExecutionV1Workflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        decision = await workflow.execute_activity(
            evaluate_execution_boundary,
            payload,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACTIVITY_RETRY,
        )
        return await workflow.execute_activity(
            enqueue_or_record_decision,
            decision,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_ACTIVITY_RETRY,
        )
