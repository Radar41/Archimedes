from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0005_execution_envelope_and_approval_gates"
down_revision = "0004_evidence_workflows_and_review_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_envelope",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column("allowed_repos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_branches", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_commands", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_envs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("secret_scope_ref", sa.Text(), nullable=False),
        sa.Column("max_cost_units", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "policy_decision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column(
            "envelope_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("execution_envelope.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "approval_gate",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column("gate_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("approval_gate")
    op.drop_table("policy_decision")
    op.drop_table("execution_envelope")
