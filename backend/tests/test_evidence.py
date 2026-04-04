from __future__ import annotations

import uuid

from backend.app.adapters.github.evidence import store_evidence
from backend.app.models.shadow import ShadowTask
from backend.app.services.evidence import (
    create_artifact_ref,
    finalize_artifact,
    list_artifacts_for_task,
)


def _seed_task(session) -> ShadowTask:
    task = ShadowTask(
        asana_gid=str(uuid.uuid4()),
        title="Evidence Task",
        status="in_progress",
        section="Runtime Core",
        custom_fields_json={},
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_evidence_lifecycle(session) -> None:
    task = _seed_task(session)

    artifact = create_artifact_ref(
        session,
        task_id=task.id,
        artifact_type="log",
        storage_url="https://example.com/log.txt",
        content_hash="abc123",
    )
    artifacts = list_artifacts_for_task(session, task.id)
    finalized = finalize_artifact(session, artifact.id)

    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "log"
    assert finalized.immutable is True


def test_store_evidence_creates_linked_artifacts(session) -> None:
    task = _seed_task(session)

    artifacts = store_evidence(
        session,
        task_id=task.id,
        diff_url="https://github.com/org/repo/pull/1/files",
        test_report_url="https://ci.example.com/reports/1",
        pr_url="https://github.com/org/repo/pull/1",
    )

    assert [artifact.artifact_type for artifact in artifacts] == ["diff", "test_report", "snapshot"]
    assert all(artifact.task_id == task.id for artifact in artifacts)
