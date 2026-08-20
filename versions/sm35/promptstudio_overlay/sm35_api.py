"""FastAPI router added alongside inherited SM34 endpoints."""

from fastapi import APIRouter, HTTPException
from .sm35_bridge import overview


router = APIRouter(prefix="/api/sm35", tags=["SM35"])


@router.get("/overview")
def sm35_overview():
    try:
        return overview()
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
