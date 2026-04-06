from __future__ import annotations

import uuid

from backend.app.adapters.filesystem.scanner import scan_file_source
from backend.app.models.shadow import DocumentChunk, FileMetadata, FileSource, ShadowTask
from backend.app.services import document_ingest, evidence


def test_scan_file_source_ingests_changed_files(session, tmp_path) -> None:
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
            title="Filesystem ingest",
            status="incomplete",
            section="Runtime Core",
            custom_fields_json={},
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        root = tmp_path / "source"
        root.mkdir()
        (root / "notes.md").write_text("filesystem ingest " * 50, encoding="utf-8")
        source = FileSource(
            name="local-docs",
            task_id=task.id,
            root_path=str(root),
            include_glob="**/*",
            cursor_value=None,
            active=True,
        )
        session.add(source)
        session.commit()
        session.refresh(source)

        result = __import__("asyncio").run(scan_file_source(session, str(source.id)))
    finally:
        document_ingest.embed_texts = original_embed

    metadata = session.query(FileMetadata).filter(FileMetadata.source_id == source.id).all()
    chunks = session.query(DocumentChunk).all()
    assert result["scanned"] == 1
    assert result["ingested"] == 1
    assert len(metadata) == 1
    assert len(chunks) >= 1


def test_scan_file_source_uses_mtime_cursor(session, tmp_path) -> None:
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
            title="Filesystem ingest cursor",
            status="incomplete",
            section="Runtime Core",
            custom_fields_json={},
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        root = tmp_path / "source"
        root.mkdir()
        path = root / "notes.md"
        path.write_text("first pass", encoding="utf-8")
        source = FileSource(
            name="local-docs",
            task_id=task.id,
            root_path=str(root),
            include_glob="**/*",
            cursor_value=None,
            active=True,
        )
        session.add(source)
        session.commit()
        session.refresh(source)

        first = __import__("asyncio").run(scan_file_source(session, str(source.id)))
        second = __import__("asyncio").run(scan_file_source(session, str(source.id)))
    finally:
        document_ingest.embed_texts = original_embed

    assert first["ingested"] == 1
    assert second["ingested"] == 0
