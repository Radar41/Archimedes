from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.app.adapters.asana.service import list_project_tasks
from backend.app.models.shadow import ShadowTask


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


async def run_inbound_sync(session: Session, project_gid: str) -> dict[str, int]:
    tasks = await list_project_tasks(project_gid=project_gid)
    synced_at = datetime.now(UTC)
    inserted = 0
    updated = 0

    for task in tasks:
        existing = session.query(ShadowTask).filter(ShadowTask.asana_gid == task.gid).one_or_none()
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
            inserted += 1
            continue

        existing.title = task.name
        existing.status = _task_status(task.completed)
        existing.section = _task_section(task.memberships)
        existing.custom_fields_json = {"custom_fields": task.custom_fields}
        existing.synced_at = synced_at
        existing.updated_at = synced_at
        updated += 1

    session.commit()
    return {"inserted": inserted, "updated": updated, "total": len(tasks)}
