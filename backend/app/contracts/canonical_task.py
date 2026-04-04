from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CanonicalTaskObject(BaseModel):
    id: uuid.UUID
    title: str
    objective: str | None = None
    done_when: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    primary_artifact: str | None = None
    status: str
    energy_band: str | None = None
    x_mode: str | None = None
    parent_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class HandoffPacket(BaseModel):
    task_id: uuid.UUID
    last_completed: str | None = None
    next_step: str
    blockers: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
