from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.models.shadow import ReviewFlag


def render_page() -> None:
    st.title("Drift Review Queue")
    with SessionLocal() as session:
        flags = (
            session.execute(
                select(ReviewFlag)
                .where(ReviewFlag.status == "open")
                .order_by(ReviewFlag.created_at.asc())
            )
            .scalars()
            .all()
        )

    st.dataframe(
        [
            {
                "id": str(flag.id),
                "task_id": str(flag.task_id),
                "flag_type": flag.flag_type,
                "summary": flag.summary,
                "status": flag.status,
                "created_at": flag.created_at.isoformat(),
            }
            for flag in flags
        ],
        use_container_width=True,
    )


if __name__ == "__main__":
    render_page()
