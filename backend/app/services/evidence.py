from __future__ import annotations

import hashlib
import os
import uuid
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import ArtifactRef

_ARTIFACT_BUCKET = "archimedes-artifacts"
_artifact_store = None


def _minio_settings() -> tuple[str, str, str]:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000").removeprefix("http://").removeprefix("https://")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    return endpoint, access_key, secret_key


class _MinioArtifactStore:
    def __init__(self) -> None:
        from minio import Minio

        endpoint, access_key, secret_key = _minio_settings()
        self.endpoint = endpoint
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(_ARTIFACT_BUCKET):
            self.client.make_bucket(_ARTIFACT_BUCKET)

    def put_object(self, *, object_name: str, payload: bytes, content_type: str) -> str:
        self._ensure_bucket()
        self.client.put_object(
            _ARTIFACT_BUCKET,
            object_name,
            BytesIO(payload),
            length=len(payload),
            content_type=content_type,
        )
        return f"http://{self.endpoint}/{_ARTIFACT_BUCKET}/{object_name}"


def _get_artifact_store() -> _MinioArtifactStore:
    global _artifact_store
    if _artifact_store is None:
        _artifact_store = _MinioArtifactStore()
    return _artifact_store


def create_artifact_ref(
    session: Session,
    *,
    task_id: uuid.UUID,
    artifact_type: str,
    payload: bytes,
    filename: str | None = None,
    content_type: str = "application/octet-stream",
    immutable: bool = False,
) -> ArtifactRef:
    content_hash = hashlib.sha256(payload).hexdigest()
    object_name = filename or f"{task_id}/{artifact_type}/{content_hash}"
    storage_url = _get_artifact_store().put_object(
        object_name=object_name,
        payload=payload,
        content_type=content_type,
    )
    artifact = ArtifactRef(
        task_id=task_id,
        artifact_type=artifact_type,
        storage_url=storage_url,
        content_hash=content_hash,
        immutable=immutable,
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


def list_artifacts_for_task(session: Session, task_id: uuid.UUID) -> list[ArtifactRef]:
    stmt = (
        select(ArtifactRef)
        .where(ArtifactRef.task_id == task_id)
        .order_by(ArtifactRef.created_at.asc())
    )
    return session.execute(stmt).scalars().all()


def finalize_artifact(session: Session, artifact_id: uuid.UUID) -> ArtifactRef:
    artifact = session.get(ArtifactRef, artifact_id)
    if artifact is None:
        raise NotImplementedError("Artifact reference not found for finalization.")
    artifact.immutable = True
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact
