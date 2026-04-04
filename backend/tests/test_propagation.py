from __future__ import annotations

import uuid

from backend.app.services.propagation import evaluate_propagation


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

    assert len(flags) == 2
    assert all(flag.flag_type == "operator_review" for flag in flags)
    assert all(
        flag.detail_json["rewrite_policy"] == "operator_owned_fields_are_never_silently_rewritten"
        for flag in flags
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
