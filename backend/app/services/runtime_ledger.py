from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import ActionAttempt, ActionRequest, IdempotencyRecord


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def begin_action(
    session: Session,
    *,
    run_id: uuid.UUID,
    envelope_id: uuid.UUID,
    adapter_type: str,
    operation: str,
    idempotency_key: str,
    request_payload: dict[str, Any],
) -> tuple[ActionRequest, ActionAttempt | None, IdempotencyRecord | None]:
    idempotency = session.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)
    ).scalar_one_or_none()
    if idempotency is not None:
        action = session.execute(
            select(ActionRequest).where(ActionRequest.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if action is None:
            action = ActionRequest(
                run_id=run_id,
                envelope_id=envelope_id,
                adapter_type=adapter_type,
                operation=operation,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                status="succeeded",
            )
            session.add(action)
            session.commit()
            session.refresh(action)
        return action, None, idempotency

    action = session.execute(
        select(ActionRequest).where(ActionRequest.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if action is None:
        action = ActionRequest(
            run_id=run_id,
            envelope_id=envelope_id,
            adapter_type=adapter_type,
            operation=operation,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            status="in_progress",
        )
        session.add(action)
        session.flush()
    else:
        action.status = "in_progress"

    latest_attempt = session.execute(
        select(ActionAttempt)
        .where(ActionAttempt.action_id == action.id)
        .order_by(ActionAttempt.attempt_num.desc())
    ).scalar_one_or_none()
    attempt_num = 1 if latest_attempt is None else latest_attempt.attempt_num + 1
    attempt = ActionAttempt(action_id=action.id, attempt_num=attempt_num, response_summary={})
    session.add(attempt)
    session.commit()
    session.refresh(action)
    session.refresh(attempt)
    return action, attempt, None


def finalize_action(
    session: Session,
    *,
    action_id: uuid.UUID,
    attempt_id: uuid.UUID,
    outcome: str,
    response_summary: dict[str, Any] | None = None,
    error_detail: str | None = None,
    idempotency_ttl: timedelta = timedelta(days=7),
) -> tuple[ActionRequest, ActionAttempt]:
    action = session.get(ActionRequest, action_id)
    attempt = session.get(ActionAttempt, attempt_id)
    if action is None or attempt is None:
        raise NotImplementedError("Action request or attempt not found for finalization.")

    ended_at = datetime.now(UTC)
    attempt.ended_at = ended_at
    attempt.outcome = outcome
    attempt.response_summary = response_summary or {}
    attempt.error_detail = error_detail

    if outcome == "success":
        action.status = "succeeded"
        record = IdempotencyRecord(
            key=action.idempotency_key,
            result_hash=_hash_payload(attempt.response_summary),
            created_at=ended_at,
            expires_at=ended_at + idempotency_ttl,
        )
        session.add(record)
    elif outcome == "policy_denied":
        action.status = "blocked"
    else:
        action.status = "failed"

    action.updated_at = ended_at
    session.add(action)
    session.add(attempt)
    session.commit()
    session.refresh(action)
    session.refresh(attempt)
    return action, attempt
