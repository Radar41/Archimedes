"""Health check endpoint with version reporting."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.6.1",
        "service": "archimedes",
    }
