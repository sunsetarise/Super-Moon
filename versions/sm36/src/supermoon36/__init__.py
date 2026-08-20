"""SUPER MOON 36 executable qualification layer."""

from .contracts import ClaimLevel, MethodologyResult, ResultState, ValidationError
from .qualification import ReleaseDecision, score_release

VERSION = "36.0.0"
RELEASE_NAME = "SUPER MOON 36 NEW UNIVERSE QUALIFICATION CANDIDATE"
RELEASE_STATE = "BLOCKED_PENDING_REAL_EXECUTION"

__all__ = [
    "ClaimLevel",
    "MethodologyResult",
    "RELEASE_NAME",
    "RELEASE_STATE",
    "ReleaseDecision",
    "ResultState",
    "VERSION",
    "ValidationError",
    "score_release",
]

