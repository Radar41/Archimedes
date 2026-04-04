from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from backend.app.models.shadow import ArtifactRef
from backend.app.services.evidence import create_artifact_ref


def _hash_url(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def store_evidence(
    session: Session,
    *,
    task_id: uuid.UUID,
    diff_url: str,
    test_report_url: str,
    pr_url: str,
) -> list[ArtifactRef]:
    return [
        create_artifact_ref(
            session,
            task_id=task_id,
            artifact_type="diff",
            storage_url=diff_url,
            content_hash=_hash_url(diff_url),
        ),
        create_artifact_ref(
            session,
            task_id=task_id,
            artifact_type="test_report",
            storage_url=test_report_url,
            content_hash=_hash_url(test_report_url),
        ),
        create_artifact_ref(
            session,
            task_id=task_id,
            artifact_type="snapshot",
            storage_url=pr_url,
            content_hash=_hash_url(pr_url),
        ),
    ]
