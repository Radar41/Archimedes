from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import AuditEvent


def write_audit_event(
    session: Session,
    *,
    event_type: str,
    subject_type: str,
    subject_id: uuid.UUID,
    summary: str,
    detail_json: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        subject_type=subject_type,
        subject_id=subject_id,
        summary=summary,
        detail_json=detail_json or {},
        trace_id=trace_id,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_audit_events(
    session: Session,
    *,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if subject_type is not None:
        stmt = stmt.where(AuditEvent.subject_type == subject_type)
    if subject_id is not None:
        stmt = stmt.where(AuditEvent.subject_id == subject_id)
    return session.execute(stmt).scalars().all()
