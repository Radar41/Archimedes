from __future__ import annotations

import os
import subprocess

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.asana.client import AsanaClient
from backend.app.db import ShadowTask, check_database, get_session
from backend.app.sync.inbound import run_inbound_sync

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    db_ok = check_database()
    asana_ok = False
    async with AsanaClient() as client:
        try:
            asana_ok = await client.check()
        except Exception:
            asana_ok = False
    return {"status": "ok", "db": {"ok": db_ok}, "asana": {"ok": asana_ok}}


@router.get("/version")
def version() -> dict[str, str]:
    try:
        sha = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
        )
    except Exception:
        sha = "dev"
    return {"version": sha}


@router.get("/tasks")
def list_tasks(session: Session = Depends(get_session)) -> list[dict]:
    tasks = session.execute(select(ShadowTask).order_by(ShadowTask.created_at.asc())).scalars().all()
    return [
        {
            "id": str(task.id),
            "asana_gid": task.asana_gid,
            "title": task.title,
            "status": task.status,
            "section": task.section,
            "custom_fields_json": task.custom_fields_json,
            "synced_at": task.synced_at.isoformat(),
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }
        for task in tasks
    ]


@router.post("/sync/inbound")
async def sync_inbound(session: Session = Depends(get_session)) -> dict[str, int]:
    project_gid = os.getenv("ASANA_PROJECT_GID", "1213914133387697")
    return await run_inbound_sync(session=session, project_gid=project_gid)

