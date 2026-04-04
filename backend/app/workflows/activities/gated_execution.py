from __future__ import annotations

from temporalio import activity

from backend.app.services.scope_gate import evaluate_scope


@activity.defn
async def evaluate_execution_boundary(payload: dict) -> dict:
    evaluation = evaluate_scope(
        current_intent=str(payload["current_intent"]),
        proposed_step=str(payload["proposed_step"]),
        requested_operation=str(payload["requested_operation"]),
    )
    return {
        "classification": evaluation.classification.value,
        "decision": evaluation.decision.value,
        "rationale": evaluation.rationale,
    }


@activity.defn
async def enqueue_or_record_decision(decision: dict) -> dict:
    return decision
