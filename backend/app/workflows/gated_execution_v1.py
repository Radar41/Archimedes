from __future__ import annotations

from datetime import timedelta

from temporalio import activity, workflow


@activity.defn
async def evaluate_execution_boundary(payload: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for execution boundary evaluation.")


@activity.defn
async def enqueue_or_record_decision(decision: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for gated execution persistence.")


@workflow.defn
class GatedExecutionV1Workflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        decision = await workflow.execute_activity(
            evaluate_execution_boundary,
            payload,
            start_to_close_timeout=timedelta(minutes=2),
        )
        return await workflow.execute_activity(
            enqueue_or_record_decision,
            decision,
            start_to_close_timeout=timedelta(minutes=2),
        )
