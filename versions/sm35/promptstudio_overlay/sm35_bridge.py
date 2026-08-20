"""Additive Prompt Studio bridge for the SM35 qualification candidate."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
from typing import Any

from .config import settings


SRC = settings.supermoon_runtime_dir / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

RUNTIME_AVAILABLE = False
IMPORT_ERROR: str | None = None
try:
    import supermoon35
    from supermoon35.physical import capability_matrix
    from supermoon35.qualification import candidate_decision
    RUNTIME_AVAILABLE = True
except Exception as exc:
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def overview() -> dict[str, Any]:
    if not RUNTIME_AVAILABLE:
        return {"available": False, "release": "SUPER MOON 35 NEW UNIVERSE QUALIFICATION CANDIDATE", "state": "BLOCKED_PENDING_REAL_EXECUTION", "error": IMPORT_ERROR}
    decision = candidate_decision()
    return {
        "available": True,
        "release": supermoon35.RELEASE_NAME,
        "version": supermoon35.VERSION,
        "state": supermoon35.RELEASE_STATE,
        "capabilities": [asdict(item) for item in capability_matrix()],
        "qualification": {**asdict(decision), "status": decision.status.value},
        "truth_boundary": "Architecture, contracts, and local tests do not replace physical qualification evidence.",
    }
