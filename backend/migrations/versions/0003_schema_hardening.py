from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0003_schema_hardening"
down_revision = "0002_audit_and_expansion_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- audit_event indexes ---
    op.create_index("ix_audit_event_subject", "audit_event", ["subject_type", "subject_id"])
    op.create_index("ix_audit_event_type_created", "audit_event", ["event_type", "created_at"])

    # --- adjacent_queue_item: FK, CHECK, index, updated_at ---
    op.add_column(
        "adjacent_queue_item",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_adjacent_queue_origin_task",
        "adjacent_queue_item",
        "shadow_tasks",
        ["origin_task_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_adjacent_queue_status",
        "adjacent_queue_item",
        "status IN ('queued', 'promoted', 'dismissed')",
    )
    op.create_index("ix_adjacent_queue_status_created", "adjacent_queue_item", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_adjacent_queue_status_created", table_name="adjacent_queue_item")
    op.drop_constraint("ck_adjacent_queue_status", "adjacent_queue_item", type_="check")
    op.drop_constraint("fk_adjacent_queue_origin_task", "adjacent_queue_item", type_="foreignkey")
    op.drop_column("adjacent_queue_item", "updated_at")
    op.drop_index("ix_audit_event_type_created", table_name="audit_event")
    op.drop_index("ix_audit_event_subject", table_name="audit_event")
