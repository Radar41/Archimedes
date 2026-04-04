from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from backend.app.contracts.policy_types import ExecutionEnvelope, PolicyEvaluation


def test_execution_envelope_dedupes_allowlists() -> None:
    envelope = ExecutionEnvelope(
        policy=PolicyEvaluation(
            task_id=uuid.uuid4(),
            x_mode="x_support",
            scope_classification="B",
            tool_allowlist=["asana", "github"],
            side_effect_boundary="repo_and_task_comment_only",
            token_budget=1200,
        ),
        allowed_repos=["Radar41/Archimedes", "Radar41/Archimedes"],
        allowed_branches=["main", "main", "feature/hydra"],
        allowed_commands=["pytest", "pytest", "git status"],
        secret_scope_ref="hydra/runtime",
        max_cost_units=25,
    )

    assert envelope.allowed_repos == ["Radar41/Archimedes"]
    assert envelope.allowed_branches == ["main", "feature/hydra"]
    assert envelope.allowed_commands == ["pytest", "git status"]


def test_execution_envelope_requires_positive_cost_limit() -> None:
    with pytest.raises(ValidationError):
        ExecutionEnvelope(
            policy=PolicyEvaluation(
                task_id=uuid.uuid4(),
                x_mode="x0",
                scope_classification="A",
                tool_allowlist=[],
                side_effect_boundary="none",
                token_budget=0,
            ),
            allowed_repos=[],
            allowed_branches=[],
            allowed_commands=[],
            secret_scope_ref="hydra/runtime",
            max_cost_units=0,
        )
