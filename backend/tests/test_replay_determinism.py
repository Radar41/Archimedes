from __future__ import annotations

import json

from backend.app.models.shadow import ExecutionEnvelopeRecord, WorkflowRun
from backend.app.services.runtime_ledger import begin_action, finalize_action
from backend.app.workflows.asana_sync_in_v1 import _generate_change_events


def _seed_run_and_envelope(session) -> tuple[WorkflowRun, ExecutionEnvelopeRecord]:
    run = WorkflowRun(
        workflow_name="asana_sync_in_v1",
        workflow_version=1,
        status="running",
        archimedes_object_ref={"project_gid": "1213914133387697"},
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    envelope = ExecutionEnvelopeRecord(
        run_id=run.id,
        allowed_repos=[],
        allowed_branches=[],
        allowed_commands=["pytest"],
        allowed_envs=[],
        secret_scope_ref="hydra/runtime",
        max_cost_units=10,
    )
    session.add(envelope)
    session.commit()
    session.refresh(envelope)
    return run, envelope


def test_change_event_planner_is_replay_stable() -> None:
    before_snapshot = {
        "100": {
            "id": "task-1",
            "asana_gid": "100",
            "title": "Old title",
            "status": "incomplete",
            "section": "Runtime Core",
            "custom_fields_json": {},
            "updated_at": "2026-04-04T19:00:00+00:00",
        }
    }
    after_snapshot = {
        "100": {
            "id": "task-1",
            "asana_gid": "100",
            "title": "New title",
            "status": "completed",
            "section": "Runtime Core",
            "custom_fields_json": {},
            "updated_at": "2026-04-04T19:01:00+00:00",
        }
    }

    serialized_state = json.dumps({"before": before_snapshot, "after": after_snapshot}, sort_keys=True)
    replayed_state = json.loads(serialized_state)

    first_result = _generate_change_events(before_snapshot, after_snapshot)
    replay_result = _generate_change_events(replayed_state["before"], replayed_state["after"])

    assert first_result == replay_result
    assert first_result[0]["event_type"] == "updated"
    assert first_result[0]["changed_fields"] == ["status", "title", "updated_at"]


def test_idempotency_record_deduplicates_completed_action(session) -> None:
    run, envelope = _seed_run_and_envelope(session)

    action, attempt, idempotency = begin_action(
        session,
        run_id=run.id,
        envelope_id=envelope.id,
        adapter_type="asana",
        operation="update_task_status",
        idempotency_key="idem-1",
        request_payload={"task_gid": "100"},
    )
    assert attempt is not None
    assert idempotency is None

    finalize_action(
        session,
        action_id=action.id,
        attempt_id=attempt.id,
        outcome="success",
        response_summary={"task_gid": "100", "updated": True},
    )

    action_again, attempt_again, idempotency_again = begin_action(
        session,
        run_id=run.id,
        envelope_id=envelope.id,
        adapter_type="asana",
        operation="update_task_status",
        idempotency_key="idem-1",
        request_payload={"task_gid": "100"},
    )

    assert action_again.id == action.id
    assert attempt_again is None
    assert idempotency_again is not None


def test_action_request_retry_reuses_action_and_increments_attempt(session) -> None:
    run, envelope = _seed_run_and_envelope(session)

    action, attempt, _ = begin_action(
        session,
        run_id=run.id,
        envelope_id=envelope.id,
        adapter_type="github",
        operation="create_pr",
        idempotency_key="idem-retry",
        request_payload={"repo": "Radar41/Archimedes"},
    )
    assert attempt is not None

    finalize_action(
        session,
        action_id=action.id,
        attempt_id=attempt.id,
        outcome="retryable_fail",
        response_summary={"error": "timeout"},
        error_detail="network timeout",
    )

    action_retry, retry_attempt, _ = begin_action(
        session,
        run_id=run.id,
        envelope_id=envelope.id,
        adapter_type="github",
        operation="create_pr",
        idempotency_key="idem-retry",
        request_payload={"repo": "Radar41/Archimedes"},
    )

    assert action_retry.id == action.id
    assert retry_attempt is not None
    assert retry_attempt.attempt_num == 2
