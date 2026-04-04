from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import AdjacentQueueItem


def create_item(
    session: Session,
    *,
    origin_task_id: uuid.UUID,
    title: str,
    candidate_action: str,
    classification: str,
) -> AdjacentQueueItem:
    item = AdjacentQueueItem(
        origin_task_id=origin_task_id,
        title=title,
        candidate_action=candidate_action,
        classification=classification,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_items(session: Session, *, status: str | None = None) -> list[AdjacentQueueItem]:
    stmt = select(AdjacentQueueItem).order_by(AdjacentQueueItem.created_at.asc())
    if status is not None:
        stmt = stmt.where(AdjacentQueueItem.status == status)
    return session.execute(stmt).scalars().all()


def promote_item(session: Session, item_id: uuid.UUID) -> AdjacentQueueItem:
    item = session.get(AdjacentQueueItem, item_id)
    if item is None:
        raise NotImplementedError("Adjacent queue item not found for promotion.")
    item.status = "promoted"
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def dismiss_item(session: Session, item_id: uuid.UUID) -> AdjacentQueueItem:
    item = session.get(AdjacentQueueItem, item_id)
    if item is None:
        raise NotImplementedError("Adjacent queue item not found for dismissal.")
    item.status = "dismissed"
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
