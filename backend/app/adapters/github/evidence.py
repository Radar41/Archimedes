from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from backend.app.models.shadow import ArtifactRef


def _url_fingerprint(value: str) -> str:
    """Hash the URL itself as a stable fingerprint. This is NOT a content hash."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def store_evidence(
    session: Session,
    *,
    task_id: uuid.UUID,
    diff_url: str,
    test_report_url: str,
    pr_url: str,
) -> list[ArtifactRef]:
    artifacts = [
        ArtifactRef(
            task_id=task_id,
            artifact_type="diff",
            storage_url=diff_url,
            content_hash=_url_fingerprint(diff_url),
        ),
        ArtifactRef(
            task_id=task_id,
            artifact_type="test_report",
            storage_url=test_report_url,
            content_hash=_url_fingerprint(test_report_url),
        ),
        ArtifactRef(
            task_id=task_id,
            artifact_type="snapshot",
            storage_url=pr_url,
            content_hash=_url_fingerprint(pr_url),
        ),
    ]
    session.add_all(artifacts)
    session.commit()
    for artifact in artifacts:
        session.refresh(artifact)
    return artifacts
