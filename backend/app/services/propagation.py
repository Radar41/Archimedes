from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.shadow import ReviewFlag


OPERATOR_OWNED_FIELDS = {"title", "objective", "done_condition", "section"}
DEPENDENCY_FIELDS = {"status", "due_date", "blocked_by", "depends_on"}


@dataclass(frozen=True)
class ReviewFlagRecord:
    task_id: uuid.UUID
    flag_type: str
    summary: str
    detail_json: dict[str, Any]
    status: str = "open"


def evaluate_propagation(change_event: dict[str, Any]) -> list[ReviewFlagRecord]:
    downstream_task_ids = change_event.get("downstream_task_ids") or []
    changed_fields = set(change_event.get("changed_fields") or [])
    source_task_id = change_event.get("task_id")
    source_label = change_event.get("task_title") or str(source_task_id or "unknown task")

    if not downstream_task_ids:
        return []

    flags: list[ReviewFlagRecord] = []

    if changed_fields & OPERATOR_OWNED_FIELDS:
        flags.extend(
            ReviewFlagRecord(
                task_id=uuid.UUID(task_id),
                flag_type="operator_review",
                summary=f"Review downstream task after operator-owned field change on {source_label}.",
                detail_json={
                    "source_task_id": source_task_id,
                    "changed_fields": sorted(changed_fields & OPERATOR_OWNED_FIELDS),
                    "rewrite_policy": "operator_owned_fields_are_never_silently_rewritten",
                },
            )
            for task_id in downstream_task_ids
        )

    if changed_fields & DEPENDENCY_FIELDS:
        flags.extend(
            ReviewFlagRecord(
                task_id=uuid.UUID(task_id),
                flag_type="dependency_impact",
                summary=f"Review dependency impact from {source_label}.",
                detail_json={
                    "source_task_id": source_task_id,
                    "changed_fields": sorted(changed_fields & DEPENDENCY_FIELDS),
                    "requires_manual_confirmation": True,
                },
            )
            for task_id in downstream_task_ids
        )

    return flags


def persist_review_flags(
    session: Session,
    flags: list[ReviewFlagRecord],
) -> list[ReviewFlag]:
    """Write ReviewFlagRecord dataclasses to the review_flag table."""
    orm_flags = [
        ReviewFlag(
            task_id=flag.task_id,
            flag_type=flag.flag_type,
            summary=flag.summary,
            detail_json=flag.detail_json,
            status=flag.status,
        )
        for flag in flags
    ]
    session.add_all(orm_flags)
    session.commit()
    for f in orm_flags:
        session.refresh(f)
    return orm_flags
