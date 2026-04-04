from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    model_config = ConfigDict(extra="allow")

    gid: str
    name: str


class Story(BaseModel):
    model_config = ConfigDict(extra="allow")

    gid: str
    resource_type: str | None = None
    text: str | None = None
    created_at: str | None = None


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")

    gid: str
    name: str
    completed: bool | None = None
    custom_fields: list[dict] = Field(default_factory=list)
    memberships: list[dict] = Field(default_factory=list)

