from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.app.models.shadow import InboxEvent, ShadowTask, SyncCursor
from backend.app.services import inbound_sync as inbound


class FakeTask:
    def __init__(self, gid: str, name: str, completed: bool, section_name: str) -> None:
        self.gid = gid
        self.name = name
        self.completed = completed
        self.custom_fields = []
        self.memberships = [{"section": {"name": section_name}}]


async def fake_list_project_tasks(project_gid: str):
    return [
        FakeTask("100", "Task One", False, "Charter & Contracts"),
        FakeTask("200", "Task Two", True, "Runtime Core"),
    ]


async def fake_get_task(task_gid: str):
    mapping = {
        "100": FakeTask("100", "Task One", False, "Charter & Contracts"),
        "200": FakeTask("200", "Task Two", True, "Runtime Core"),
        "300": FakeTask("300", "Task Three", False, "Asana Bridge"),
    }
    return mapping[task_gid]


def test_sync_inbound_is_idempotent(session) -> None:
    original = inbound.list_project_tasks
    original_get = inbound.get_task
    inbound.list_project_tasks = fake_list_project_tasks
    inbound.get_task = fake_get_task
    try:
        result_one = __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
        result_two = __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
    finally:
        inbound.list_project_tasks = original
        inbound.get_task = original_get

    tasks = session.execute(select(ShadowTask)).scalars().all()
    assert result_one["inserted"] == 2
    assert result_one["incremental"] is False
    assert result_two["incremental"] is True
    assert result_two["updated"] == 0
    assert len(tasks) == 2
    cursor = session.execute(select(SyncCursor).where(SyncCursor.source == "asana_project:project")).scalar_one()
    assert cursor.cursor_value == result_two["cursor_after"]


def test_sync_inbound_uses_inbox_events_incrementally(session) -> None:
    original = inbound.list_project_tasks
    original_get = inbound.get_task
    inbound.list_project_tasks = fake_list_project_tasks
    inbound.get_task = fake_get_task
    try:
        first = __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
        session.add(
            InboxEvent(
                asana_gid="300",
                event_type="changed",
                payload_json={"resource": {"gid": "300"}},
                received_at=datetime.now(UTC) + timedelta(seconds=1),
                processed=False,
                dedupe_key="evt-300",
            )
        )
        session.commit()
        second = __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
    finally:
        inbound.list_project_tasks = original
        inbound.get_task = original_get

    tasks = session.execute(select(ShadowTask).order_by(ShadowTask.asana_gid.asc())).scalars().all()
    events = session.execute(select(InboxEvent)).scalars().all()
    assert first["total"] == 2
    assert second["incremental"] is True
    assert second["inserted"] == 1
    assert second["task_gids"] == ["300"]
    assert [task.asana_gid for task in tasks] == ["100", "200", "300"]
    assert events[0].processed is True


def test_consume_inbox_events_activity_processes_pending_rows(session) -> None:
    original = inbound.list_project_tasks
    original_get = inbound.get_task
    inbound.list_project_tasks = fake_list_project_tasks
    inbound.get_task = fake_get_task
    try:
        __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
        session.add(
            InboxEvent(
                asana_gid="300",
                event_type="changed",
                payload_json={"resource": {"gid": "300"}},
                received_at=datetime.now(UTC) + timedelta(seconds=1),
                processed=False,
                dedupe_key="evt-301",
            )
        )
        session.commit()
        result = __import__("asyncio").run(inbound.consume_pending_inbox_events(session, "project"))
    finally:
        inbound.list_project_tasks = original
        inbound.get_task = original_get

    assert result["pending_events_before"] == 1
    assert result["processed_events"] == 1
    assert result["task_gids"] == ["300"]
