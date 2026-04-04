from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import ApprovalGate


def request_approval(
    session: Session,
    *,
    run_id: uuid.UUID,
    gate_type: str,
    rationale: str | None = None,
) -> ApprovalGate:
    gate = ApprovalGate(run_id=run_id, gate_type=gate_type, rationale=rationale)
    session.add(gate)
    session.commit()
    session.refresh(gate)
    return gate


def resolve_approval(
    session: Session,
    *,
    gate_id: uuid.UUID,
    status: str,
    resolved_by: str,
    rationale: str | None = None,
) -> ApprovalGate:
    gate = session.get(ApprovalGate, gate_id)
    if gate is None:
        raise NotImplementedError("Approval gate not found for resolution.")
    gate.status = status
    gate.resolved_by = resolved_by
    gate.rationale = rationale
    gate.resolved_at = datetime.now(UTC)
    session.add(gate)
    session.commit()
    session.refresh(gate)
    return gate


def list_pending_approvals(session: Session) -> list[ApprovalGate]:
    stmt = (
        select(ApprovalGate)
        .where(ApprovalGate.status == "pending")
        .order_by(ApprovalGate.requested_at.asc())
    )
    return session.execute(stmt).scalars().all()
