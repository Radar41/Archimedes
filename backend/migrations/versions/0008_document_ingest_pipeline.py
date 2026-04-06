from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0008_document_ingest_pipeline"
down_revision = "0007_runtime_ledger_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type = sa.UserDefinedType()
        embedding_type.get_col_spec = lambda **kw: "vector(1536)"  # type: ignore[attr-defined]
    else:
        embedding_type = sa.JSON()

    op.create_table(
        "document_chunk",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artifact_ref.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_chunk_artifact_chunk", "document_chunk", ["artifact_id", "chunk_index"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_document_chunk_artifact_chunk", table_name="document_chunk")
    op.drop_table("document_chunk")
