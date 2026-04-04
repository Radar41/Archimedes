from __future__ import annotations

import os

from dotenv import load_dotenv

from backend.app.adapters.asana.client import AsanaClient
from backend.app.adapters.asana.schemas import Section, Story, Task

load_dotenv()

DEFAULT_WORKSPACE_GID = os.getenv("ASANA_WORKSPACE_GID", "952160553655161")
DEFAULT_PROJECT_GID = os.getenv("ASANA_PROJECT_GID", "1213914133387697")

TASK_FIELDS = "gid,name,completed,custom_fields,memberships.section.name"
STORY_FIELDS = "gid,resource_type,text,created_at"
SECTION_FIELDS = "gid,name"


async def _paginate(client: AsanaClient, path: str, params: dict | None = None) -> list[dict]:
    results: list[dict] = []
    next_params = dict(params or {})
    while True:
        payload = await client.get(path, params=next_params)
        results.extend(payload.get("data", []))
        next_page = payload.get("next_page")
        if not next_page or not next_page.get("offset"):
            return results
        next_params["offset"] = next_page["offset"]


async def list_project_tasks(
    project_gid: str = DEFAULT_PROJECT_GID,
    client: AsanaClient | None = None,
) -> list[Task]:
    owns_client = client is None
    client = client or AsanaClient()
    try:
        payload = await _paginate(client, f"/projects/{project_gid}/tasks", {"opt_fields": TASK_FIELDS})
        return [Task.model_validate(item) for item in payload]
    finally:
        if owns_client:
            await client.close()


async def get_task(task_gid: str, client: AsanaClient | None = None) -> Task:
    owns_client = client is None
    client = client or AsanaClient()
    try:
        payload = await client.get(f"/tasks/{task_gid}", {"opt_fields": TASK_FIELDS})
        return Task.model_validate(payload["data"])
    finally:
        if owns_client:
            await client.close()


async def list_stories(task_gid: str, client: AsanaClient | None = None) -> list[Story]:
    owns_client = client is None
    client = client or AsanaClient()
    try:
        payload = await _paginate(client, f"/tasks/{task_gid}/stories", {"opt_fields": STORY_FIELDS})
        return [Story.model_validate(item) for item in payload]
    finally:
        if owns_client:
            await client.close()


async def list_sections(
    project_gid: str = DEFAULT_PROJECT_GID,
    client: AsanaClient | None = None,
) -> list[Section]:
    owns_client = client is None
    client = client or AsanaClient()
    try:
        payload = await _paginate(client, f"/projects/{project_gid}/sections", {"opt_fields": SECTION_FIELDS})
        return [Section.model_validate(item) for item in payload]
    finally:
        if owns_client:
            await client.close()

