from __future__ import annotations

from backend.app.models.shadow import WorkflowRun
from backend.app.services.approval import (
    list_pending_approvals,
    request_approval,
    resolve_approval,
)


def _seed_run(session) -> WorkflowRun:
    run = WorkflowRun(
        workflow_name="gated_execution_v1",
        workflow_version=1,
        status="running",
        archimedes_object_ref={"task_id": "123"},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def test_approval_lifecycle(session) -> None:
    run = _seed_run(session)

    gate = request_approval(
        session,
        run_id=run.id,
        gate_type="human_escalation",
        rationale="Needs operator confirmation for elevated command scope.",
    )
    pending = list_pending_approvals(session)
    resolved = resolve_approval(
        session,
        gate_id=gate.id,
        status="approved",
        resolved_by="adrian",
        rationale="Approved for constrained repo and branch scope.",
    )

    assert len(pending) == 1
    assert pending[0].id == gate.id
    assert resolved.status == "approved"
    assert resolved.resolved_by == "adrian"
    assert resolved.resolved_at is not None
    assert list_pending_approvals(session) == []
