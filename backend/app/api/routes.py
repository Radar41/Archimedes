from __future__ import annotations

import os
import subprocess
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.asana.client import AsanaClient
from backend.app.db import check_database, get_session
from backend.app.models.shadow import ShadowTask
from backend.app.services.document_ingest import ingest_artifact_document, similarity_search
from backend.app.services.evidence import create_artifact_ref
from backend.app.services.inbound_sync import run_inbound_sync

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


@router.post("/artifacts/upload")
async def upload_artifact(
    task_id: str = Form(...),
    artifact_type: str = Form("source_document"),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded artifact is empty.")
    artifact = create_artifact_ref(
        session,
        task_id=uuid.UUID(task_id),
        artifact_type=artifact_type,
        payload=payload,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
    )
    chunks = await ingest_artifact_document(
        session,
        artifact=artifact,
        payload=payload,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
    )
    return {
        "artifact_id": str(artifact.id),
        "storage_url": artifact.storage_url,
        "chunk_count": len(chunks),
        "content_hash": artifact.content_hash,
    }


@router.get("/artifacts/search")
async def search_artifacts(query: str, top_k: int = 5, session: Session = Depends(get_session)) -> list[dict]:
    return await similarity_search(session=session, query_text=query, top_k=top_k)
