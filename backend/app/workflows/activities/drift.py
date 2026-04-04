from __future__ import annotations

from temporalio import activity


@activity.defn
async def collect_drift_inputs(subject_id: str) -> dict:
    raise NotImplementedError("Temporal activity placeholder for drift input collection.")


@activity.defn
async def compare_canonical_and_external_state(inputs: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for drift comparison.")
