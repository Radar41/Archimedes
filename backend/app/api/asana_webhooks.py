from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db import get_session
from backend.app.models.shadow import InboxEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _signature_secret() -> str:
    secret = os.getenv("ASANA_WEBHOOK_SECRET")
    if not secret:
        raise NotImplementedError("ASANA_WEBHOOK_SECRET must be configured for webhook validation.")
    return secret


def _expected_signature(body: bytes) -> str:
    return hmac.new(
        _signature_secret().encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


def _event_records(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    events = payload.get("events")
    if isinstance(events, list) and events:
        return events
    return [payload]


@router.post("/asana", response_model=None)
async def ingest_asana_webhook(
    request: Request,
    session: Session = Depends(get_session),
    x_hook_secret: str | None = Header(default=None, alias="X-Hook-Secret"),
    x_hook_signature: str | None = Header(default=None, alias="X-Hook-Signature"),
) -> Response | dict[str, int]:
    # --- Asana handshake: echo X-Hook-Secret to establish the webhook ---
    if x_hook_secret is not None:
        return Response(
            status_code=200,
            headers={"X-Hook-Secret": x_hook_secret},
        )

    # --- Normal delivery: validate signature ---
    if x_hook_signature is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing webhook signature.")

    body = await request.body()
    expected_signature = _expected_signature(body)
    if not hmac.compare_digest(x_hook_signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature.")

    payload = json.loads(body.decode("utf-8") or "{}")
    inserted = 0
    deduped = 0
    for record in _event_records(payload):
        dedupe_key = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        inbox_event = InboxEvent(
            asana_gid=(record.get("resource") or {}).get("gid"),
            event_type=record.get("action") or record.get("type") or "webhook_event",
            payload_json=record,
            dedupe_key=dedupe_key,
        )
        session.add(inbox_event)
        try:
            session.commit()
            inserted += 1
        except IntegrityError:
            session.rollback()
            deduped += 1

    return {"received": inserted, "deduped": deduped}
