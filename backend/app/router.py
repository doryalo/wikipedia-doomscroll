from fastapi import APIRouter, HTTPException

from .db import is_ready

router = APIRouter()


@router.get("/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["health"])
async def ready() -> dict[str, str]:
    if not is_ready():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}

