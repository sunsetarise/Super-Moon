"""Additive Prompt Studio bridge for Super Moon 36."""

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
    import supermoon36
    from supermoon36.physical import capability_matrix
    from supermoon36.qualification import candidate_decision
    RUNTIME_AVAILABLE = True
except Exception as exc:
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def overview() -> dict[str, Any]:
    if not RUNTIME_AVAILABLE:
        return {
            "available": False, "release": "SUPER MOON 36 NEW UNIVERSE QUALIFICATION CANDIDATE",
            "state": "BLOCKED_PENDING_REAL_EXECUTION", "error": IMPORT_ERROR,
        }
    decision = candidate_decision()
    return {
        "available": True, "release": supermoon36.RELEASE_NAME, "version": supermoon36.VERSION,
        "state": supermoon36.RELEASE_STATE, "methodologies": 15000,
        "capabilities": [asdict(item) for item in capability_matrix()],
        "qualification": {**asdict(decision), "state": decision.state.value},
        "truth_boundary": "Local software evidence cannot substitute for physical qualification or independent reproduction.",
    }
