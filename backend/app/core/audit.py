"""Audit event logger — append-only audit trail."""
from datetime import datetime, timezone


class AuditLogger:
    def __init__(self, db):
        self.db = db

    def log(self, event_type: str, entity_type: str, entity_id: str,
            actor: str = "system", detail: str = "", metadata: dict | None = None):
        self.db.log_event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            detail=detail,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
