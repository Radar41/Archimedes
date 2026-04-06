from __future__ import annotations

import uuid

from backend.app.models.shadow import ShadowTask
from backend.app.services import document_ingest, evidence


def test_upload_artifact_endpoint(client, session) -> None:
    class FakeArtifactStore:
        def put_object(self, *, object_name: str, payload: bytes, content_type: str) -> str:
            return f"http://minio.local/{object_name}"

    async def fake_embed_texts(texts):
        values = list(texts)
        return [[1.0, 0.0] for _ in values]

    evidence._artifact_store = FakeArtifactStore()
    original_embed = document_ingest.embed_texts
    document_ingest.embed_texts = fake_embed_texts
    try:
        task = ShadowTask(
            asana_gid=str(uuid.uuid4()),
            title="Upload target",
            status="incomplete",
            section="Runtime Core",
            custom_fields_json={},
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        response = client.post(
            "/artifacts/upload",
            data={"task_id": str(task.id), "artifact_type": "source_document"},
            files={"file": ("notes.txt", b"signal extraction " * 80, "text/plain")},
        )
    finally:
        document_ingest.embed_texts = original_embed

    assert response.status_code == 200
    payload = response.json()
    assert payload["chunk_count"] >= 1
    assert payload["content_hash"]
