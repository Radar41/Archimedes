from __future__ import annotations

from datetime import timedelta

from temporalio import activity, workflow


@activity.defn
async def collect_drift_inputs(subject_id: str) -> dict:
    raise NotImplementedError("Temporal activity placeholder for drift input collection.")


@activity.defn
async def compare_canonical_and_external_state(inputs: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for drift comparison.")


@workflow.defn
class DriftDetectV1Workflow:
    @workflow.run
    async def run(self, subject_id: str) -> dict:
        inputs = await workflow.execute_activity(
            collect_drift_inputs,
            subject_id,
            start_to_close_timeout=timedelta(minutes=2),
        )
        return await workflow.execute_activity(
            compare_canonical_and_external_state,
            inputs,
            start_to_close_timeout=timedelta(minutes=2),
        )
