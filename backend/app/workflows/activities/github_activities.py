from __future__ import annotations

import uuid

from temporalio import activity

from backend.app.adapters.github.evidence import store_evidence
from backend.app.adapters.github.service import create_branch, create_pr
from backend.app.db import SessionLocal


@activity.defn
async def create_branch_activity(payload: dict) -> dict:
    return await create_branch(
        repository=str(payload["repository"]),
        branch_name=str(payload["branch_name"]),
        source_sha=str(payload["source_sha"]),
    )


@activity.defn
async def create_pr_activity(payload: dict) -> dict:
    return await create_pr(
        repository=str(payload["repository"]),
        title=str(payload["title"]),
        body=str(payload["body"]),
        head=str(payload["head"]),
        base=str(payload["base"]),
    )


@activity.defn
async def collect_evidence_activity(payload: dict) -> list[dict]:
    with SessionLocal() as session:
        artifacts = store_evidence(
            session,
            task_id=uuid.UUID(str(payload["task_id"])),
            diff_url=str(payload["diff_url"]),
            test_report_url=str(payload["test_report_url"]),
            pr_url=str(payload["pr_url"]),
        )
    return [
        {
            "id": str(artifact.id),
            "task_id": str(artifact.task_id),
            "artifact_type": artifact.artifact_type,
            "storage_url": artifact.storage_url,
            "content_hash": artifact.content_hash,
            "immutable": artifact.immutable,
        }
        for artifact in artifacts
    ]
