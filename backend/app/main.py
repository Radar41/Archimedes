from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.asana_webhooks import router as asana_webhooks_router
from backend.app.api.routes import router
from backend.app.db import engine
from backend.app.models.shadow import Base


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Archimedes", lifespan=lifespan)
app.include_router(router)
app.include_router(asana_webhooks_router)
