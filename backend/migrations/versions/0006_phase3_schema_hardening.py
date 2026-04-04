from __future__ import annotations

from alembic import op


revision = "0006_phase3_schema_hardening"
down_revision = "0005_execution_envelope_and_approval_gates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- artifact_ref index ---
    op.create_index("ix_artifact_ref_task_id", "artifact_ref", ["task_id"])

    # --- workflow_run index ---
    op.create_index("ix_workflow_run_status", "workflow_run", ["status"])

    # --- review_flag index + CHECK ---
    op.create_index("ix_review_flag_task_status", "review_flag", ["task_id", "status"])
    op.create_check_constraint(
        "ck_review_flag_status",
        "review_flag",
        "status IN ('open', 'resolved', 'dismissed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_review_flag_status", "review_flag", type_="check")
    op.drop_index("ix_review_flag_task_status", table_name="review_flag")
    op.drop_index("ix_workflow_run_status", table_name="workflow_run")
    op.drop_index("ix_artifact_ref_task_id", table_name="artifact_ref")
