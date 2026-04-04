from __future__ import annotations

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.shadow import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database() -> bool:
    with SessionLocal() as session:
        session.execute(select(1))
    return True
