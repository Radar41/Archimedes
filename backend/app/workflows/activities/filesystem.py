from __future__ import annotations

from temporalio import activity

from backend.app.adapters.filesystem.scanner import scan_file_source
from backend.app.db import SessionLocal


@activity.defn
async def scan_filesystem_activity(source_id: str) -> dict:
    with SessionLocal() as session:
        return await scan_file_source(session, source_id)
