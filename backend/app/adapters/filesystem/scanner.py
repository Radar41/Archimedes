from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import FileMetadata, FileSource
from backend.app.services.document_ingest import ingest_artifact_document
from backend.app.services.evidence import create_artifact_ref


@dataclass
class ScannedFile:
    relative_path: str
    absolute_path: Path
    mtime_utc: datetime


def _iter_candidate_files(source: FileSource) -> list[ScannedFile]:
    root = Path(source.root_path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Filesystem source root does not exist: {root}")

    cursor_dt = datetime.fromisoformat(source.cursor_value) if source.cursor_value else None
    discovered: list[ScannedFile] = []
    for path in sorted(root.glob(source.include_glob)):
        if not path.is_file():
            continue
        stat = path.stat()
        mtime_utc = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        if cursor_dt is not None and mtime_utc <= cursor_dt:
            continue
        discovered.append(
            ScannedFile(
                relative_path=str(path.relative_to(root)),
                absolute_path=path,
                mtime_utc=mtime_utc,
            )
        )
    return discovered


async def scan_file_source(session: Session, source_id: str) -> dict:
    source = session.get(FileSource, uuid.UUID(str(source_id)))
    if source is None:
        raise ValueError("File source not found.")
    candidates = _iter_candidate_files(source)
    if not candidates:
        return {"source_id": str(source.id), "scanned": 0, "ingested": 0, "cursor_after": source.cursor_value or ""}

    ingested = 0
    latest_cursor = source.cursor_value
    for candidate in candidates:
        payload = candidate.absolute_path.read_bytes()
        content_hash = hashlib.sha256(payload).hexdigest()
        metadata = session.execute(
            select(FileMetadata).where(
                FileMetadata.source_id == source.id,
                FileMetadata.relative_path == candidate.relative_path,
            )
        ).scalar_one_or_none()
        if metadata is not None and metadata.content_hash == content_hash:
            metadata.mtime_utc = candidate.mtime_utc
            metadata.updated_at = datetime.now(UTC)
            session.add(metadata)
            latest_cursor = candidate.mtime_utc.isoformat()
            continue

        artifact = create_artifact_ref(
            session,
            task_id=source.task_id,
            artifact_type="filesystem_document",
            payload=payload,
            filename=f"{source.id}/{candidate.relative_path}",
            content_type="text/plain",
        )
        await ingest_artifact_document(
            session,
            artifact=artifact,
            payload=payload,
            filename=candidate.relative_path,
            content_type="text/plain",
        )
        if metadata is None:
            metadata = FileMetadata(
                source_id=source.id,
                artifact_id=artifact.id,
                relative_path=candidate.relative_path,
                content_hash=content_hash,
                size_bytes=len(payload),
                mtime_utc=candidate.mtime_utc,
            )
        else:
            metadata.artifact_id = artifact.id
            metadata.content_hash = content_hash
            metadata.size_bytes = len(payload)
            metadata.mtime_utc = candidate.mtime_utc
            metadata.updated_at = datetime.now(UTC)
        session.add(metadata)
        ingested += 1
        latest_cursor = candidate.mtime_utc.isoformat()

    source.cursor_value = latest_cursor
    source.updated_at = datetime.now(UTC)
    session.add(source)
    session.commit()
    return {
        "source_id": str(source.id),
        "scanned": len(candidates),
        "ingested": ingested,
        "cursor_after": latest_cursor,
    }
