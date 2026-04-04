from __future__ import annotations

import asyncio

import streamlit as st
from sqlalchemy import func, select

from backend.app.adapters.asana.client import AsanaClient
from backend.app.db import SessionLocal, check_database
from backend.app.models.shadow import ShadowTask


def render_page() -> None:
    st.title("Runtime Health")

    db_ok = check_database()
    asana_ok = asyncio.run(_check_asana())
    last_sync = _last_sync_timestamp()

    st.metric("Database", "connected" if db_ok else "unreachable")
    st.metric("Asana Adapter", "reachable" if asana_ok else "unreachable")
    st.metric("Last Sync", last_sync or "never")


async def _check_asana() -> bool:
    async with AsanaClient() as client:
        try:
            return await client.check()
        except Exception:
            return False


def _last_sync_timestamp() -> str | None:
    with SessionLocal() as session:
        last_sync = session.execute(select(func.max(ShadowTask.synced_at))).scalar_one()
    return last_sync.isoformat() if last_sync is not None else None


if __name__ == "__main__":
    render_page()
