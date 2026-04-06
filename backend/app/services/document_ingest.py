from __future__ import annotations

import json
import math
import os
import uuid
from collections.abc import Iterable
from io import BytesIO

import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from backend.app.models.shadow import ArtifactRef, DocumentChunk

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def extract_text(*, payload: bytes, content_type: str, filename: str | None = None) -> str:
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type in {"text/plain", "text/markdown", "text/csv"}:
        return payload.decode("utf-8")
    if normalized_type == "application/json":
        return json.dumps(json.loads(payload.decode("utf-8")), indent=2, sort_keys=True)
    if normalized_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(payload))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if filename and filename.lower().endswith((".md", ".txt", ".json", ".csv")):
        return extract_text(payload=payload, content_type="text/plain", filename=None)
    # TODO(asana:document-ingest): Add DOCX/HTML extractors when those artifact types enter the ingest pipeline.
    raise NotImplementedError(f"Unsupported document type for ingest: {content_type}")


def chunk_text(text_content: str, *, chunk_size: int = 800, overlap: int = 120) -> list[dict]:
    cleaned = " ".join(text_content.split())
    if not cleaned:
        return []
    chunks: list[dict] = []
    start = 0
    chunk_index = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunk_body = cleaned[start:end]
        chunks.append(
            {
                "chunk_index": chunk_index,
                "content": chunk_body,
                "metadata_json": {"start_offset": start, "end_offset": end},
            }
        )
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
        chunk_index += 1
    return chunks


async def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    values = list(texts)
    if not values:
        return []
    base_url = os.getenv("LITELLM_API_BASE", "http://localhost:4000").rstrip("/")
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("LITELLM_MASTER_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/v1/embeddings",
            headers=headers,
            json={"model": EMBEDDING_MODEL, "input": values},
        )
        response.raise_for_status()
    payload = response.json()
    return [list(item["embedding"]) for item in payload["data"]]


async def ingest_artifact_document(
    session: Session,
    *,
    artifact: ArtifactRef,
    payload: bytes,
    filename: str | None,
    content_type: str,
) -> list[DocumentChunk]:
    text_content = extract_text(payload=payload, content_type=content_type, filename=filename)
    chunks = chunk_text(text_content)
    if not chunks:
        return []

    embeddings = await embed_texts(chunk["content"] for chunk in chunks)
    session.execute(delete(DocumentChunk).where(DocumentChunk.artifact_id == artifact.id))
    stored: list[DocumentChunk] = []
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        row = DocumentChunk(
            artifact_id=artifact.id,
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            embedding=embedding,
            metadata_json=chunk["metadata_json"],
        )
        session.add(row)
        stored.append(row)
    session.commit()
    for row in stored:
        session.refresh(row)
    return stored


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


async def similarity_search(
    session: Session,
    *,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    [query_embedding] = await embed_texts([query_text])
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        vector_literal = "[" + ",".join(f"{value:.12f}" for value in query_embedding) + "]"
        stmt = text(
            """
            SELECT
              dc.id,
              dc.artifact_id,
              dc.chunk_index,
              dc.content,
              dc.metadata_json,
              dc.embedding <=> CAST(:query_embedding AS vector) AS distance
            FROM document_chunk AS dc
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
            """
        )
        rows = session.execute(stmt, {"query_embedding": vector_literal, "top_k": top_k}).mappings().all()
        return [
            {
                "chunk_id": str(row["id"]),
                "artifact_id": str(row["artifact_id"]),
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "metadata_json": row["metadata_json"],
                "score": 1.0 - float(row["distance"]),
            }
            for row in rows
        ]

    chunks = session.execute(select(DocumentChunk)).scalars().all()
    ranked = sorted(
        chunks,
        key=lambda chunk: _cosine_similarity(query_embedding, list(chunk.embedding)),
        reverse=True,
    )[:top_k]
    return [
        {
            "chunk_id": str(chunk.id),
            "artifact_id": str(chunk.artifact_id),
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "metadata_json": chunk.metadata_json,
            "score": _cosine_similarity(query_embedding, list(chunk.embedding)),
        }
        for chunk in ranked
    ]


def artifact_for_ingest(session: Session, artifact_id: uuid.UUID) -> ArtifactRef:
    artifact = session.get(ArtifactRef, artifact_id)
    if artifact is None:
        raise ValueError("Artifact reference not found for document ingest.")
    return artifact
