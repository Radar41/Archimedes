from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class XMode(StrEnum):
    X0 = "x0"
    X_SUPPORT = "x_support"
    X_HIGH = "x_high"


class ScopeClassificationCode(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class PolicyEvaluation(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: uuid.UUID
    x_mode: XMode
    scope_classification: ScopeClassificationCode
    tool_allowlist: list[str] = Field(default_factory=list)
    side_effect_boundary: str
    token_budget: int = Field(ge=0)


class ExecutionEnvelope(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    policy: PolicyEvaluation
    allowed_repos: list[str] = Field(default_factory=list)
    allowed_branches: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=list)
    secret_scope_ref: str
    max_cost_units: int = Field(gt=0)

    @field_validator("allowed_repos", "allowed_branches", "allowed_commands")
    @classmethod
    def _dedupe_preserve_order(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
