from __future__ import annotations

from backend.app.services.scope_gate import (
    ScopeClassification,
    ScopeDecision,
    evaluate_scope,
)


def test_scope_gate_allows_in_scope_continuation() -> None:
    result = evaluate_scope(
        current_intent="sync Asana tasks into the shadow task ledger",
        proposed_step="sync another page of Asana tasks into the shadow task ledger",
        requested_operation="read_sync",
    )

    assert result.classification == ScopeClassification.A_CONTINUE
    assert result.decision == ScopeDecision.ALLOW


def test_scope_gate_queues_adjacent_work() -> None:
    result = evaluate_scope(
        current_intent="ingest webhook payloads into inbox events",
        proposed_step="create a follow-up backlog item for operator review later",
        requested_operation="queue_follow_up",
    )

    assert result.classification == ScopeClassification.B_ADJACENT_DEFER
    assert result.decision == ScopeDecision.BLOCK_AND_QUEUE


def test_scope_gate_escalates_new_project_or_high_risk_work() -> None:
    result = evaluate_scope(
        current_intent="stabilize the inbound sync path",
        proposed_step="replace the schema and start a new project cutover",
        requested_operation="create_project",
    )

    assert result.classification == ScopeClassification.C_NEW_PROJECT_ISOLATE
    assert result.decision == ScopeDecision.REQUIRE_ESCALATION
