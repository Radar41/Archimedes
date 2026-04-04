from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScopeClassification(StrEnum):
    A_CONTINUE = "A_CONTINUE"
    B_ADJACENT_DEFER = "B_ADJACENT_DEFER"
    C_NEW_PROJECT_ISOLATE = "C_NEW_PROJECT_ISOLATE"


class ScopeDecision(StrEnum):
    ALLOW = "ALLOW"
    BLOCK_AND_QUEUE = "BLOCK_AND_QUEUE"
    REQUIRE_ESCALATION = "REQUIRE_ESCALATION"


@dataclass(frozen=True)
class ScopeEvaluation:
    classification: ScopeClassification
    decision: ScopeDecision
    rationale: str


WRITE_OPERATIONS = {
    "create_project",
    "delete_task",
    "provision_integration",
    "write_external_system",
}
HIGH_RISK_KEYWORDS = {
    "architecture",
    "schema",
    "migration",
    "new project",
    "replace",
    "cutover",
    "production",
}
ADJACENT_KEYWORDS = {
    "later",
    "follow up",
    "follow-up",
    "backlog",
    "adjacent",
    "next",
    "separate",
}


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def evaluate_scope(
    current_intent: str,
    proposed_step: str,
    requested_operation: str,
) -> ScopeEvaluation:
    intent = _normalize(current_intent)
    step = _normalize(proposed_step)
    operation = _normalize(requested_operation)

    if any(keyword in step for keyword in HIGH_RISK_KEYWORDS) or operation in WRITE_OPERATIONS:
        return ScopeEvaluation(
            classification=ScopeClassification.C_NEW_PROJECT_ISOLATE,
            decision=ScopeDecision.REQUIRE_ESCALATION,
            rationale="Step crosses a high-risk or explicitly isolated execution boundary.",
        )

    shared_terms = {token for token in step.split() if len(token) > 3} & {
        token for token in intent.split() if len(token) > 3
    }
    if shared_terms and not any(keyword in step for keyword in ADJACENT_KEYWORDS):
        return ScopeEvaluation(
            classification=ScopeClassification.A_CONTINUE,
            decision=ScopeDecision.ALLOW,
            rationale="Step materially overlaps with the active intent and stays in-bounds.",
        )

    return ScopeEvaluation(
        classification=ScopeClassification.B_ADJACENT_DEFER,
        decision=ScopeDecision.BLOCK_AND_QUEUE,
        rationale="Step is related but should be queued outside the active execution lane.",
    )
