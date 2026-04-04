from __future__ import annotations

from temporalio import activity


@activity.defn
async def evaluate_execution_boundary(payload: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for execution boundary evaluation.")


@activity.defn
async def enqueue_or_record_decision(decision: dict) -> dict:
    raise NotImplementedError("Temporal activity placeholder for gated execution persistence.")
