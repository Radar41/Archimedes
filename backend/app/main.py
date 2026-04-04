from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.asana_webhooks import router as asana_webhooks_router
from backend.app.api.routes import router
from backend.app.db import engine
from backend.app.models.shadow import Base
from backend.app.services.otel_setup import init_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_telemetry(app)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Archimedes", lifespan=lifespan)
app.include_router(router)
app.include_router(asana_webhooks_router)
