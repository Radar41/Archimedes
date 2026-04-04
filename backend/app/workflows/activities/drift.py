from __future__ import annotations

from temporalio import activity


@activity.defn
async def collect_drift_inputs(subject_id: str) -> dict:
    # TODO(Phase 3): fetch external state from Asana/GitHub and canonical state from shadow_tasks
    raise NotImplementedError("Drift input collection not yet implemented.")


@activity.defn
async def compare_canonical_and_external_state(inputs: dict) -> dict:
    # TODO(Phase 3): compare canonical vs external state and produce review flags
    raise NotImplementedError("Drift comparison not yet implemented.")
