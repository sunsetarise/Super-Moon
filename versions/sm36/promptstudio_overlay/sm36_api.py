"""Optional FastAPI router added beside inherited SM34/SM35 endpoints."""

from fastapi import APIRouter, HTTPException

from .sm36_bridge import overview


router = APIRouter(prefix="/api/sm36", tags=["SM36"])


@router.get("/overview")
def sm36_overview():
    try:
        return overview()
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
