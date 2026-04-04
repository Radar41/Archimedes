from __future__ import annotations

from temporalio import activity


@activity.defn
async def collect_drift_inputs(subject_id: str) -> dict:
    return {"subject_id": subject_id, "external_state": {}, "canonical_state": {}}


@activity.defn
async def compare_canonical_and_external_state(inputs: dict) -> dict:
    return {"subject_id": inputs["subject_id"], "drift_detected": False, "review_flags": []}
