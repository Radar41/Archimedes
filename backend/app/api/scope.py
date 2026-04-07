"""EBL scope evaluation HTTP surface."""
from fastapi import APIRouter
from pydantic import BaseModel

from ..services.scope_gate import evaluate_scope

router = APIRouter(prefix="/scope", tags=["ebl"])


class ScopeRequest(BaseModel):
    description: str
    task_id: str | None = None
    x_mode: str = "x1_align"
    work_class: str = "build"


@router.post("/evaluate")
async def evaluate(req: ScopeRequest):
    task = {"x_mode": req.x_mode, "work_class": req.work_class} if req.task_id else None
    return evaluate_scope(req.description, task=task)
