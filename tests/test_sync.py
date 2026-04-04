from __future__ import annotations

from sqlalchemy import select

from backend.app.db import ShadowTask
from backend.app.sync import inbound


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


def test_sync_inbound_is_idempotent(session) -> None:
    original = inbound.list_project_tasks
    inbound.list_project_tasks = fake_list_project_tasks
    try:
        result_one = __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
        result_two = __import__("asyncio").run(inbound.run_inbound_sync(session, "project"))
    finally:
        inbound.list_project_tasks = original

    tasks = session.execute(select(ShadowTask)).scalars().all()
    assert result_one["inserted"] == 2
    assert result_two["updated"] == 2
    assert len(tasks) == 2
