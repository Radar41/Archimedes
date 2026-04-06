from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0009_filesystem_ingest"
down_revision = "0008_document_ingest_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()

    op.create_table(
        "file_source",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shadow_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("include_glob", sa.Text(), nullable=False, server_default=sa.text("'**/*'")),
        sa.Column("cursor_value", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ux_file_source_root_path", "file_source", ["root_path"], unique=True)

    op.create_table(
        "file_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("file_source.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artifact_ref.id", ondelete="SET NULL"), nullable=True),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mtime_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ux_file_metadata_source_relpath", "file_metadata", ["source_id", "relative_path"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_file_metadata_source_relpath", table_name="file_metadata")
    op.drop_table("file_metadata")
    op.drop_index("ux_file_source_root_path", table_name="file_source")
    op.drop_table("file_source")
