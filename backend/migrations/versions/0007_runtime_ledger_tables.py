from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0007_runtime_ledger_tables"
down_revision = "0006_phase3_schema_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_step",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "action_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("execution_envelope.id"), nullable=False),
        sa.Column("adapter_type", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False, unique=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_action_request_status",
        "action_request",
        "status IN ('pending', 'in_progress', 'succeeded', 'failed', 'blocked')",
    )
    op.create_table(
        "action_attempt",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("action_request.id"), nullable=False),
        sa.Column("attempt_num", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("response_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_action_attempt_outcome",
        "action_attempt",
        "outcome IN ('success', 'retryable_fail', 'fatal_fail', 'policy_denied')",
    )
    op.create_table(
        "external_object_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("external_system", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("canonical_type", sa.Text(), nullable=False),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ux_external_object_map_system_external",
        "external_object_map",
        ["external_system", "external_id"],
        unique=True,
    )
    op.create_index(
        "ix_external_object_map_canonical",
        "external_object_map",
        ["canonical_type", "canonical_id"],
    )
    op.create_table(
        "sync_cursor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("cursor_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ux_sync_cursor_source", "sync_cursor", ["source"], unique=True)
    op.create_table(
        "idempotency_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.Text(), nullable=False, unique=True),
        sa.Column("result_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency_record")
    op.drop_index("ux_sync_cursor_source", table_name="sync_cursor")
    op.drop_table("sync_cursor")
    op.drop_index("ix_external_object_map_canonical", table_name="external_object_map")
    op.drop_index("ux_external_object_map_system_external", table_name="external_object_map")
    op.drop_table("external_object_map")
    op.drop_constraint("ck_action_attempt_outcome", "action_attempt", type_="check")
    op.drop_table("action_attempt")
    op.drop_constraint("ck_action_request_status", "action_request", type_="check")
    op.drop_table("action_request")
    op.drop_table("workflow_step")
