from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.models.shadow import WorkflowRun


def render_page() -> None:
    st.title("Workflow Runs")
    with SessionLocal() as session:
        runs = (
            session.execute(select(WorkflowRun).order_by(WorkflowRun.started_at.desc()))
            .scalars()
            .all()
        )

    st.dataframe(
        [
            {
                "id": str(run.id),
                "workflow_name": run.workflow_name,
                "workflow_version": run.workflow_version,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            }
            for run in runs
        ],
        use_container_width=True,
    )


if __name__ == "__main__":
    render_page()
