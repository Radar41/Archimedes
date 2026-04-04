from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0004_evidence_workflows_and_review_flags"
down_revision = "0003_schema_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_ref",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shadow_tasks.id"), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workflow_name", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archimedes_object_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_table(
        "review_flag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shadow_tasks.id"), nullable=False),
        sa.Column("flag_type", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_flag")
    op.drop_table("workflow_run")
    op.drop_table("artifact_ref")
