from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from backend.app.models.shadow import AuditEvent


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

# Pre-compile word-boundary patterns for each keyword set
_HIGH_RISK_PATTERNS = [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in HIGH_RISK_KEYWORDS]
_ADJACENT_PATTERNS = [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in ADJACENT_KEYWORDS]


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _has_high_risk(text: str) -> bool:
    return any(p.search(text) for p in _HIGH_RISK_PATTERNS)


def _has_adjacent(text: str) -> bool:
    return any(p.search(text) for p in _ADJACENT_PATTERNS)


def evaluate_scope(
    current_intent: str,
    proposed_step: str,
    requested_operation: str,
    *,
    session: Session | None = None,
    subject_id: uuid.UUID | None = None,
) -> ScopeEvaluation:
    intent = _normalize(current_intent)
    step = _normalize(proposed_step)
    operation = _normalize(requested_operation)

    if _has_high_risk(step) or operation in WRITE_OPERATIONS:
        result = ScopeEvaluation(
            classification=ScopeClassification.C_NEW_PROJECT_ISOLATE,
            decision=ScopeDecision.REQUIRE_ESCALATION,
            rationale="Step crosses a high-risk or explicitly isolated execution boundary.",
        )
    else:
        shared_terms = {token for token in step.split() if len(token) > 3} & {
            token for token in intent.split() if len(token) > 3
        }
        if shared_terms and not _has_adjacent(step):
            result = ScopeEvaluation(
                classification=ScopeClassification.A_CONTINUE,
                decision=ScopeDecision.ALLOW,
                rationale="Step materially overlaps with the active intent and stays in-bounds.",
            )
        else:
            result = ScopeEvaluation(
                classification=ScopeClassification.B_ADJACENT_DEFER,
                decision=ScopeDecision.BLOCK_AND_QUEUE,
                rationale="Step is related but should be queued outside the active execution lane.",
            )

    # Write audit trail if a session is available
    if session is not None:
        audit_event = AuditEvent(
            event_type="scope_gate_evaluation",
            subject_type="scope_gate",
            subject_id=subject_id or uuid.uuid4(),
            summary=f"{result.classification} / {result.decision}: {result.rationale}",
            detail_json={
                "current_intent": current_intent,
                "proposed_step": proposed_step,
                "requested_operation": requested_operation,
                "classification": result.classification,
                "decision": result.decision,
            },
        )
        session.add(audit_event)
        session.commit()

    return result
