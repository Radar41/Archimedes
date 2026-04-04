from __future__ import annotations

import hashlib
import hmac
import json

from sqlalchemy import select

from backend.app.models.shadow import InboxEvent


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_asana_webhook_handshake_echoes_secret(client) -> None:
    response = client.post(
        "/webhooks/asana",
        content=b"",
        headers={"X-Hook-Secret": "handshake-token-abc"},
    )
    assert response.status_code == 200
    assert response.headers["X-Hook-Secret"] == "handshake-token-abc"


def test_asana_webhook_rejects_invalid_signature(client, monkeypatch) -> None:
    monkeypatch.setenv("ASANA_WEBHOOK_SECRET", "test-secret")

    response = client.post(
        "/webhooks/asana",
        content=b'{"events":[]}',
        headers={"X-Hook-Signature": "invalid"},
    )

    assert response.status_code == 401


def test_asana_webhook_persists_and_dedupes_events(client, session, monkeypatch) -> None:
    monkeypatch.setenv("ASANA_WEBHOOK_SECRET", "test-secret")
    payload = {
        "events": [
            {
                "action": "changed",
                "resource": {"gid": "123"},
                "change": {"field": "name"},
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    signature = _sign("test-secret", body)

    first = client.post(
        "/webhooks/asana",
        content=body,
        headers={"X-Hook-Signature": signature, "Content-Type": "application/json"},
    )
    second = client.post(
        "/webhooks/asana",
        content=body,
        headers={"X-Hook-Signature": signature, "Content-Type": "application/json"},
    )

    events = session.execute(select(InboxEvent)).scalars().all()
    assert first.status_code == 200
    assert first.json() == {"received": 1, "deduped": 0}
    assert second.status_code == 200
    assert second.json() == {"received": 0, "deduped": 1}
    assert len(events) == 1
    assert events[0].asana_gid == "123"
    assert events[0].event_type == "changed"
