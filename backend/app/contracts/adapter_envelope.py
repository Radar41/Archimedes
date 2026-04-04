from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdapterErrorClass(StrEnum):
    RETRYABLE = "retryable"
    FATAL = "fatal"
    POLICY_DENIED = "policy_denied"


class AdapterRequestEnvelope(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    adapter_type: str
    operation: str
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AdapterResponseEnvelope(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    request_id: uuid.UUID
    adapter_type: str
    operation: str
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    error_class: AdapterErrorClass | None = None
    error_message: str | None = None
