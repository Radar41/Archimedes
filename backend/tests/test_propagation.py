from __future__ import annotations

import uuid

from sqlalchemy import select

from backend.app.models.shadow import ReviewFlag, ShadowTask
from backend.app.services.propagation import evaluate_propagation, persist_review_flags


def test_propagation_creates_operator_review_flags() -> None:
    downstream_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    flags = evaluate_propagation(
        {
            "task_id": str(uuid.uuid4()),
            "task_title": "Hydra Runtime Bootstrap",
            "changed_fields": ["title", "status"],
            "downstream_task_ids": downstream_ids,
        }
    )

    operator_flags = [f for f in flags if f.flag_type == "operator_review"]
    assert len(operator_flags) == 2
    assert all(
        flag.detail_json["rewrite_policy"] == "operator_owned_fields_are_never_silently_rewritten"
        for flag in operator_flags
    )


def test_propagation_creates_dependency_impact_flags() -> None:
    downstream_id = str(uuid.uuid4())

    flags = evaluate_propagation(
        {
            "task_id": str(uuid.uuid4()),
            "task_title": "Asana Bridge",
            "changed_fields": ["status"],
            "downstream_task_ids": [downstream_id],
        }
    )

    assert len(flags) == 1
    assert flags[0].flag_type == "dependency_impact"
    assert flags[0].detail_json["requires_manual_confirmation"] is True


def test_propagation_returns_no_flags_without_downstream_impacts() -> None:
    flags = evaluate_propagation(
        {
            "task_id": str(uuid.uuid4()),
            "task_title": "Audit Trail",
            "changed_fields": ["custom_field"],
            "downstream_task_ids": [],
        }
    )

    assert flags == []


def test_propagation_creates_both_flag_types_for_overlapping_fields() -> None:
    """When changed_fields span both operator-owned and dependency categories,
    both flag types must be produced — not just the first match."""
    downstream_id = str(uuid.uuid4())

    flags = evaluate_propagation(
        {
            "task_id": str(uuid.uuid4()),
            "task_title": "Overlap Task",
            "changed_fields": ["title", "status"],
            "downstream_task_ids": [downstream_id],
        }
    )

    flag_types = {f.flag_type for f in flags}
    assert flag_types == {"operator_review", "dependency_impact"}


def test_persist_review_flags_writes_to_db(session) -> None:
    task = ShadowTask(
        asana_gid=str(uuid.uuid4()),
        title="Persist Test",
        status="in_progress",
        section="Test",
        custom_fields_json={},
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    flags = evaluate_propagation(
        {
            "task_id": str(task.id),
            "task_title": task.title,
            "changed_fields": ["status"],
            "downstream_task_ids": [str(task.id)],
        }
    )
    persisted = persist_review_flags(session, flags)

    db_flags = session.execute(select(ReviewFlag)).scalars().all()
    assert len(persisted) == 1
    assert len(db_flags) == 1
    assert db_flags[0].flag_type == "dependency_impact"
