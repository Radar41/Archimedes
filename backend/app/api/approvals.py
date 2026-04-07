"""Approval gate HTTP surface."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/approvals", tags=["governance"])


class ApprovalDecision(BaseModel):
    decision: str  # approved, denied
    reason: str = ""
    actor: str = "radar41"


@router.post("/{gate_id}/decision")
async def decide(gate_id: str, body: ApprovalDecision):
    # TODO: wire to approval service
    return {"gate_id": gate_id, "decision": body.decision, "status": "stub_acknowledged"}
