from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Index, JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import UserDefinedType
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Use JSONB on PostgreSQL, fall back to JSON on other dialects (e.g. SQLite in tests)
JSONVariant = JSON().with_variant(JSONB, "postgresql")


class PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:
        return f"vector({self.dimensions})"


EmbeddingVariant = JSON().with_variant(PgVector(1536), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ShadowTask(Base):
    __tablename__ = "shadow_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asana_gid: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    section: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_fields_json: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class InboxEvent(Base):
    __tablename__ = "inbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asana_gid: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dedupe_key: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)


class IdMapping(Base):
    __tablename__ = "id_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asana_gid: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    object_type: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_subject", "subject_type", "subject_id"),
        Index("ix_audit_event_type_created", "event_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AdjacentQueueItem(Base):
    __tablename__ = "adjacent_queue_item"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'promoted', 'dismissed')", name="ck_adjacent_queue_status"),
        Index("ix_adjacent_queue_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    origin_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shadow_tasks.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_action: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ArtifactRef(Base):
    __tablename__ = "artifact_ref"
    __table_args__ = (
        Index("ix_artifact_ref_task_id", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shadow_tasks.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunk"
    __table_args__ = (
        Index("ix_document_chunk_artifact_chunk", "artifact_id", "chunk_index", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_ref.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVariant, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class FileSource(Base):
    __tablename__ = "file_source"
    __table_args__ = (
        Index("ux_file_source_root_path", "root_path", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    include_glob: Mapped[str] = mapped_column(Text, nullable=False, default="**/*")
    cursor_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class FileMetadata(Base):
    __tablename__ = "file_metadata"
    __table_args__ = (
        Index("ux_file_metadata_source_relpath", "source_id", "relative_path", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_source.id", ondelete="CASCADE"), nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_ref.id", ondelete="SET NULL"), nullable=True)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mtime_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_run"
    __table_args__ = (
        Index("ix_workflow_run_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_name: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archimedes_object_ref: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)


class WorkflowStep(Base):
    __tablename__ = "workflow_step"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_run.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ExecutionEnvelopeRecord(Base):
    __tablename__ = "execution_envelope"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_run.id"), nullable=False)
    allowed_repos: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    allowed_branches: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    allowed_commands: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    allowed_envs: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    secret_scope_ref: Mapped[str] = mapped_column(Text, nullable=False)
    max_cost_units: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class PolicyDecision(Base):
    __tablename__ = "policy_decision"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_run.id"), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("execution_envelope.id"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ApprovalGate(Base):
    __tablename__ = "approval_gate"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_run.id"), nullable=False)
    gate_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActionRequest(Base):
    __tablename__ = "action_request"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'succeeded', 'failed', 'blocked')",
            name="ck_action_request_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_run.id"), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("execution_envelope.id"), nullable=False)
    adapter_type: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    request_payload: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ActionAttempt(Base):
    __tablename__ = "action_attempt"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'retryable_fail', 'fatal_fail', 'policy_denied')",
            name="ck_action_attempt_outcome",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("action_request.id"), nullable=False)
    attempt_num: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_summary: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalObjectMap(Base):
    __tablename__ = "external_object_map"
    __table_args__ = (
        Index("ix_external_object_map_canonical", "canonical_type", "canonical_id"),
        Index("ux_external_object_map_system_external", "external_system", "external_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_system: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SyncCursor(Base):
    __tablename__ = "sync_cursor"
    __table_args__ = (
        Index("ux_sync_cursor_source", "source", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    cursor_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    result_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewFlag(Base):
    __tablename__ = "review_flag"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name="ck_review_flag_status"),
        Index("ix_review_flag_task_status", "task_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shadow_tasks.id"), nullable=False)
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
