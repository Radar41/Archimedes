from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.shadow import ArtifactRef


def create_artifact_ref(
    session: Session,
    *,
    task_id: uuid.UUID,
    artifact_type: str,
    storage_url: str,
    content_hash: str,
    immutable: bool = False,
) -> ArtifactRef:
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
