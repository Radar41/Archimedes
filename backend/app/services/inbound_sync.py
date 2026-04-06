from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.asana.service import get_task, list_project_tasks
from backend.app.models.shadow import InboxEvent, ShadowTask, SyncCursor


def _cursor_source(project_gid: str) -> str:
    return f"asana_project:{project_gid}"


def _task_status(task_completed: bool | None) -> str:
    return "completed" if task_completed else "incomplete"


def _task_section(task_memberships: list[dict]) -> str | None:
    if not task_memberships:
        return None
    first_membership = task_memberships[0]
    section = first_membership.get("section") if isinstance(first_membership, dict) else None
    if isinstance(section, dict):
        return section.get("name")
    return None


def _load_sync_cursor(session: Session, project_gid: str) -> SyncCursor | None:
    return session.execute(select(SyncCursor).where(SyncCursor.source == _cursor_source(project_gid))).scalar_one_or_none()


def _set_sync_cursor(session: Session, project_gid: str, cursor_value: str) -> SyncCursor:
    cursor = _load_sync_cursor(session, project_gid)
    now = datetime.now(UTC)
    if cursor is None:
        cursor = SyncCursor(source=_cursor_source(project_gid), cursor_value=cursor_value, updated_at=now)
    else:
        cursor.cursor_value = cursor_value
        cursor.updated_at = now
    session.add(cursor)
    return cursor


def _upsert_shadow_task(session: Session, task, synced_at: datetime) -> str:
    existing = session.execute(select(ShadowTask).where(ShadowTask.asana_gid == task.gid)).scalar_one_or_none()
    if existing is None:
        session.add(
            ShadowTask(
                asana_gid=task.gid,
                title=task.name,
                status=_task_status(task.completed),
                section=_task_section(task.memberships),
                custom_fields_json={"custom_fields": task.custom_fields},
                synced_at=synced_at,
                updated_at=synced_at,
            )
        )
        return "inserted"

    existing.title = task.name
    existing.status = _task_status(task.completed)
    existing.section = _task_section(task.memberships)
    existing.custom_fields_json = {"custom_fields": task.custom_fields}
    existing.synced_at = synced_at
    existing.updated_at = synced_at
    return "updated"


def _pending_inbox_events(
    session: Session,
    *,
    since: datetime | None,
    changed_task_gids: list[str] | None = None,
) -> list[InboxEvent]:
    stmt = select(InboxEvent).where(InboxEvent.processed.is_(False)).order_by(InboxEvent.received_at.asc())
    if since is not None:
        stmt = stmt.where(InboxEvent.received_at >= since)
    if changed_task_gids:
        stmt = stmt.where(InboxEvent.asana_gid.in_(changed_task_gids))
    return session.execute(stmt).scalars().all()


async def _load_tasks_for_sync(
    session: Session,
    *,
    project_gid: str,
    cursor: SyncCursor | None,
    changed_task_gids: list[str] | None,
) -> tuple[list, list[InboxEvent], bool]:
    cursor_dt = None
    if cursor is not None:
        cursor_dt = datetime.fromisoformat(cursor.cursor_value)

    pending_events = _pending_inbox_events(
        session,
        since=cursor_dt,
        changed_task_gids=changed_task_gids,
    )
    event_task_gids = sorted({event.asana_gid for event in pending_events if event.asana_gid})
    if changed_task_gids:
        event_task_gids = sorted(set(event_task_gids) | set(changed_task_gids))

    if cursor is None and not changed_task_gids:
        return await list_project_tasks(project_gid=project_gid), pending_events, False

    if not event_task_gids:
        return [], pending_events, True

    tasks = []
    for task_gid in event_task_gids:
        tasks.append(await get_task(task_gid))
    return tasks, pending_events, True


async def run_inbound_sync(
    session: Session,
    project_gid: str,
    *,
    changed_task_gids: list[str] | None = None,
) -> dict[str, int | str | bool | list[str]]:
    cursor_before = _load_sync_cursor(session, project_gid)
    tasks, pending_events, incremental = await _load_tasks_for_sync(
        session,
        project_gid=project_gid,
        cursor=cursor_before,
        changed_task_gids=changed_task_gids,
    )
    synced_at = datetime.now(UTC)
    inserted = 0
    updated = 0
    processed_events = 0

    for task in tasks:
        outcome = _upsert_shadow_task(session, task, synced_at)
        if outcome == "inserted":
            inserted += 1
        else:
            updated += 1

    for event in pending_events:
        event.processed = True
        session.add(event)
        processed_events += 1

    cursor_after = synced_at.isoformat()
    _set_sync_cursor(session, project_gid, cursor_after)
    session.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "total": len(tasks),
        "incremental": incremental,
        "cursor_before": cursor_before.cursor_value if cursor_before else "",
        "cursor_after": cursor_after,
        "processed_events": processed_events,
        "task_gids": [task.gid for task in tasks],
    }


async def consume_pending_inbox_events(session: Session, project_gid: str) -> dict[str, int | str | list[str] | bool]:
    pending = session.query(InboxEvent).filter(InboxEvent.processed.is_(False)).count()
    sync_result = await run_inbound_sync(session=session, project_gid=project_gid)
    return {
        "project_gid": project_gid,
        "pending_events_before": pending,
        "processed_events": sync_result["processed_events"],
        "task_gids": sync_result["task_gids"],
        "sync_result": sync_result,
    }
