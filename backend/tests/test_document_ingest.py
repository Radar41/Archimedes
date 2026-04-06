from __future__ import annotations

import uuid

from backend.app.models.shadow import ArtifactRef, DocumentChunk, ShadowTask
from backend.app.services import document_ingest, evidence


def _seed_task(session) -> ShadowTask:
    task = ShadowTask(
        asana_gid=str(uuid.uuid4()),
        title="Document ingest",
        status="incomplete",
        section="Runtime Core",
        custom_fields_json={},
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_chunk_text_splits_large_content() -> None:
    text_body = "alpha " * 500
    chunks = document_ingest.chunk_text(text_body, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["metadata_json"]["start_offset"] < chunks[0]["metadata_json"]["end_offset"]


def test_ingest_artifact_document_persists_chunks(session) -> None:
    class FakeArtifactStore:
        def put_object(self, *, object_name: str, payload: bytes, content_type: str) -> str:
            return f"http://minio.local/{object_name}"

    async def fake_embed_texts(texts):
        values = list(texts)
        return [[float(index + 1), float(index + 2)] for index, _ in enumerate(values)]

    evidence._artifact_store = FakeArtifactStore()
    original_embed = document_ingest.embed_texts
    document_ingest.embed_texts = fake_embed_texts
    try:
        task = _seed_task(session)
        artifact = evidence.create_artifact_ref(
            session,
            task_id=task.id,
            artifact_type="source_document",
            payload=b"hello world " * 100,
            filename="doc.txt",
            content_type="text/plain",
        )
        chunks = __import__("asyncio").run(
            document_ingest.ingest_artifact_document(
                session,
                artifact=artifact,
                payload=b"hello world " * 100,
                filename="doc.txt",
                content_type="text/plain",
            )
        )
    finally:
        document_ingest.embed_texts = original_embed

    stored = session.query(DocumentChunk).filter(DocumentChunk.artifact_id == artifact.id).all()
    assert len(chunks) == len(stored) >= 1
    assert stored[0].artifact_id == artifact.id


def test_similarity_search_returns_ranked_chunks(session) -> None:
    async def fake_embed_texts(texts):
        values = list(texts)
        if values == ["volatility regime"]:
            return [[1.0, 0.0]]
        return [[1.0, 0.0] for _ in values]

    original_embed = document_ingest.embed_texts
    document_ingest.embed_texts = fake_embed_texts
    try:
        artifact = ArtifactRef(
            task_id=uuid.uuid4(),
            artifact_type="source_document",
            storage_url="http://example/artifact",
            content_hash="abc",
            immutable=False,
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        session.add_all(
            [
                DocumentChunk(
                    artifact_id=artifact.id,
                    chunk_index=0,
                    content="volatility regime signal",
                    embedding=[1.0, 0.0],
                    metadata_json={},
                ),
                DocumentChunk(
                    artifact_id=artifact.id,
                    chunk_index=1,
                    content="orthogonal text",
                    embedding=[0.0, 1.0],
                    metadata_json={},
                ),
            ]
        )
        session.commit()
        results = __import__("asyncio").run(
            document_ingest.similarity_search(session=session, query_text="volatility regime", top_k=1)
        )
    finally:
        document_ingest.embed_texts = original_embed

    assert len(results) == 1
    assert results[0]["chunk_index"] == 0
